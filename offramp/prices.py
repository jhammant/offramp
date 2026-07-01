"""Price catalog + model matching — cloud-neutral.

Prices are $ per 1M tokens (input/output) for text models, and $ per image for
image models. Figures compiled from public pricing, July 2026 — a starting table;
edit here or refresh later. Rows marked `approx` are best-effort (open-weight
list prices on a hyperscaler move around); the proprietary frontier prices
(Claude/Gemini/GPT) and the cheaper-host prices are grounded.

Model of the world:
  * A hyperscaler CLOUD (bedrock/vertex/azure) is where usage runs today.
  * A HOST (groq/together/deepinfra/fal/stability) is a cheaper place to run the
    SAME open weights — that's arbitrage (no quality change).
  * A cloud's PROPRIETARY frontier model (Claude/Nova, Gemini, GPT) has no cheaper
    twin anywhere, so its only lever is SUBSTITUTION to a cheaper model (a bet).

`capability` is an ILLUSTRATIVE prior (0-100) used only to flag substitution risk;
replay-eval replaces it with a measured number on your own traffic.
"""
from __future__ import annotations

from dataclasses import dataclass

# Hyperscaler clouds (where spend originates). Everything else is a cheaper host.
CLOUDS = {"bedrock", "vertex", "azure"}
CLOUD_LABEL = {"bedrock": "AWS", "vertex": "Google", "azure": "Microsoft"}


@dataclass(frozen=True)
class TextModel:
    id: str            # canonical id; same weights across providers share it
    provider: str      # cloud (bedrock/vertex/azure) or host (groq/deepinfra/...)
    input: float       # $ / 1M input tokens
    output: float      # $ / 1M output tokens
    capability: int    # illustrative prior, 0-100
    weight_class: str  # "open" | "proprietary"
    family: str        # grouping label for proprietary tiers

    def blended(self, ratio: float = 3.0) -> float:
        return (ratio * self.input + self.output) / (ratio + 1)


@dataclass(frozen=True)
class ImageModel:
    id: str
    provider: str
    per_image: float
    quality: int
    weight_class: str
    family: str


# --- Text catalog ---------------------------------------------------------
_TEXT = [
    # === AWS Bedrock ===
    TextModel("claude-opus-4.6",   "bedrock", 5.0, 25.0, 92, "proprietary", "claude-opus"),
    TextModel("claude-sonnet-5",   "bedrock", 3.0, 15.0, 88, "proprietary", "claude-sonnet"),
    TextModel("claude-haiku-4.5",  "bedrock", 1.0,  5.0, 80, "proprietary", "claude-haiku"),
    TextModel("nova-pro",          "bedrock", 0.80, 3.20, 76, "proprietary", "nova-pro"),
    TextModel("nova-lite",         "bedrock", 0.06, 0.24, 64, "proprietary", "nova-lite"),
    TextModel("llama-3.3-70b",     "bedrock", 0.72, 0.72, 74, "open", "llama-3.3-70b"),
    TextModel("mistral-large-2",   "bedrock", 3.0,  9.0,  78, "open", "mistral-large-2"),
    TextModel("mistral-small",     "bedrock", 0.20, 0.60, 66, "open", "mistral-small"),
    # === Google Vertex ===
    TextModel("gemini-2.5-pro",    "vertex", 1.25, 10.0, 90, "proprietary", "gemini-2.5-pro"),
    TextModel("gemini-2.5-flash",  "vertex", 0.30,  2.50, 82, "proprietary", "gemini-2.5-flash"),
    TextModel("llama-3.3-70b",     "vertex", 0.75, 0.75, 74, "open", "llama-3.3-70b"),   # approx (Model Garden)
    # === Microsoft Azure (OpenAI) ===
    TextModel("gpt-5.2",           "azure", 1.75, 14.0, 91, "proprietary", "gpt-5.2"),
    TextModel("gpt-5",             "azure", 1.25, 10.0, 89, "proprietary", "gpt-5"),
    TextModel("gpt-5-nano",        "azure", 0.05,  0.40, 72, "proprietary", "gpt-5-nano"),
    TextModel("gpt-4o",            "azure", 2.50, 10.0, 80, "proprietary", "gpt-4o"),
    TextModel("gpt-oss-120b",      "azure", 0.30,  1.20, 84, "open", "gpt-oss-120b"),     # approx
    # === Cheaper hosts (same open weights) — arbitrage / substitution targets ===
    TextModel("llama-3.3-70b",     "deepinfra", 0.23, 0.40, 74, "open", "llama-3.3-70b"),
    TextModel("llama-3.3-70b",     "groq",      0.59, 0.79, 74, "open", "llama-3.3-70b"),
    TextModel("llama-3.3-70b",     "together",  0.88, 0.88, 74, "open", "llama-3.3-70b"),
    TextModel("gpt-oss-120b",      "groq",      0.15, 0.60, 84, "open", "gpt-oss-120b"),
    TextModel("deepseek-v3.1",     "deepinfra", 0.27, 1.10, 85, "open", "deepseek-v3.1"),
    TextModel("deepseek-v3.1",     "together",  0.60, 1.70, 85, "open", "deepseek-v3.1"),
]
TEXT_ROWS = _TEXT

