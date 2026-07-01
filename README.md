# offramp

**Analyze your AWS Bedrock spend and recommend cheaper providers — before you route a single call.**

Bedrock resells models at the vendor's list price. For **open-weight** models
(Llama, Mistral, gpt-oss) the *same weights* run cheaper elsewhere; for
**proprietary** models (Claude, Nova) the only lever is substituting a cheaper
model — a quality bet. `offramp` reads your real usage, prices it, and ranks the
savings, separating the **safe** (identical-weights) wins from the **advisory**
(quality-bet) ones. Routing comes later, only for what you approve.

> Analyze → recommend → (Phase 2) route. Phase 1 is 100% read-only.

## Install

```bash
pip install -e .          # analyzer + recommender (no deps)
pip install -e '.[live]'  # add boto3 for live CloudWatch reads
```

## Use

```bash
# 1. ANALYZE — what could you save? (sample workload, no AWS needed)
offramp analyze --dry-run
offramp analyze --live --regions us-east-1,us-west-2   # real account, read-only

# 2. REPLAY-EVAL — prove a substitution on your prompts before trusting it
offramp replay claude-opus-4.6 deepseek-v3.1           # offline mock by default
#   OFFRAMP_LIVE_ROUTING=1 + a host key => real models + real agreement

# 3. OPTIMIZE — governed action plan (recommend + replay + policy)
offramp optimize --dry-run --audit offramp-audit.jsonl
offramp optimize --live --auto-substitutions --deny claude   # e.g. never touch Claude

offramp prices                                         # the price catalog
```

`--live` reads only the `AWS/Bedrock` CloudWatch namespace (token counts +
invocations per model). No inference, no writes, no cost.

## What you get

- **Usage mix** — models, tokens/images, estimated Bedrock spend.
- **SAFE recs** — same weights on a cheaper host (text *and* Stability image models).
  Auto-routable, no quality change.
- **ADVISORY recs** — cheaper model with a capability-delta flag. *Quality bets.*
- **Replay-eval** — run your prompts through reference vs candidate, judge
  agreement, get a `recommend | review | reject` verdict + projected saving. Turns
  the capability *prior* into a measured number on your own traffic.
- **Governed optimize** — a policy engine sorts every rec into **apply now** (safe
  arbitrage), **stage** (subs that passed eval, awaiting sign-off), or **hold**
  (blocked / rejected), with an append-only audit ledger. Guardrails: allow/deny
  models, min-saving, reroute caps, auto-substitution gated on the replay verdict.

## Honesty notes

- **Claude/GPT have no cheaper twin.** OpenRouter passes through the vendor price
  (+~5.5% fee), so "move Claude off Bedrock to OpenRouter" saves nothing. The only
  real Claude savings are substitution, caching, batch, or region-pinning.
- `capability` scores are **priors from public benchmarks**, not guarantees. The
  whole point of replay-eval (Phase 2) is to replace them with measured numbers.
- The router (`offramp/router/`) is scaffolded but `shadow`/`route` are guarded so
  nothing reroutes production traffic or spends money without explicit wiring.

## Status

- **Phase 1 — analyze + recommend:** working (text + image, live + sample).
- **Phase 2 — replay-eval + router:** replay-eval works offline (mock provider);
  the Converse↔OpenAI translator + OpenAI-compatible adapters are wired but live
  routing/eval is gated behind `OFFRAMP_LIVE_ROUTING=1` + a host key so nothing
  bills or reroutes by default.
- **Phase 3 — governed optimize:** working (policy engine + action plan + audit).
  The plan is produced but not auto-executed — `shadow`/`route` stay guarded until
  you wire a target and flip them on.

Prices compiled July 2026 — refresh in `offramp/prices.py`. Apache-2.0.
