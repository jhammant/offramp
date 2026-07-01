"""Turn usage into ranked savings recommendations.

Two kinds:
  * arbitrage    — same weights, cheaper host. No quality change. Safe to auto-route.
  * substitution — a different (cheaper) model. A quality BET. Advisory only; the
                   `capability` delta flags risk and Phase-2 replay-eval measures it.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import prices
from .usage import UsageRecord


@dataclass
class Rec:
    kind: str            # arbitrage | substitution | image | flag
    model_id: str
    detail: str          # target description
    current: float       # $ / window
    new: float           # $ / window
    saving: float
    pct: float
    confidence: str      # high | medium | low | n/a
    note: str = ""


def _text_cost(m: prices.TextModel, it: int, ot: int) -> float:
    return it / 1e6 * m.input + ot / 1e6 * m.output


def _confidence(cap_from: int, cap_to: int) -> str:
    gap = cap_from - cap_to
    if gap <= 3:
        return "high"
    if gap <= 8:
        return "medium"
    return "low"


def recommend(records: list[UsageRecord], ratio: float = 3.0) -> tuple[list[Rec], dict]:
    recs: list[Rec] = []
    total_spend = 0.0
    arbitrage_saving = 0.0
    unmatched: list[str] = []

    for r in records:
        if r.kind == "image":
            im = prices.find_image_model(r.model_id)
            if not im:
                unmatched.append(r.model_id)
                continue
            spend = r.calls * im.per_image
            total_spend += spend
            alt = prices.image_cheapest_alt(im.family) if im.weight_class == "open" else None
            if alt and alt.per_image < im.per_image:
                new = r.calls * alt.per_image
                saving = spend - new
                arbitrage_saving += saving
                recs.append(Rec("arbitrage", r.model_id,
                                f"same model on {alt.provider}",
                                spend, new, saving, saving / spend * 100 if spend else 0,
                                "high", "identical image model — no quality change"))
            else:
                why = "Amazon-only — no cheaper host" if im.weight_class == "proprietary" else "already cheapest"
                recs.append(Rec("image", r.model_id,
                                f"{r.calls} imgs @ ${im.per_image:.3f}", spend, spend,
                                0.0, 0.0, "n/a", why))
            continue

        m = prices.find_text_model(r.model_id, r.cloud)
        if not m:
            unmatched.append(r.model_id)
            continue

        current = _text_cost(m, r.input_tokens, r.output_tokens)
        total_spend += current

        # --- arbitrage: same weights, cheaper host --------------------------
        if m.weight_class == "open":
            alt = prices.cheapest_alt(m.id)
            if alt and _text_cost(alt, r.input_tokens, r.output_tokens) < current:
                new = _text_cost(alt, r.input_tokens, r.output_tokens)
                saving = current - new
                arbitrage_saving += saving
                recs.append(Rec("arbitrage", r.model_id,
                                f"same weights on {alt.provider}",
                                current, new, saving, saving / current * 100,
                                "high", "identical model — no quality change"))

        # --- substitution: cheaper model, quality bet -----------------------
        for cand_id in prices.LADDER.get(m.id, []):
            t = prices.target(cand_id)
            new = _text_cost(t, r.input_tokens, r.output_tokens)
            if new >= current:
                continue
            saving = current - new
            recs.append(Rec("substitution", r.model_id,
                            f"-> {t.id} on {t.provider}",
                            current, new, saving, saving / current * 100,
                            _confidence(m.capability, t.capability),
                            f"capability {m.capability}->{t.capability} (prior) — validate with replay-eval"))

    recs.sort(key=lambda x: x.saving, reverse=True)
    totals = {
        "total_spend": total_spend,
        "arbitrage_saving": arbitrage_saving,          # safe, stackable
        "best_substitution": _best_per_model(recs),    # advisory, pick one per model
        "unmatched": unmatched,
    }
    return recs, totals


def _best_per_model(recs: list[Rec]) -> float:
    best: dict[str, float] = {}
    for r in recs:
        if r.kind == "substitution":
            best[r.model_id] = max(best.get(r.model_id, 0.0), r.saving)
    return sum(best.values())