# Canonical view by id (any cloud row preferred) — for replay reference lookups.
SOURCE: dict[str, TextModel] = {}
for _m in _TEXT:
    cur = SOURCE.get(_m.id)
    if cur is None or (_m.provider in CLOUDS and cur.provider not in CLOUDS):
        SOURCE[_m.id] = _m


def alternatives(canonical_id: str) -> list[TextModel]:
    """Same weights on a cheaper HOST (not another hyperscaler), cheapest first."""
    alts = [m for m in _TEXT if m.id == canonical_id and m.provider not in CLOUDS]
    return sorted(alts, key=lambda m: m.blended())


def cheapest_alt(canonical_id: str) -> TextModel | None:
    alts = alternatives(canonical_id)
    return alts[0] if alts else None


def source_row(canonical_id: str, cloud: str | None) -> TextModel | None:
    """The priced row for a model as run on a given cloud (else any cloud row)."""
    rows = [m for m in _TEXT if m.id == canonical_id]
    if not rows:
        return None
    for m in rows:
        if m.provider == cloud:
            return m
    for m in rows:
        if m.provider in CLOUDS:
            return m
    return sorted(rows, key=lambda m: m.blended())[0]


def target(canonical_id: str) -> TextModel:
    """Cheapest row for a canonical id (used as a substitution target)."""
    rows = [m for m in _TEXT if m.id == canonical_id]
    return sorted(rows, key=lambda m: m.blended())[0]


# Substitution ladder: source canonical id -> ordered cheaper candidates.
LADDER: dict[str, list[str]] = {
    # AWS
    "claude-opus-4.6": ["claude-sonnet-5", "claude-haiku-4.5", "deepseek-v3.1", "gpt-oss-120b"],
    "claude-sonnet-5": ["claude-haiku-4.5", "deepseek-v3.1", "gpt-oss-120b"],
    "mistral-large-2": ["deepseek-v3.1", "gpt-oss-120b", "mistral-small"],
    "nova-pro":        ["nova-lite", "gpt-oss-120b"],
    # Google
    "gemini-2.5-pro":   ["gemini-2.5-flash", "deepseek-v3.1", "gpt-oss-120b"],
    "gemini-2.5-flash": ["deepseek-v3.1", "gpt-oss-120b"],
    # Microsoft
    "gpt-5.2": ["gpt-5", "gpt-5-nano", "deepseek-v3.1", "gpt-oss-120b"],
    "gpt-5":   ["gpt-5-nano", "deepseek-v3.1", "gpt-oss-120b"],
    "gpt-4o":  ["gpt-5-nano", "deepseek-v3.1", "gpt-oss-120b"],
}

# Substring rules: live ModelId -> canonical id. MORE SPECIFIC FIRST (gpt-5-nano
# and gpt-5.2 must precede gpt-5; gpt-oss precedes gpt).
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
    ("gemini-2.5-pro", "gemini-2.5-pro"),
    ("gemini-2.5-flash", "gemini-2.5-flash"),
    ("gpt-oss-120b", "gpt-oss-120b"),
    ("gpt-5-nano", "gpt-5-nano"),
    ("gpt-5.2", "gpt-5.2"),
    ("gpt-4o", "gpt-4o"),
    ("gpt-5", "gpt-5"),
    ("deepseek-v3", "deepseek-v3.1"),
]


# --- Image catalog (AWS Bedrock only for now) ------------------------------
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
SOURCE_IMAGE: dict[str, ImageModel] = {}
for _im in _IMAGE:
    cur = SOURCE_IMAGE.get(_im.family)
    if cur is None or (_im.provider == "bedrock" and cur.provider != "bedrock"):
        SOURCE_IMAGE[_im.family] = _im


def image_alternatives(family: str) -> list[ImageModel]:
    alts = [m for m in _IMAGE if m.family == family and m.provider not in CLOUDS]
    return sorted(alts, key=lambda m: m.per_image)


def image_cheapest_alt(family: str) -> ImageModel | None:
    alts = image_alternatives(family)
    return alts[0] if alts else None


def _match(model_id: str, rules) -> str | None:
    mid = model_id.lower()
    for sub, canon in rules:
        if sub in mid:
            return canon
    return None


def find_text_model(model_id: str, cloud: str | None = None) -> TextModel | None:
    canon = _match(model_id, _TEXT_MATCH)
    return source_row(canon, cloud) if canon else None


def find_image_model(model_id: str) -> ImageModel | None:
    canon = _match(model_id, _IMAGE_MATCH)
    return SOURCE_IMAGE[canon] if canon else None
