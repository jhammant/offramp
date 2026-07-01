"""Route/shadow migration layer — exercised offline via the mock provider."""
import json

import pytest

from offramp.router.shim import Client, Ledger
from offramp.router.translate import converse_to_openai, openai_to_converse


class FakeBedrock:
    """Stand-in for boto3 bedrock-runtime so route tests never touch AWS."""

    def __init__(self):
        self.calls = 0

    def converse(self, **kwargs):
        self.calls += 1
        return {
            "output": {"message": {"role": "assistant", "content": [{"text": "REAL bedrock"}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 5, "outputTokens": 4, "totalTokens": 9},
        }


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    # unset live routing so get_provider() returns the deterministic MockProvider
    monkeypatch.delenv("OFFRAMP_LIVE_ROUTING", raising=False)


def _client(tmp_path, **kw):
    return Client(ledger=Ledger(path=str(tmp_path / "ledger.jsonl")), **kw)


def test_route_open_weight_serves_cheaper_host(tmp_path):
    c = _client(tmp_path, mode="route", prefer_host="groq")
    fake = FakeBedrock()
    c._bedrock = fake
    resp = c.converse(
        modelId="gpt-oss-120b",
        messages=[{"role": "user", "content": [{"text": "hello"}]}],
    )
    assert resp["offramp"]["routed_to"] == "groq"
    assert resp["offramp"]["same_weights_as"] == "gpt-oss-120b"
    assert resp["offramp"]["saved_per_1m"] > 0
    assert fake.calls == 0  # never hit Bedrock — served from the cheaper host
    assert resp["output"]["message"]["content"][0]["text"]  # a real (mock) answer


def test_route_proprietary_passes_through(tmp_path):
    c = _client(tmp_path, mode="route")
    fake = FakeBedrock()
    c._bedrock = fake
    resp = c.converse(
        modelId="anthropic.claude-opus-4-6-v1:0",
        messages=[{"role": "user", "content": [{"text": "hi"}]}],
    )
    assert "offramp" not in resp  # never rerouted
    assert fake.calls == 1
    assert resp["output"]["message"]["content"][0]["text"] == "REAL bedrock"


def test_shadow_serves_real_but_logs_candidate(tmp_path):
    path = tmp_path / "ledger.jsonl"
    c = Client(mode="shadow", prefer_host="groq", ledger=Ledger(path=str(path)))
    fake = FakeBedrock()
    c._bedrock = fake
    resp = c.converse(
        modelId="gpt-oss-120b",
        messages=[{"role": "user", "content": [{"text": "hi"}]}],
    )
    assert resp["output"]["message"]["content"][0]["text"] == "REAL bedrock"  # served real
    assert fake.calls == 1
    row = [json.loads(line) for line in open(path)][-1]
    assert row["shadow_host"] == "groq"
    assert row["would_save_per_1m"] > 0


def test_route_target_policy(tmp_path):
    c = _client(tmp_path, mode="route", prefer_host="groq")
    assert c.route_target("gpt-oss-120b") is not None
    assert c.route_target("anthropic.claude-opus-4-6-v1:0") is None  # proprietary
    denied = _client(tmp_path, mode="route", prefer_host="groq", deny=["gpt-oss"])
    assert denied.route_target("gpt-oss-120b") is None


def test_observe_is_pure_passthrough(tmp_path):
    c = _client(tmp_path, mode="observe")
    fake = FakeBedrock()
    c._bedrock = fake
    resp = c.converse(
        modelId="gpt-oss-120b",
        messages=[{"role": "user", "content": [{"text": "hi"}]}],
    )
    assert "offramp" not in resp
    assert fake.calls == 1  # observe never reroutes, even an open-weight model


def test_translate_roundtrip():
    req = converse_to_openai(
        "m",
        [{"role": "user", "content": [{"text": "hi"}]}],
        system=[{"text": "be brief"}],
        inference_config={"maxTokens": 32, "temperature": 0.2},
    )
    assert req["messages"][0] == {"role": "system", "content": "be brief"}
    assert req["max_tokens"] == 32 and req["temperature"] == 0.2
    conv = openai_to_converse(
        {"choices": [{"message": {"content": "yo"}, "finish_reason": "stop"}],
         "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}}
    )
    assert conv["output"]["message"]["content"][0]["text"] == "yo"
    assert conv["usage"]["totalTokens"] == 3
