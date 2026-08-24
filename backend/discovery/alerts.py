"""Intersection alerts: deterministic governance signals over the object log.

The OCPM literature is explicit that flattening multi-object processes onto a
single case *manufactures* anomalies (deficiency/convergence/divergence), and
that the first generation of trustworthy signals is transparent rules, not
models. This module evaluates three such rules over ``build_object_log``
output:

- ``shared_object_across_cases`` (warn): a non-case/non-actor object touching
  several cases — the canonical divergence/bottleneck signal.
- ``large_amount_observed`` (critical): an amount object at or above a
  configured dollar threshold — auditable point anomaly.
- ``hub_actor`` (info): one actor concentrating many events.

Thresholds come from an optional policy file (``AUTOPILOT_ALERTS_POLICY``,
same pattern as the tool-governance allowlist); absent file = defaults. No
LLM anywhere: identical workspace in, identical alerts out.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

POLICY_ENV = "AUTOPILOT_ALERTS_POLICY"

DEFAULTS: dict[str, dict[str, Any]] = {
    "shared_object_across_cases": {"min_cases": 2, "exclude_types": ["case", "actor"]},
    "large_amount_observed": {"min_dollars": 10_000},
    "hub_actor": {"min_events": 5},
}

_AMOUNT_RE = re.compile(r"^\$(\d+(?:\.\d+)?)$")


def _load_policy() -> dict[str, dict[str, Any]]:
    raw_path = os.getenv(POLICY_ENV, "").strip()
    if not raw_path:
        return DEFAULTS
    path = os.path.expanduser(raw_path)
    if not os.path.exists(path):
        return DEFAULTS
    try:
        with open(path, encoding="utf-8") as handle:
            overrides = json.load(handle)
        merged = {rule: dict(params) for rule, params in DEFAULTS.items()}
        for rule, params in overrides.get("rules", {}).items():
            merged.setdefault(rule, {}).update(params or {})
        return merged
    except (ValueError, OSError):
        return DEFAULTS


def evaluate_alerts(log: dict[str, Any],
                    policy: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Run every rule; returns severity-ordered alerts with evidence ids."""
    config = policy or _load_policy()
    # Index: object -> touching event ids + distinct case ids + type.
    index: dict[str, dict[str, Any]] = {}
    for event in log["events"]:
        case_ids = {rel["objectId"] for rel in event["relationships"]
                    if rel["qualifier"] == "case"}
        for rel in event["relationships"]:
            entry = index.setdefault(rel["objectId"], {
                "type": rel["qualifier"], "event_ids": [], "case_ids": set(),
                "values": [],
            })
            entry["event_ids"].append(event["id"])
            entry["case_ids"].update(case_ids)

    alerts: list[dict[str, Any]] = []

    shared_cfg = config.get("shared_object_across_cases", {})
    exclude = set(shared_cfg.get("exclude_types", ["case", "actor"]))
    min_cases = int(shared_cfg.get("min_cases", 2))
    for object_id, entry in sorted(index.items()):
        if entry["type"] in exclude:
            continue
        if len(entry["case_ids"]) >= min_cases:
            alerts.append(_alert(
                "shared_object_across_cases", "warn", object_id, entry,
                message=(f"'{object_id}' spans {len(entry['case_ids'])} cases — "
                         "potential divergence/bottleneck intersection."),
            ))

    amount_cfg = config.get("large_amount_observed", {})
    min_dollars = float(amount_cfg.get("min_dollars", 10_000))
    for object_id, entry in sorted(index.items()):
        if entry["type"] != "amount":
            continue
        value_part = object_id.split(":", 1)[-1]
        match = _AMOUNT_RE.match(value_part)
        if match and float(match.group(1)) >= min_dollars:
            alerts.append(_alert(
                "large_amount_observed", "critical", object_id, entry,
                message=f"Amount {object_id} observed at or above ${min_dollars:,.0f}.",
            ))

    hub_cfg = config.get("hub_actor", {})
    min_events = int(hub_cfg.get("min_events", 5))
    for object_id, entry in sorted(index.items()):
        if entry["type"] != "actor":
            continue
        unique_events = sorted(set(entry["event_ids"]))
        if len(unique_events) >= min_events:
            alerts.append(_alert(
                "hub_actor", "info", object_id, entry,
                message=f"Actor '{object_id}' touches {len(unique_events)} events.",
            ))

    severity_rank = {"critical": 0, "warn": 1, "info": 2}
    return sorted(alerts, key=lambda a: (severity_rank[a["severity"]],
                                         a["rule_id"], a["object_id"]))


def _alert(rule_id: str, severity: str, object_id: str,
           entry: dict[str, Any], *, message: str) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "object_id": object_id,
        "object_type": entry["type"],
        "message": message,
        "event_ids": sorted(set(entry["event_ids"])),
    }
