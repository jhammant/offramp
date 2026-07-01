"""Price catalog + model matching.

Prices are $ per 1M tokens (input/output) for text models, and $ per image for
image models. Figures compiled from public pricing, July 2026 — treat as a
starting table, refresh with `offramp prices --refresh` (Phase 2) or edit here.

`capability` is an ILLUSTRATIVE prior from public benchmark aggregates (0-100),
used only to flag quality risk on substitutions. It is NOT a guarantee — the
whole point of the Phase-2 replay-eval is to replace it with measured agreement
on your own traffic.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextModel:
    id: str            # canonical id used by the ladder
    provider: str      # bedrock | groq | deepinfra | together
    input: float       # $ / 1M input tokens
    output: float      # $ / 1M output tokens
    capability: int    # illustrative prior, 0-100
    weight_class: str  # "open" | "proprietary"
    family: str        # same weights across providers share a family

    def blended(self, ratio: float = 3.0) -> float:
        """Blended $/1M at a given input:output ratio (default 3:1, input-heavy)."""
        return (ratio * self.input + self.output) / (ratio + 1)


@dataclass(frozen=True)
class ImageModel:
    id: str
    provider: str
    per_image: float   # $ / image at a representative standard size/step count
    quality: int
    weight_class: str  # "open" (hostable elsewhere) | "proprietary" (Amazon-only)
    family: str


# --- Text catalog ---------------------------------------------------------
# Bedrock-hosted (source) + cheaper hosts (arbitrage / substitution targets).
_TEXT = [
    # Anthropic (proprietary — no same-weight arbitrage, only substitution).
    TextModel("claude-opus-4.6",   "bedrock", 5.0, 25.0, 92, "proprietary", "claude-opus"),
    TextModel("claude-sonnet-5",   "bedrock", 3.0, 15.0, 88, "proprietary", "claude-sonnet"),  # std; launch promo 2/10
    TextModel("claude-haiku-4.5",  "bedrock", 1.0,  5.0, 80, "proprietary", "claude-haiku"),
    # Amazon Nova (proprietary, Amazon-only).
    TextModel("nova-pro",          "bedrock", 0.80, 3.20, 76, "proprietary", "nova-pro"),
    TextModel("nova-lite",         "bedrock", 0.06, 0.24, 64, "proprietary", "nova-lite"),
    # Open-weight on Bedrock (source models — arbitrage candidates).
    TextModel("llama-3.3-70b",     "bedrock",   0.72, 0.72, 74, "open", "llama-3.3-70b"),
    TextModel("mistral-large-2",   "bedrock",   3.0,  9.0,  78, "open", "mistral-large-2"),
    TextModel("mistral-small",     "bedrock",   0.20, 0.60, 66, "open", "mistral-small"),
    # Same weights on cheaper hosts (arbitrage targets).
    TextModel("llama-3.3-70b",     "deepinfra", 0.23, 0.40, 74, "open", "llama-3.3-70b"),
    TextModel("llama-3.3-70b",     "groq",      0.59, 0.79, 74, "open", "llama-3.3-70b"),
    TextModel("llama-3.3-70b",     "together",  0.88, 0.88, 74, "open", "llama-3.3-70b"),
    # Frontier open-weight (substitution targets).
    TextModel("gpt-oss-120b",      "groq",      0.15, 0.60, 84, "open", "gpt-oss-120b"),
    TextModel("deepseek-v3.1",     "deepinfra", 0.27, 1.10, 85, "open", "deepseek-v3.1"),
    TextModel("deepseek-v3.1",     "together",  0.60, 1.70, 85, "open", "deepseek-v3.1"),
]

# All (id, provider) rows, plus a canonical-source view for the ladder.
TEXT_ROWS = _TEXT
# Canonical source model per id = the Bedrock row if present, else cheapest.
SOURCE: dict[str, TextModel] = {}
for _m in _TEXT:
    cur = SOURCE.get(_m.id)
    if cur is None or (_m.provider == "bedrock" and cur.provider != "bedrock"):
        SOURCE[_m.id] = _m


def alternatives(family: str) -> list[TextModel]:
    """Same-weight rows hosted somewhere other than Bedrock, cheapest first."""
    alts = [m for m in _TEXT if m.family == family and m.provider != "bedrock"]
    return sorted(alts, key=lambda m: m.blended())


def cheapest_alt(family: str) -> TextModel | None:
    alts = alternatives(family)
    return alts[0] if alts else None


def target(canonical_id: str) -> TextModel:
    """Cheapest row for a canonical model id (used as a substitution target)."""
    rows = [m for m in _TEXT if m.id == canonical_id]
    return sorted(rows, key=lambda m: m.blended())[0]


# Substitution ladder: source canonical id -> ordered downgrade candidates.
LADDER: dict[str, list[str]] = {
    "claude-opus-4.6": ["claude-sonnet-5", "claude-haiku-4.5", "deepseek-v3.1", "gpt-oss-120b"],
    "claude-sonnet-5": ["claude-haiku-4.5", "deepseek-v3.1", "gpt-oss-120b"],
    "mistral-large-2": ["deepseek-v3.1", "gpt-oss-120b", "mistral-small"],
    "nova-pro":        ["nova-lite", "gpt-oss-120b"],
}

# Substring rules to map a live Bedrock ModelId -> canonical text id.
_TEXT_MATCH = [
    ("claude-opus", "claude-opus-4.6"),
    ("claude-sonnet", "claude-sonnet-5"),
    ("claude-haiku", "claude-haiku-4.5"),
    ("nova-pro", "nova-pro"),
    ("nova-lite", "nova-lite"),
    ("llama3-3-70b", "llama-3.3-70b"),
    ("llama-3.3-70b", "llama-3.3-70b"),
    ("mistral-large", "mistral-large-2"),
    ("mistral-small", "mistral-small"),
    ("gpt-oss-120b", "gpt-oss-120b"),
    ("deepseek-v3", "deepseek-v3.1"),
]


# --- Image catalog --------------------------------------------------------
# Bedrock per-image (source) + same-model cheaper hosts (arbitrage targets).
# Nova/Titan are Amazon-only (proprietary — no arbitrage, like Claude for text);
# Stability models are open weights and hostable on Stability-direct / Fal / etc.
_IMAGE = [
    ImageModel("nova-canvas",        "bedrock",   0.04,  78, "proprietary", "nova-canvas"),
    ImageModel("titan-image-v2",     "bedrock",   0.01,  70, "proprietary", "titan-image"),
    ImageModel("sd3.5-large",        "bedrock",   0.08,  85, "open", "sd3.5-large"),
    ImageModel("sd3.5-large",        "fal",       0.065, 85, "open", "sd3.5-large"),
    ImageModel("sd3.5-large",        "stability", 0.065, 85, "open", "sd3.5-large"),
    ImageModel("stable-image-core",  "bedrock",   0.04,  80, "open", "stable-image-core"),
    ImageModel("stable-image-core",  "stability", 0.03,  80, "open", "stable-image-core"),
    ImageModel("stable-image-ultra", "bedrock",   0.14,  88, "open", "stable-image-ultra"),
    ImageModel("stable-image-ultra", "stability", 0.08,  88, "open", "stable-image-ultra"),
]
IMAGE_ROWS = _IMAGE
_IMAGE_MATCH = [
    ("nova-canvas", "nova-canvas"),
    ("titan-image", "titan-image"),
    ("sd3-5-large", "sd3.5-large"),
    ("stable-image-core", "stable-image-core"),
    ("stable-image-ultra", "stable-image-ultra"),
]
# Bedrock source row per family (for matching live usage).
SOURCE_IMAGE: dict[str, ImageModel] = {}
for _im in _IMAGE:
    cur = SOURCE_IMAGE.get(_im.family)
    if cur is None or (_im.provider == "bedrock" and cur.provider != "bedrock"):
        SOURCE_IMAGE[_im.family] = _im


def image_alternatives(family: str) -> list[ImageModel]:
    alts = [m for m in _IMAGE if m.family == family and m.provider != "bedrock"]
    return sorted(alts, key=lambda m: m.per_image)


def image_cheapest_alt(family: str) -> ImageModel | None:
    alts = image_alternatives(family)
    return alts[0] if alts else None


def find_text_model(model_id: str) -> TextModel | None:
    mid = model_id.lower()
    for sub, canon in _TEXT_MATCH:
        if sub in mid:
            return SOURCE[canon]
    return None


def find_image_model(model_id: str) -> ImageModel | None:
    mid = model_id.lower()
    for sub, family in _IMAGE_MATCH:
        if sub in mid:
            return SOURCE_IMAGE[family]
    return None
