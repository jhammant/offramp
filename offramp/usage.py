"""Load usage from live cloud metrics or a sample file — cloud-neutral.

Live readers are read-only. AWS is fully wired (CloudWatch). Vertex/Azure readers
are structured but EXPERIMENTAL — they need your GCP/Azure creds + config to run,
and metric names may need tweaking per project. Use `--dry-run --cloud gcp|azure`
to exercise the (identical) recommend/govern engine on sample data meanwhile.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone


@dataclass
class UsageRecord:
    model_id: str
    region: str
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    kind: str = "text"           # text | image | other
    cloud: str = "bedrock"       # bedrock | vertex | azure

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_SCAN_REGIONS = [
    "us-east-1", "us-east-2", "us-west-2",
    "eu-west-1", "eu-west-2", "eu-central-1",
    "ap-southeast-1", "ap-northeast-1",
]


CLOUD_ALIAS = {"aws": "bedrock", "gcp": "vertex", "azure": "azure",
               "bedrock": "bedrock", "vertex": "vertex", "microsoft": "azure"}


def load_sample(path: str, cloud: str | None = None) -> tuple[list[UsageRecord], int]:
    with open(path) as fh:
        data = json.load(fh)
    records = [UsageRecord(**r) for r in data["records"]]
    if cloud and cloud != "all":
        want = CLOUD_ALIAS.get(cloud, cloud)
        records = [r for r in records if r.cloud == want]
    return records, int(data.get("window_days", 30))


def load_live(cloud: str = "aws", regions: list[str] | None = None,
              days: int = 30) -> tuple[list[UsageRecord], int]:
    if cloud in ("aws", "bedrock"):
        return load_live_aws(regions=regions, days=days)
    if cloud in ("gcp", "vertex"):
        return load_live_vertex(days=days)
    if cloud in ("azure", "microsoft"):
        return load_live_azure(days=days)
    if cloud == "all":
        records: list[UsageRecord] = []
        recs, days = load_live_aws(regions=regions, days=days)
        records += recs
        for fn in (load_live_vertex, load_live_azure):
            try:
                more, _ = fn(days=days)
                records += more
            except SystemExit as e:
                print(f"  [skip] {e}")
        return records, days
    raise SystemExit(f"unknown cloud {cloud!r} (use aws|gcp|azure|all)")


# --- AWS Bedrock (fully wired) --------------------------------------------
def load_live_aws(regions: list[str] | None = None, days: int = 30):
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("Live AWS needs boto3 — pip install 'offramp[live]'") from exc

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    records: list[UsageRecord] = []
    for region in (regions or DEFAULT_SCAN_REGIONS):
        cw = boto3.client("cloudwatch", region_name=region)
        model_ids: set[str] = set()
        for page in cw.get_paginator("list_metrics").paginate(Namespace="AWS/Bedrock"):
            for metric in page.get("Metrics", []):
                for dim in metric.get("Dimensions", []):
                    if dim["Name"] == "ModelId":
                        model_ids.add(dim["Value"])
        for model_id in sorted(model_ids):
            it = _cw_sum(cw, "InputTokenCount", model_id, start, end)
            ot = _cw_sum(cw, "OutputTokenCount", model_id, start, end)
            calls = _cw_sum(cw, "Invocations", model_id, start, end)
            if it == 0 and ot == 0 and calls == 0:
                continue
            kind = "text" if (it or ot) else "image"
            records.append(UsageRecord(model_id, region, int(it), int(ot), int(calls),
                                       kind, cloud="bedrock"))
    return records, days


def _cw_sum(cw, metric_name, model_id, start, end) -> float:
    resp = cw.get_metric_statistics(
        Namespace="AWS/Bedrock", MetricName=metric_name,
        Dimensions=[{"Name": "ModelId", "Value": model_id}],
        StartTime=start, EndTime=end, Period=86400, Statistics=["Sum"])
    return sum(dp["Sum"] for dp in resp.get("Datapoints", []))


# --- Google Vertex (experimental; needs google-cloud-monitoring + project) --
def load_live_vertex(days: int = 30):  # pragma: no cover - needs GCP creds
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise SystemExit("Vertex live: set GOOGLE_CLOUD_PROJECT (+ ADC creds). "
                         "Meanwhile: offramp analyze --dry-run --cloud gcp")
    try:
        from google.cloud import monitoring_v3  # noqa: F401
    except ImportError as exc:
        raise SystemExit("Vertex live needs google-cloud-monitoring — "
                         "pip install google-cloud-monitoring") from exc
    # Structure only: query aiplatform.googleapis.com token_count metrics per
    # model, split input/output, over the window. Metric names vary by project;
    # verify against Cloud Monitoring before trusting numbers.
    raise SystemExit("Vertex live reader is experimental and unverified on this "
                     "project — use --dry-run --cloud gcp, or wire the metric query.")


# --- Microsoft Azure OpenAI (experimental; needs azure-monitor-query) -------
def load_live_azure(days: int = 30):  # pragma: no cover - needs Azure creds
    resource = os.environ.get("AZURE_OPENAI_RESOURCE_ID")
    if not resource:
        raise SystemExit("Azure live: set AZURE_OPENAI_RESOURCE_ID (+ az login). "
                         "Meanwhile: offramp analyze --dry-run --cloud azure")
    try:
        from azure.monitor.query import MetricsQueryClient  # noqa: F401
        from azure.identity import DefaultAzureCredential  # noqa: F401
    except ImportError as exc:
        raise SystemExit("Azure live needs azure-monitor-query azure-identity — "
                         "pip install azure-monitor-query azure-identity") from exc
    # Structure only: Azure Monitor metrics ProcessedPromptTokens / GeneratedTokens
    # on the Cognitive Services account, split by ModelDeploymentName.
    raise SystemExit("Azure live reader is experimental and unverified on this "
                     "resource — use --dry-run --cloud azure, or wire the query.")
