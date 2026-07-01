"""Load Bedrock usage — from live CloudWatch metrics or a sample file.

Live mode is read-only: it reads the `AWS/Bedrock` namespace (InputTokenCount,
OutputTokenCount, Invocations) per ModelId. No writes, no inference, no cost.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone


@dataclass
class UsageRecord:
    model_id: str
    region: str
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    kind: str = "text"  # text | image | other

    def to_dict(self) -> dict:
        return asdict(self)


# Regions worth scanning for Bedrock metrics when none are specified.
DEFAULT_SCAN_REGIONS = [
    "us-east-1", "us-east-2", "us-west-2",
    "eu-west-1", "eu-west-2", "eu-central-1",
    "ap-southeast-1", "ap-northeast-1",
]


def load_sample(path: str) -> tuple[list[UsageRecord], int]:
    with open(path) as fh:
        data = json.load(fh)
    records = [UsageRecord(**r) for r in data["records"]]
    return records, int(data.get("window_days", 30))


def load_live(regions: list[str] | None = None, days: int = 30) -> tuple[list[UsageRecord], int]:
    """Pull per-model token/invocation sums from CloudWatch. Requires boto3 (`pip install offramp[live]`)."""
    try:
        import boto3  # lazy: dry-run needs no dependencies
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("Live mode needs boto3 — install with: pip install 'offramp[live]'") from exc

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    scan = regions or DEFAULT_SCAN_REGIONS
    records: list[UsageRecord] = []

    for region in scan:
        cw = boto3.client("cloudwatch", region_name=region)
        # Discover model ids that have any Bedrock metric in this region.
        model_ids: set[str] = set()
        paginator = cw.get_paginator("list_metrics")
        for page in paginator.paginate(Namespace="AWS/Bedrock"):
            for metric in page.get("Metrics", []):
                for dim in metric.get("Dimensions", []):
                    if dim["Name"] == "ModelId":
                        model_ids.add(dim["Value"])
        if not model_ids:
            continue

        for model_id in sorted(model_ids):
            it = _sum(cw, "InputTokenCount", model_id, start, end)
            ot = _sum(cw, "OutputTokenCount", model_id, start, end)
            calls = _sum(cw, "Invocations", model_id, start, end)
            if it == 0 and ot == 0 and calls == 0:
                continue
            kind = "text" if (it or ot) else "image"  # image models emit no token metrics
            records.append(UsageRecord(model_id, region, int(it), int(ot), int(calls), kind))

    return records, days


def _sum(cw, metric_name: str, model_id: str, start, end) -> float:
    resp = cw.get_metric_statistics(
        Namespace="AWS/Bedrock",
        MetricName=metric_name,
        Dimensions=[{"Name": "ModelId", "Value": model_id}],
        StartTime=start,
        EndTime=end,
        Period=86400,
        Statistics=["Sum"],
    )
    return sum(dp["Sum"] for dp in resp.get("Datapoints", []))
