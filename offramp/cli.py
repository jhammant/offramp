"""offramp CLI — `offramp analyze` (read-only) and `offramp prices`."""
from __future__ import annotations

import argparse
import os
import sys

from . import __version__, prices
from .optimize import optimize, render_plan
from .policy import Policy
from .recommend import recommend
from .replay import load_prompts, replay
from .report import render
from .usage import load_live, load_sample

_HERE = os.path.dirname(__file__)
SAMPLE = os.path.join(_HERE, "..", "sample", "usage_sample.json")
PROMPTS = os.path.join(_HERE, "..", "sample", "replay_prompts.json")


def _load_usage(args):
    cloud = getattr(args, "cloud", "all")
    if args.live:
        regions = args.regions.split(",") if args.regions else None
        records, window = load_live(cloud=cloud, regions=regions, days=args.days)
        return records, window, f"live: {cloud}"
    path = args.sample or SAMPLE
    records, window = load_sample(path, cloud=cloud)
    return records, window, f"sample ({cloud})"


def cmd_analyze(args: argparse.Namespace) -> int:
    records, window, source = _load_usage(args)
    sov = None if getattr(args, "sovereign", "any") == "any" else args.sovereign
    recs, totals = recommend(records, ratio=args.ratio, sovereign=sov)
    print(render(records, recs, totals, window, source, args.ratio))
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    prompts = load_prompts(args.prompts or PROMPTS)
    judge, host = None, None
    if args.live:
        os.environ["OFFRAMP_LIVE_ROUTING"] = "1"
        host = args.host
        if args.limit:
            prompts = prompts[:args.limit]
        from .replay import groq_judge, lexical_judge
        judge = lexical_judge if args.lexical else groq_judge
    kw = {"threshold": args.threshold, "host": host}
    if judge is not None:
        kw["judge"] = judge
    res = replay(prompts, args.reference, args.candidate, **kw)
    live = os.environ.get("OFFRAMP_LIVE_ROUTING") == "1"
    tag = f"LIVE on {host}, {'lexical' if args.lexical else 'LLM'}-judge" if live else "MOCK"
    print(f"replay-eval  {res.reference} -> {res.candidate}   ({tag}, n={res.n})")
    print(f"  agreement={res.agreement}  pass_rate={res.pass_rate} (>= {res.threshold})")
    print(f"  projected saving: ${res.projected_saving_per_1m:.2f}/1M blended")
    print(f"  VERDICT: {res.verdict.upper()}")
    if res.misses:
        print(f"  {len(res.misses)} below threshold, e.g.: {res.misses[0]['prompt']!r} (score {res.misses[0]['score']})")
    if not live:
        print("  [mock provider — set OFFRAMP_LIVE_ROUTING=1 + host key for a real eval]")
    return 0


def cmd_optimize(args: argparse.Namespace) -> int:
    records, window, source = _load_usage(args)
    policy = Policy(
        auto_apply_substitution=args.auto_substitutions,
        min_saving=args.min_saving,
        deny_models=args.deny.split(",") if args.deny else [],
    )
    prompts = None if args.no_replay else load_prompts(args.prompts or PROMPTS)
    decisions, plan, totals = optimize(records, policy, ratio=args.ratio,
                                       prompts=prompts, audit_path=args.audit)
    print(render_plan(decisions, plan, totals))
    if args.audit:
        print(f"  audit ledger appended: {args.audit}")
    return 0


def cmd_prices(args: argparse.Namespace) -> int:
    print(f"{'model':<20}{'provider':<12}{'in $/M':>9}{'out $/M':>9}{'blend':>8}{'cap':>5}  class")
    for m in sorted(prices.TEXT_ROWS, key=lambda x: (x.family, x.blended())):
        print(f"{m.id:<20}{m.provider:<12}{m.input:>9.2f}{m.output:>9.2f}"
              f"{m.blended():>8.2f}{m.capability:>5}  {m.weight_class}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="offramp", description="Analyze Bedrock spend; recommend cheaper providers.")
    p.add_argument("--version", action="version", version=f"offramp {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_usage_flags(parser):
        g = parser.add_mutually_exclusive_group()
        g.add_argument("--live", action="store_true", help="read real usage from the cloud (read-only)")
        g.add_argument("--sample", metavar="PATH", help="use a sample usage JSON file")
        g.add_argument("--dry-run", dest="sample", action="store_const", const=SAMPLE,
                       help="use the bundled sample workload")
        parser.add_argument("--cloud", choices=["aws", "gcp", "azure", "all"], default="all",
                            help="which cloud(s) to analyze (default: all)")
        parser.add_argument("--sovereign", choices=["any", "eu"], default="any",
                            help="prefer EU-sovereign hosts for arbitrage (data residency)")
        parser.add_argument("--regions", help="comma-separated regions for --live (AWS)")
        parser.add_argument("--days", type=int, default=30, help="lookback window (default 30)")
        parser.add_argument("--ratio", type=float, default=3.0, help="input:output token ratio")

    a = sub.add_parser("analyze", help="analyze usage and print savings recommendations")
    add_usage_flags(a)
    a.set_defaults(func=cmd_analyze)

    rp = sub.add_parser("replay", help="replay-eval a substitution on sample prompts")
    rp.add_argument("reference", help="reference model id, e.g. llama-3.3-70b")
    rp.add_argument("candidate", help="cheaper candidate id, e.g. gpt-oss-120b")
    rp.add_argument("--prompts", help="prompts JSON (default: bundled sample)")
    rp.add_argument("--threshold", type=float, default=0.8, help="per-prompt pass bar (0..1)")
    rp.add_argument("--live", action="store_true", help="call real models (needs host API key)")
    rp.add_argument("--host", default="groq", help="host for --live (default groq)")
    rp.add_argument("--limit", type=int, default=6, help="prompts to eval when --live")
    rp.add_argument("--lexical", action="store_true", help="use lexical judge instead of LLM-judge")
    rp.set_defaults(func=cmd_replay)

    op = sub.add_parser("optimize", help="governed action plan (recommend + replay + policy)")
    add_usage_flags(op)
    op.add_argument("--auto-substitutions", action="store_true",
                    help="allow auto-applying substitutions that pass replay-eval")
    op.add_argument("--min-saving", type=float, default=1.0, help="ignore recs below $ (per window)")
    op.add_argument("--deny", help="comma-separated model substrings to never touch")
    op.add_argument("--no-replay", action="store_true", help="skip replay-eval (substitutions -> hold)")
    op.add_argument("--prompts", help="prompts JSON for replay (default: bundled sample)")
    op.add_argument("--audit", help="append decisions to this JSONL audit ledger")
    op.set_defaults(func=cmd_optimize)

    pr = sub.add_parser("prices", help="print the price catalog")
    pr.set_defaults(func=cmd_prices)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
