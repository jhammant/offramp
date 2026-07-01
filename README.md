# offramp

[![tests](https://github.com/jhammant/offramp/actions/workflows/ci.yml/badge.svg)](https://github.com/jhammant/offramp/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml)

**Analyze your cloud AI spend — AWS Bedrock, Google Vertex, Azure OpenAI — and recommend cheaper providers, before you route a single call.**

Every hyperscaler resells models at the vendor's list price. For **open-weight**
models (Llama, Mistral, gpt-oss) the *same weights* run cheaper on a dedicated
host; for **proprietary** frontier models (Claude, Nova, **Gemini**, **GPT**) there
is no cheaper twin — the only lever is substituting a cheaper model, a quality
bet. `offramp` treats all three clouds evenhandedly: it reads your real usage,
prices it, and ranks the savings, separating the **safe** (identical-weights) wins
from the **advisory** (quality-bet) ones. Routing comes later, only for what you approve.

> Same truth on every cloud: open weights = a free lunch; frontier = a quality bet.
> Analyze → replay-eval → govern. Analysis is 100% read-only.

## Install

```bash
pip install -e .          # analyzer + recommender (no deps)
pip install -e '.[live]'  # add boto3 for live AWS reads
#   Vertex live (experimental): pip install google-cloud-monitoring
#   Azure  live (experimental): pip install azure-monitor-query azure-identity
```

## Use

```bash
# 1. ANALYZE — what could you save? (sample workload spanning all 3 clouds)
offramp analyze --dry-run                 # all clouds, even-handed
offramp analyze --dry-run --cloud gcp     # or focus one: aws | gcp | azure
offramp analyze --live --cloud aws --regions us-east-1,us-west-2   # read-only

# 2. REPLAY-EVAL — prove a substitution on your prompts before trusting it
offramp replay claude-opus-4.6 deepseek-v3.1           # offline mock by default
#   OFFRAMP_LIVE_ROUTING=1 + a host key => real models + real agreement

# 3. OPTIMIZE — governed action plan (recommend + replay + policy)
offramp optimize --dry-run --audit offramp-audit.jsonl
offramp optimize --live --auto-substitutions --deny claude   # e.g. never touch Claude

offramp prices                                         # the price catalog
```

`--live --cloud aws` reads only the `AWS/Bedrock` CloudWatch namespace (token
counts + invocations per model). No inference, no writes, no cost.

## Clouds

| Cloud | Analyze (live) | Open-weight arbitrage | Frontier (substitution-only) |
|---|---|---|---|
| **AWS Bedrock** | ✅ CloudWatch | Llama, Mistral, gpt-oss | Claude, Nova |
| **Google Vertex** | ⚗️ experimental (Cloud Monitoring) | Llama (Model Garden) | Gemini |
| **Azure OpenAI** | ⚗️ experimental (Azure Monitor) | gpt-oss | GPT-5.x, GPT-4o |

The `recommend → replay-eval → govern` engine is identical across all three — only
the usage reader differs. AWS is wired live; Vertex/Azure readers need your creds
+ config (run `--dry-run --cloud gcp|azure` to exercise the engine meanwhile).

## What you get

- **Usage mix** — models, tokens/images, estimated spend, grouped by cloud.
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

- **Frontier models (Claude / Gemini / GPT) have no cheaper twin.** They live on
  one vendor; OpenRouter just passes the list price through (+~5.5% fee). So the
  only savings on them are substitution, caching, batch, or region-pinning — never
  "same model, cheaper host." offramp says this the same way for every cloud.
- `capability` scores are **priors from public benchmarks**, not guarantees. The
  whole point of replay-eval (Phase 2) is to replace them with measured numbers.
- The router (`offramp/router/`) is scaffolded but `shadow`/`route` are guarded so
  nothing reroutes production traffic or spends money without explicit wiring.

## Status

- **Multi-cloud:** AWS/Google/Azure in the price model + recommender + sample.
  AWS live reader wired; Vertex/Azure live readers experimental (need creds).
- **Phase 1 — analyze + recommend:** working (text + image, live + sample).
- **Phase 2 — replay-eval + router:** replay-eval works offline (mock provider);
  the Converse↔OpenAI translator + OpenAI-compatible adapters are wired but live
  routing/eval is gated behind `OFFRAMP_LIVE_ROUTING=1` + a host key so nothing
  bills or reroutes by default.
- **Phase 3 — governed optimize:** working (policy engine + action plan + audit).
  The plan is produced but not auto-executed — `shadow`/`route` stay guarded until
  you wire a target and flip them on.

Prices compiled July 2026 — refresh in `offramp/prices.py`. Apache-2.0.
