"""Phase 2 (scaffold): the drop-in router.

`offramp.client("bedrock-runtime")` mimics the boto3 Bedrock client so existing
code changes by one line. Three modes:

    observe  — pass everything through to real Bedrock, record calls to a ledger
               (this is what powers request-level analysis; zero behavior change)
    shadow   — pass through to Bedrock AND mirror to a cheaper target, compare
    route    — send the approved (safe) traffic to the cheaper target

Only `observe` is wired here. `shadow`/`route` deliberately raise until the
translate + provider adapters (and your explicit approval) are in place, so this
never silently reroutes production traffic or spends money.
"""
from .shim import client

__all__ = ["client"]
