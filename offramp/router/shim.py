"""Drop-in Bedrock client shim — the actual migration layer.

Swap ``boto3.client("bedrock-runtime")`` for ``offramp.client(...)`` and pick a mode:

  observe : pass every call straight through to real Bedrock, recording usage.
            Zero behaviour change — just request-level visibility.
  shadow  : serve the REAL Bedrock response, but ALSO run the cheaper candidate
            in parallel and log it. A zero-risk production comparison.
  route   : transparently serve approved open-weight models from the cheaper host
            (same weights, no quality change); everything else falls through to
            Bedrock untouched. This is the migration.

Safety by construction: only same-weights arbitrage is ever auto-routed. Proprietary
models (Claude/Nova/GPT/Gemini) have no cheaper twin, so ``route`` never touches
them. A *substitution* (a different, cheaper model) is a quality bet and is NEVER
auto-routed here — that decision lives behind ``offramp optimize`` + policy + your
sign-off. Real host calls need OFFRAMP_LIVE_ROUTING=1 + a host key; otherwise the
deterministic mock provider answers, so the whole path runs offline.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from .. import prices
from .providers import get_provider, host_model_name
from .translate import converse_to_openai, openai_to_converse


@dataclass
class Ledger:
    """Append-only record of observed/routed calls (for request-level analysis)."""

    path: str = "offramp-ledger.jsonl"
    count: int = 0

    def record(self, model_id: str, usage: dict, **meta) -> None:
        row = {"model_id": model_id, "usage": usage, **meta}
        with open(self.path, "a") as fh:
            fh.write(json.dumps(row) + "\n")
        self.count += 1


@dataclass
class RouteTarget:
    host: str
    host_model: str
    source: prices.TextModel
    alt: prices.TextModel

    @property
    def saved_per_1m(self) -> float:
        return round(self.source.blended() - self.alt.blended(), 3)


@dataclass
class Client:
    mode: str = "observe"                 # observe | shadow | route
    region_name: str | None = None
    prefer_host: str | None = None        # force a specific cheaper host (else cheapest)
    allow: list = field(default_factory=list)  # if set, only these route (substring)
    deny: list = field(default_factory=list)   # never route these (substring)
    ledger: Ledger = field(default_factory=Ledger)
    _bedrock: object = None

    # -- real Bedrock (lazy; only imported/created when actually needed) --------
    def _real(self):
        if self._bedrock is None:
            import boto3

            self._bedrock = boto3.client("bedrock-runtime", region_name=self.region_name)
        return self._bedrock

    def _blocked(self, model_id: str) -> bool:
        mid = model_id.lower()
        if any(d.lower() in mid for d in self.deny):
            return True
        if self.allow and not any(a.lower() in mid for a in self.allow):
            return True
        return False

    def route_target(self, model_id: str) -> RouteTarget | None:
        """The safe routing target for a model, or None if it must stay on Bedrock.

        A target exists only when the model is open-weight (identical weights run
        elsewhere), a cheaper host carries it, and policy allows it."""
        m = prices.find_text_model(model_id)
        if not m or m.weight_class != "open" or self._blocked(model_id):
            return None
        alt = None
        if self.prefer_host:
            rows = [r for r in prices.TEXT_ROWS
                    if r.id == m.id and r.provider == self.prefer_host]
            alt = rows[0] if rows else None
        if alt is None:
            alt = prices.cheapest_alt(m.id)
        if not alt or alt.blended() >= m.blended():
            return None
        return RouteTarget(alt.provider, host_model_name(alt.provider, m.id), m, alt)

    # -- the drop-in Converse entrypoint --------------------------------------
    def converse(self, **kwargs):
        model_id = kwargs.get("modelId", "?")

        if self.mode == "observe":
            resp = self._real().converse(**kwargs)
            self.ledger.record(model_id, resp.get("usage", {}), routed=False)
            return resp

        target = self.route_target(model_id)
        if target is None:
            # proprietary / blocked / no cheaper host -> serve the real, trusted model
            resp = self._real().converse(**kwargs)
            self.ledger.record(model_id, resp.get("usage", {}), routed=False,
                               reason="no cheaper twin — served from Bedrock")
            return resp

        oai_req = converse_to_openai(
            target.host_model,
            kwargs.get("messages", []),
            kwargs.get("system"),
            kwargs.get("inferenceConfig"),
        )
        provider = get_provider(target.host)

        if self.mode == "shadow":
            real = self._real().converse(**kwargs)
            try:
                cand = openai_to_converse(provider.chat(target.host_model, oai_req))
                self.ledger.record(model_id, real.get("usage", {}), routed=False,
                                   shadow_host=target.host,
                                   shadow_usage=cand["usage"],
                                   would_save_per_1m=target.saved_per_1m)
            except Exception as exc:  # shadow must never break the real call
                self.ledger.record(model_id, real.get("usage", {}), routed=False,
                                   shadow_error=str(exc))
            return real

        # route: serve the cheaper host (same weights, no quality change)
        cand = openai_to_converse(provider.chat(target.host_model, oai_req))
        cand["offramp"] = {
            "routed_to": target.host,
            "same_weights_as": target.source.id,
            "saved_per_1m": target.saved_per_1m,
        }
        self.ledger.record(model_id, cand["usage"], routed=True, host=target.host,
                           saved_per_1m=target.saved_per_1m)
        return cand

    def converse_stream(self, **kwargs):
        # Streaming translation is out of v1 scope: always serve real Bedrock.
        return self._real().converse_stream(**kwargs)

    def __getattr__(self, name):
        # Anything we don't override passes straight through to real Bedrock.
        # Guard private/dunder misses so introspection/pickling never spins up boto3.
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._real(), name)


def client(service_name: str = "bedrock-runtime", *, mode: str | None = None,
           region_name: str | None = None, host: str | None = None,
           allow: list | None = None, deny: list | None = None) -> Client:
    if service_name != "bedrock-runtime":
        raise ValueError("offramp.client only shims 'bedrock-runtime'")
    return Client(mode=mode or os.environ.get("OFFRAMP_MODE", "observe"),
                  region_name=region_name, prefer_host=host,
                  allow=allow or [], deny=deny or [])
