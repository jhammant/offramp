"""Phase 3 guardrails: decide what a recommendation is ALLOWED to become.

The policy is the safety layer between "here's a cheaper option" and "traffic is
now flowing there." Safe arbitrage can auto-apply; substitutions can only auto-
apply if a replay-eval cleared them; everything else is held for a human.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .recommend import Rec


@dataclass
class Policy:
    auto_apply_arbitrage: bool = True        # same-weights, no quality change
    auto_apply_substitution: bool = False    # only if replay verdict clears it
    min_replay_pass_rate: float = 0.95       # bar for auto-applying a substitution
    max_reroute_pct: float = 1.0             # cap fraction of spend rerouted at once
    min_saving: float = 1.0                  # ignore trivial recs (per window $)
    deny_models: list[str] = field(default_factory=list)   # never touch (substring)
    allow_only: list[str] = field(default_factory=list)    # if set, only these
    error_rollback_rate: float = 0.02        # auto-rollback if live error rate exceeds

    def _blocked(self, model_id: str) -> bool:
        mid = model_id.lower()
        if any(d.lower() in mid for d in self.deny_models):
            return True
        if self.allow_only and not any(a.lower() in mid for a in self.allow_only):
            return True
        return False


@dataclass
class Decision:
    action: str      # "auto" | "stage" | "hold"
    reason: str
    rec: Rec
    replay_verdict: str | None = None


def decide(rec: Rec, policy: Policy, replay_verdict: str | None = None) -> Decision:
    if rec.saving < policy.min_saving:
        return Decision("hold", f"saving < ${policy.min_saving:g} threshold", rec, replay_verdict)
    if policy._blocked(rec.model_id):
        return Decision("hold", "blocked by allow/deny policy", rec, replay_verdict)

    if rec.kind == "arbitrage":
        if policy.auto_apply_arbitrage:
            return Decision("auto", "same weights — no quality change", rec, replay_verdict)
        return Decision("stage", "arbitrage auto-apply disabled", rec, replay_verdict)

    if rec.kind == "substitution":
        if replay_verdict is None:
            return Decision("hold", "needs replay-eval before any routing", rec, replay_verdict)
        if replay_verdict == "reject":
            return Decision("hold", "replay-eval rejected (quality too low)", rec, replay_verdict)
        if (policy.auto_apply_substitution and replay_verdict == "recommend"):
            return Decision("auto", "replay-eval passed the auto bar", rec, replay_verdict)
        return Decision("stage", f"replay verdict '{replay_verdict}' — needs sign-off", rec, replay_verdict)

    return Decision("hold", "no action for this record", rec, replay_verdict)
