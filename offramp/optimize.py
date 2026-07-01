"""Phase 3: the governed optimize loop.

recommend -> (replay-eval substitutions) -> policy.decide -> action plan.
Produces a plan of {auto, stage, hold} plus an append-only audit ledger. In this
release it PLANS but does not flip live routing (the router's shadow/route modes
stay guarded), so it is safe to run continuously.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from . import prices
from .policy import Decision, Policy, decide
from .recommend import Rec, recommend
from .replay import load_prompts, replay
from .usage import UsageRecord


@dataclass
class Plan:
    auto: float = 0.0     # $ savings safe to apply now
    stage: float = 0.0    # $ savings awaiting sign-off
    hold: float = 0.0     # $ savings blocked/needs eval
    counts: dict = None


def _canonical_ref(model_id: str) -> str:
    m = prices.find_text_model(model_id)
    return m.id if m else model_id


def _candidate_from_detail(detail: str) -> str | None:
    # substitution detail: "-> {id} on {provider}"
    if "-> " in detail and " on " in detail:
        return detail.split("-> ", 1)[1].split(" on ", 1)[0]
    return None


def optimize(records: list[UsageRecord], policy: Policy, *, ratio: float = 3.0,
             prompts: list[str] | None = None,
             audit_path: str | None = None) -> tuple[list[Decision], Plan, dict]:
    recs, totals = recommend(records, ratio=ratio)
    decisions: list[Decision] = []

    # Cache replay verdicts per (reference, candidate) so we don't re-run.
    verdict_cache: dict[tuple[str, str], str] = {}

    for r in recs:
        verdict = None
        if r.kind == "substitution" and prompts:
            ref = _canonical_ref(r.model_id)
            cand = _candidate_from_detail(r.detail)
            if cand:
                key = (ref, cand)
                if key not in verdict_cache:
                    verdict_cache[key] = replay(prompts, ref, cand).verdict
                verdict = verdict_cache[key]
        decisions.append(decide(r, policy, verdict))

    plan = _summarize(decisions)
    if audit_path:
        _write_audit(audit_path, decisions)
    return decisions, plan, totals


def _summarize(decisions: list[Decision]) -> Plan:
    buckets = {"auto": 0.0, "stage": 0.0, "hold": 0.0}
    counts = {"auto": 0, "stage": 0, "hold": 0}
    seen_sub: set[str] = set()  # only count best substitution per source model
    for d in decisions:
        # avoid double-counting multiple substitution candidates per model
        if d.rec.kind == "substitution":
            if d.rec.model_id in seen_sub:
                continue
            seen_sub.add(d.rec.model_id)
        buckets[d.action] += d.rec.saving
        counts[d.action] += 1
    return Plan(buckets["auto"], buckets["stage"], buckets["hold"], counts)


def _write_audit(path: str, decisions: list[Decision]) -> None:
    with open(path, "a") as fh:
        for d in decisions:
            fh.write(json.dumps({
                "action": d.action, "reason": d.reason,
                "model": d.rec.model_id, "kind": d.rec.kind,
                "target": d.rec.detail, "saving": round(d.rec.saving, 2),
                "replay_verdict": d.replay_verdict,
            }) + "\n")


def render_plan(decisions: list[Decision], plan: Plan, totals: dict) -> str:
    BAR = "=" * 66
    out = [BAR, "  offramp optimize — governed action plan", BAR]
    out.append(f"  Estimated Bedrock spend: ${totals['total_spend']:,.2f} / window")
    out.append("-" * 66)

    def show(action, title):
        rows = [d for d in decisions if d.action == action]
        out.append(f"  {title}  ({len(rows)})")
        shown: set[str] = set()
        for d in sorted(rows, key=lambda x: x.rec.saving, reverse=True):
            if d.rec.kind == "substitution":
                if d.rec.model_id in shown:
                    continue
                shown.add(d.rec.model_id)
            v = f" [replay:{d.replay_verdict}]" if d.replay_verdict else ""
            out.append(f"    {d.rec.model_id} {d.rec.detail}")
            out.append(f"       save ${d.rec.saving:,.2f}  <- {d.reason}{v}")
        if not rows:
            out.append("    (none)")

    show("auto", "APPLY NOW — safe, within policy")
    out.append(f"  => auto-applicable savings: ${plan.auto:,.2f}")
    out.append("-" * 66)
    show("stage", "STAGE — needs your sign-off")
    out.append(f"  => staged (pending approval): ${plan.stage:,.2f}")
    out.append("-" * 66)
    show("hold", "HOLD — blocked / needs eval")
    out.append(BAR)
    out.append("  Router stays in observe/plan mode — nothing is rerouted until you")
    out.append("  enable shadow/route. Audit ledger written if --audit given.")
    out.append(BAR)
    return "\n".join(out)
