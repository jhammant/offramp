"""Drop-in Bedrock client shim. Observe mode is real; shadow/route are guarded."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field


@dataclass
class Ledger:
    """Append-only record of observed calls (for request-level analysis)."""
    path: str = "offramp-ledger.jsonl"
    count: int = 0

    def record(self, model_id: str, usage: dict) -> None:
        row = {"model_id": model_id, "usage": usage}
        with open(self.path, "a") as fh:
            fh.write(json.dumps(row) + "\n")
        self.count += 1


@dataclass
class Client:
    mode: str = "observe"          # observe | shadow | route
    region_name: str | None = None
    ledger: Ledger = field(default_factory=Ledger)
    _bedrock: object = None

    def _real(self):
        if self._bedrock is None:
            import boto3
            self._bedrock = boto3.client("bedrock-runtime", region_name=self.region_name)
        return self._bedrock

    def converse(self, **kwargs):
        if self.mode == "observe":
            resp = self._real().converse(**kwargs)
            self.ledger.record(kwargs.get("modelId", "?"), resp.get("usage", {}))
            return resp
        # shadow/route need the Converse<->OpenAI translator + a priced, approved
        # target + provider adapter. Guarded so we never reroute/spend silently.
        raise NotImplementedError(
            f"mode={self.mode!r} not wired yet. Run `offramp analyze` first, approve a "
            "target, then Phase-2 enables shadow/route. See offramp/router/translate.py."
        )

    def converse_stream(self, **kwargs):
        if self.mode == "observe":
            return self._real().converse_stream(**kwargs)
        raise NotImplementedError("streaming shadow/route is Phase 2")

    def __getattr__(self, name):
        # Anything we don't override passes straight through to real Bedrock.
        return getattr(self._real(), name)


def client(service_name: str = "bedrock-runtime", *, mode: str | None = None,
           region_name: str | None = None) -> Client:
    if service_name != "bedrock-runtime":
        raise ValueError("offramp.client only shims 'bedrock-runtime'")
    return Client(mode=mode or os.environ.get("OFFRAMP_MODE", "observe"),
                  region_name=region_name)
