"""Bedrock Converse <-> OpenAI Chat Completions mapping (Phase 2, text happy path).

Cheaper hosts (Groq/Together/DeepInfra/OpenRouter) speak the OpenAI schema, so
routing = Converse request -> OpenAI request, then OpenAI response -> Converse
response. Tool-calling / multimodal are deliberately out of scope for v1.
"""
from __future__ import annotations


def converse_to_openai(model: str, messages: list, system: list | None = None,
                       inference_config: dict | None = None) -> dict:
    oai_messages = []
    for block in (system or []):
        if "text" in block:
            oai_messages.append({"role": "system", "content": block["text"]})
    for m in messages:
        text = " ".join(c.get("text", "") for c in m.get("content", []))
        oai_messages.append({"role": m["role"], "content": text})
    cfg = inference_config or {}
    req = {"model": model, "messages": oai_messages}
    if "maxTokens" in cfg:
        req["max_tokens"] = cfg["maxTokens"]
    if "temperature" in cfg:
        req["temperature"] = cfg["temperature"]
    return req


def openai_to_converse(resp: dict) -> dict:
    choice = resp["choices"][0]
    text = choice["message"]["content"]
    usage = resp.get("usage", {})
    return {
        "output": {"message": {"role": "assistant", "content": [{"text": text}]}},
        "stopReason": choice.get("finish_reason", "end_turn"),
        "usage": {
            "inputTokens": usage.get("prompt_tokens", 0),
            "outputTokens": usage.get("completion_tokens", 0),
            "totalTokens": usage.get("total_tokens", 0),
        },
    }
