"""Replay-eval: prove a substitution on YOUR prompts before routing to it.

Take a sample of real prompts, run them through the reference model and a cheaper
candidate, judge output equivalence, and report agreement + projected savings.
That turns "capability 92->84 (prior)" into a measured number on your traffic.

Offline by default: `get_provider` returns a deterministic MockProvider unless
OFFRAMP_LIVE_ROUTING=1. The judge is pluggable — lexical similarity by default;
swap in an LLM-as-judge for real runs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import SequenceMatcher

from . import prices
from .router.providers import get_provider, host_model_name


@dataclass
class ReplayResult:
    reference: str
    candidate: str
    n: int
    agreement: float          # mean judge score, 0..1
    pass_rate: float          # fraction >= threshold
    threshold: float
    projected_saving_per_1m: float
    verdict: str              # "recommend" | "review" | "reject"
    misses: list[dict]

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        return d


def lexical_judge(a: str, b: str) -> float:
    """Cheap default judge. Replace with an LLM-as-judge for production runs."""
    return SequenceMatcher(None, a, b).ratio()


def groq_judge(a: str, b: str) -> float:
    """LLM-as-judge: ask a fast Groq model how semantically equivalent two answers
    are (0..1). Needs GROQ_API_KEY. Falls back to lexical on any parse failure."""
    import re
    from .router.providers import OpenAICompatProvider
    prov = OpenAICompatProvider("groq")
    req = {"messages": [
        {"role": "system", "content": "You judge whether two AI answers to the same "
         "prompt are equivalent in meaning. Reply with ONLY a number from 0.0 to 1.0 "
         "(1.0 = same meaning, 0.0 = unrelated). No words."},
        {"role": "user", "content": f"Answer A:\n{a}\n\nAnswer B:\n{b}\n\nScore:"}],
        "temperature": 0, "max_tokens": 8}
    try:
        out = prov.chat("llama-3.1-8b-instant", req)["choices"][0]["message"]["content"]
        m = re.search(r"[01](?:\.\d+)?|\.\d+", out)
        return max(0.0, min(1.0, float(m.group()))) if m else lexical_judge(a, b)
    except Exception:
        return lexical_judge(a, b)


def _to_openai(prompt: str) -> dict:
    return {"messages": [{"role": "user", "content": prompt}], "max_tokens": 512}


def replay(prompts: list[str], reference_id: str, candidate_id: str, *,
           threshold: float = 0.8, judge=lexical_judge,
           candidate_drift: float | None = None, host: str | None = None) -> ReplayResult:
    ref_model = prices.SOURCE.get(reference_id) or prices.target(reference_id)
    cand_model = prices.target(candidate_id)
    # In mock mode, expected disagreement grows with the capability gap — so the
    # offline demo exercises recommend/review/reject. A live eval ignores this and
    # measures real agreement instead.
    if candidate_drift is None:
        gap = max(0, ref_model.capability - cand_model.capability)
        candidate_drift = min(0.5, 0.04 + gap * 0.02)
    if host:  # live: run BOTH models on the given host with its real model names
        ref_provider = cand_provider = get_provider(host)
        ref_name = host_model_name(host, reference_id)
        cand_name = host_model_name(host, candidate_id)
    else:
        ref_provider = get_provider(ref_model.provider, drift=0.0)
        cand_provider = get_provider(cand_model.provider, drift=candidate_drift)
        ref_name, cand_name = reference_id, candidate_id

    scores: list[float] = []
    misses: list[dict] = []
    for p in prompts:
        ref = ref_provider.chat(ref_name, _to_openai(p))["choices"][0]["message"]["content"]
        cand = cand_provider.chat(cand_name, _to_openai(p))["choices"][0]["message"]["content"]
        s = judge(ref, cand)
        scores.append(s)
        if s < threshold:
            misses.append({"prompt": p[:80], "score": round(s, 3),
                           "ref": ref[:60], "cand": cand[:60]})

    n = len(scores)
    agreement = sum(scores) / n if n else 0.0
    pass_rate = sum(1 for s in scores if s >= threshold) / n if n else 0.0
    saving_per_1m = ref_model.blended() - cand_model.blended()

    if pass_rate >= 0.95:
        verdict = "recommend"
    elif pass_rate >= 0.80:
        verdict = "review"
    else:
        verdict = "reject"

    return ReplayResult(reference_id, candidate_id, n, round(agreement, 3),
                        round(pass_rate, 3), threshold, round(saving_per_1m, 3),
                        verdict, misses[:10])


def load_prompts(path: str) -> list[str]:
    with open(path) as fh:
        data = json.load(fh)
    return data["prompts"] if isinstance(data, dict) else list(data)
