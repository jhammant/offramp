"""Sanity checks for the recommender."""
from offramp.recommend import recommend
from offramp.usage import UsageRecord


def test_arbitrage_is_safe_and_cheaper():
    # Llama on Bedrock should get a same-weights arbitrage rec, high confidence.
    rec_list, totals = recommend([
        UsageRecord("meta.llama3-3-70b-instruct-v1:0", "us-west-2",
                    input_tokens=500_000_000, output_tokens=150_000_000, calls=300_000),
    ])
    arb = [r for r in rec_list if r.kind == "arbitrage"]
    assert arb, "expected an arbitrage recommendation for open-weight Llama"
    assert arb[0].new < arb[0].current
    assert arb[0].confidence == "high"
    assert totals["arbitrage_saving"] > 0


def test_claude_has_no_arbitrage_only_substitution():
    rec_list, _ = recommend([
        UsageRecord("anthropic.claude-opus-4-6-v1:0", "us-east-1",
                    input_tokens=120_000_000, output_tokens=40_000_000, calls=210_000),
    ])
    assert not [r for r in rec_list if r.kind == "arbitrage"], "Claude has no same-weight twin"
    subs = [r for r in rec_list if r.kind == "substitution"]
    assert subs, "expected substitution options for Claude Opus"
    # Opus -> Sonnet should be the highest-confidence downgrade.
    assert any("claude-sonnet" in r.detail and r.confidence in ("high", "medium") for r in subs)


def test_image_arbitrage_for_stability_models():
    # Stability weights are hostable elsewhere -> same-model arbitrage.
    rec_list, _ = recommend([
        UsageRecord("stability.sd3-5-large-v1:0", "us-west-2", calls=1000, kind="image"),
    ])
    arb = [r for r in rec_list if r.kind == "arbitrage"]
    assert arb and arb[0].new < arb[0].current and arb[0].confidence == "high"


def test_image_proprietary_has_no_arbitrage():
    # Nova/Titan are Amazon-only -> detected, no cheaper host.
    rec_list, _ = recommend([
        UsageRecord("amazon.nova-canvas-v1:0", "us-east-1", calls=1000, kind="image"),
    ])
    assert not [r for r in rec_list if r.kind == "arbitrage"]
    img = [r for r in rec_list if r.kind == "image"]
    assert img and img[0].saving == 0.0


def test_gemini_is_substitution_only():
    # Gemini is Google-only -> no same-weight arbitrage, only substitution.
    rec_list, _ = recommend([
        UsageRecord("gemini-2.5-pro", "us-central1", 200_000_000, 60_000_000, 180_000, cloud="vertex"),
    ])
    assert not [r for r in rec_list if r.kind == "arbitrage"], "Gemini has no cheaper twin"
    assert [r for r in rec_list if r.kind == "substitution"], "expected substitution options"


def test_gpt_on_azure_is_substitution_only():
    rec_list, _ = recommend([
        UsageRecord("gpt-4o", "eastus", 250_000_000, 80_000_000, 300_000, cloud="azure"),
    ])
    assert not [r for r in rec_list if r.kind == "arbitrage"], "GPT list price is the same everywhere"
    assert [r for r in rec_list if r.kind == "substitution"]


def test_open_weight_arbitrage_works_on_every_cloud():
    # Llama on Vertex and gpt-oss on Azure should each get same-weights arbitrage.
    for rec in [UsageRecord("publishers/meta/models/llama-3.3-70b", "us-central1",
                            150_000_000, 50_000_000, 90_000, cloud="vertex"),
                UsageRecord("gpt-oss-120b", "eastus",
                            300_000_000, 90_000_000, 200_000, cloud="azure")]:
        rec_list, _ = recommend([rec])
        arb = [r for r in rec_list if r.kind == "arbitrage"]
        assert arb and arb[0].new < arb[0].current, f"no arbitrage for {rec.model_id}"


def test_replay_agreement_tracks_capability_gap():
    # A near-capability swap should agree more than a far one (mock is monotonic).
    from offramp.replay import replay
    prompts = ["classify this billing message", "summarize the ticket"] * 4
    near = replay(prompts, "claude-opus-4.6", "claude-sonnet-5")   # gap 4
    far = replay(prompts, "claude-opus-4.6", "gpt-oss-120b")       # gap 8
    assert near.agreement >= far.agreement
