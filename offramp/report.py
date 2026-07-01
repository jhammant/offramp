"""Render the analysis as a plain-text CLI report."""
from __future__ import annotations

from . import prices
from .recommend import Rec
from .usage import UsageRecord

BAR = "=" * 66
DASH = "-" * 66


def _money(x: float) -> str:
    return f"${x:,.0f}" if x >= 100 else f"${x:,.2f}"


def render(records: list[UsageRecord], recs: list[Rec], totals: dict,
           window_days: int, source: str, ratio: float) -> str:
    out: list[str] = []
    out.append(BAR)
    out.append(f"  offramp — cloud AI spend analysis   ({source}, {window_days}d, {ratio:.0f}:1 in:out)")
    out.append(BAR)

    if not records:
        out.append("  No Bedrock usage found. Nothing to analyze.")
        out.append(BAR)
        return "\n".join(out)

    # Model mix, grouped by cloud (even-handed across AWS / Google / Microsoft)
    out.append("  USAGE")
    clouds = sorted({r.cloud for r in records}, key=lambda c: prices.CLOUD_LABEL.get(c, c))
    for cloud in clouds:
        out.append(f"   {prices.CLOUD_LABEL.get(cloud, cloud)}:")
        for r in sorted([x for x in records if x.cloud == cloud], key=lambda x: x.model_id):
            if r.kind == "image":
                out.append(f"     {r.model_id:<36} {r.calls:>10,} images  [{r.region}]")
            else:
                toks = (r.input_tokens + r.output_tokens) / 1e6
                out.append(f"     {r.model_id:<36} {toks:>9,.1f}M tok  [{r.region}]")
    out.append("")
    out.append(f"   Estimated cloud AI spend: {_money(totals['total_spend'])} / {window_days}d"
               f"   ({len(clouds)} cloud{'s' if len(clouds) != 1 else ''})")
    out.append(DASH)

    arb = [r for r in recs if r.kind == "arbitrage"]
    sub = [r for r in recs if r.kind == "substitution"]
    img = [r for r in recs if r.kind == "image"]

    out.append("  SAFE — same weights, cheaper host (auto-routable, no quality change)")
    if arb:
        for r in arb:
            out.append(f"   {r.model_id}")
            out.append(f"      {r.detail:<28} {_money(r.current)} -> {_money(r.new)}"
                       f"   save {_money(r.saving)} ({r.pct:.0f}%)")
        out.append(f"   => safe savings this window: {_money(totals['arbitrage_saving'])}")
    else:
        out.append("   (none — no open-weight Bedrock traffic with a cheaper host)")
    out.append(DASH)

    out.append("  ADVISORY — cheaper model, QUALITY BET (approve after replay-eval)")
    if sub:
        shown: dict[str, int] = {}
        for r in sub:
            shown[r.model_id] = shown.get(r.model_id, 0) + 1
            if shown[r.model_id] > 3:  # top 3 candidates per source model
                continue
            flag = {"high": "OK ", "medium": "~  ", "low": "!! "}.get(r.confidence, "   ")
            out.append(f"   [{flag}] {r.model_id} {r.detail}")
            out.append(f"          {_money(r.current)} -> {_money(r.new)}   save {_money(r.saving)}"
                       f" ({r.pct:.0f}%)   conf={r.confidence}")
        out.append(f"   => if best per model applied (advisory): up to {_money(totals['best_substitution'])}")
    else:
        out.append("   (none)")

    if img:
        out.append(DASH)
        out.append("  IMAGE MODELS — detected (per-image pricing; host arbitrage pending)")
        for r in img:
            out.append(f"   {r.model_id:<38} {_money(r.current)}   {r.note}")

    if totals.get("unmatched"):
        out.append(DASH)
        out.append("  UNMATCHED (not in price table — add to prices.py):")
        for mid in sorted(set(totals["unmatched"])):
            out.append(f"   - {mid}")

    out.append(BAR)
    out.append("  NOTE: capability scores are priors, not guarantees. 'Safe' rows are")
    out.append("  identical weights. 'Advisory' rows change behavior — validate before routing.")
    out.append(BAR)
    return "\n".join(out)
