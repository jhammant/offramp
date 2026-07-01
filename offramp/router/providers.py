"""Cheaper-host adapters. All OpenAI-compatible, so one impl covers most.

Real network calls are gated behind OFFRAMP_LIVE_ROUTING=1 + a host API key, so
nothing spends money by default. `MockProvider` lets the whole replay/route loop
run deterministically offline.
"""
from __future__ import annotations

import hashlib
import os
from typing import Protocol

# OpenAI-compatible base URLs for the cheaper hosts.
ENDPOINTS = {
    "groq":       "https://api.groq.com/openai/v1",
    "together":   "https://api.together.xyz/v1",
    "deepinfra":  "https://api.deepinfra.com/v1/openai",
    "openrouter": "https://openrouter.ai/api/v1",
}
KEY_ENV = {
    "groq": "GROQ_API_KEY",
    "together": "TOGETHER_API_KEY",
    "deepinfra": "DEEPINFRA_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


class Provider(Protocol):
    def chat(self, model: str, request: dict) -> dict:
        """Take an OpenAI-shaped request, return an OpenAI-shaped response."""
        ...


def _prompt_text(request: dict) -> str:
    return " ".join(m.get("content", "") for m in request.get("messages", []))


def _mock_completion(model: str, request: dict, drift: float = 0.0) -> str:
    """Deterministic pseudo-output for offline eval. The 'answer' is derived from
    the PROMPT (model-independent), so an equivalent candidate reproduces it;
    `drift` (0..1) replaces that fraction of tokens with model-seeded noise, plus
    a per-prompt difficulty jitter so pass-rates spread across prompts. Judge
    agreement then tracks `drift` — which replay() ties to the capability gap."""
    text = _prompt_text(request)
    n = 20
    base = [hashlib.sha1((str(i) + text).encode()).hexdigest()[:6] for i in range(n)]
    if drift > 0:
        jitter = ((int(hashlib.sha1(text.encode()).hexdigest(), 16) % 21) - 10) / 100.0
        eff = min(0.6, max(0.0, drift + jitter))
        k = int(round(n * eff))
        seed = int(hashlib.sha256(model.encode()).hexdigest(), 16)
        for j in range(k):
            base[(seed + j) % n] = f"x{(seed + j) % 97:02d}"
    return " ".join(base)


class MockProvider:
    """Offline, deterministic — for tests, demos, and dry runs. Never bills."""

    def __init__(self, host: str = "mock", drift: float = 0.0):
        self.host = host
        self.drift = drift

    def chat(self, model: str, request: dict) -> dict:
        content = _mock_completion(model, request, self.drift)
        pt = len(_prompt_text(request).split())
        ct = len(content.split())
        return {
            "choices": [{"message": {"role": "assistant", "content": content},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": pt, "completion_tokens": ct,
                      "total_tokens": pt + ct},
        }


class OpenAICompatProvider:
    """Groq/Together/DeepInfra/OpenRouter — all OpenAI-compatible."""

    def __init__(self, host: str):
        if host not in ENDPOINTS:
            raise ValueError(f"unknown host {host!r}")
        self.host = host
        self.base_url = ENDPOINTS[host]

    def chat(self, model: str, request: dict) -> dict:  # pragma: no cover - needs network+key
        key = os.environ.get(KEY_ENV[self.host])
        if not key:
            raise SystemExit(f"{KEY_ENV[self.host]} not set — cannot call {self.host}")
        from urllib import request as urlreq
        import json
        body = json.dumps({**request, "model": model}).encode()
        req = urlreq.Request(f"{self.base_url}/chat/completions", data=body,
                             headers={"Authorization": f"Bearer {key}",
                                      "Content-Type": "application/json"})
        with urlreq.urlopen(req) as resp:
            return json.loads(resp.read())


def get_provider(host: str, *, drift: float = 0.0) -> Provider:
    """Return a live provider only when explicitly enabled; else the mock."""
    if os.environ.get("OFFRAMP_LIVE_ROUTING") == "1" and host in ENDPOINTS:
        return OpenAICompatProvider(host)
    return MockProvider(host, drift=drift)
