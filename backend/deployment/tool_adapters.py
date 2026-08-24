"""Safe reference tool adapters for generated agents.

``AgentFactory.generate_langgraph_code`` emits workflows whose automated nodes
call ``execute_agent_step(step_name, context)``. This module is the reference
implementation of that function: it dispatches on the step's risk tier (the
same ``APSEngine.STEP_CLASSIFIERS`` table that scored it during discovery) and
executes only what the tier allows.

Safety model, stated plainly:

- READ_ONLY        -> deterministic context formatting. No side effects.
- DRAFT_ONLY       -> writes a draft artifact to a local review directory.
- INTERNAL_ACTION  -> POSTs the payload to an operator-configured internal
                      webhook URL taken from ``context["webhook_url"]``.
- EXTERNAL_WRITE   -> structurally blocked. A human sends the message.
- CRITICAL_TRANSACTION -> structurally blocked, always.

Blocked tiers raise :class:`StructuralGateError` -- never a silent success.
The boundary lives in code, not in policy files, so no configuration can
talk a generated workflow past it.
"""

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from ..models.schema import StepActionType
from ..scoring.aps_engine import APSEngine

_DRAFT_DIR_ENV = "AUTOPILOT_DRAFT_DIR"
_DEFAULT_TIMEOUT_SECONDS = 10.0
_MAX_WEBHOOK_PAYLOAD_BYTES = 64 * 1024


class StructuralGateError(RuntimeError):
    """A step's risk tier forbids automatic execution.

    Raised for EXTERNAL_WRITE and CRITICAL_TRANSACTION steps regardless of any
    configuration: those steps require a human, by construction.
    """


def classify_step(step_name: str) -> StepActionType:
    """Risk tier for a step name; unknown steps classify conservatively."""
    entry = APSEngine.STEP_CLASSIFIERS.get(step_name)
    if entry:
        return entry[0]
    lowered = step_name.lower()
    if any(word in lowered for word in ("pay", "refund", "delete", "credential", "wire", "rollback")):
        return StepActionType.CRITICAL_TRANSACTION
    if any(word in lowered for word in ("send", "post", "publish", "email customer")):
        return StepActionType.EXTERNAL_WRITE
    if any(word in lowered for word in ("draft", "summar", "prepare", "brief")):
        return StepActionType.DRAFT_ONLY
    if any(word in lowered for word in ("assign", "schedule", "update", "provision", "reconcile", "confirm")):
        return StepActionType.INTERNAL_ACTION
    return StepActionType.READ_ONLY


def execute_agent_step(step_name: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Dispatch a generated-workflow step to the adapter its risk tier allows.

    This is the function generated LangGraph code imports. An unimplemented
    step must fail loudly instead of pretending the work happened.
    """
    context = dict(context or {})
    action_type = classify_step(step_name)
    handler = _HANDLERS.get(action_type)
    if handler is None:
        raise StructuralGateError(
            f"Step '{step_name}' is classified {action_type.value}; "
            "this tier cannot be executed automatically and requires a human."
        )
    result = handler(step_name, context)
    result.setdefault("step_name", step_name)
    result.setdefault("action_type", action_type.value)
    result["executed_at"] = datetime.now(UTC).isoformat()
    return result


def _format_context(step_name: str, context: dict[str, Any]) -> dict[str, Any]:
    """READ_ONLY adapter: deterministic summary of the working context."""
    keys = sorted(context.keys())
    preview = {
        key: context[key]
        for key in keys
        if isinstance(context[key], str | int | float | bool) or context[key] is None
    }
    return {
        "status": "completed",
        "adapter": "read_only_context",
        "observed_keys": keys,
        "scalar_fields": preview,
        "detail": f"Read-only inspection for '{step_name}' completed; no systems were modified.",
    }


def _write_draft(step_name: str, context: dict[str, Any]) -> dict[str, Any]:
    """DRAFT_ONLY adapter: persist a draft artifact for human review."""
    base_raw = os.getenv(_DRAFT_DIR_ENV, "")
    base = Path(base_raw).expanduser() if base_raw else Path.cwd() / "runs" / "drafts"
    base.mkdir(parents=True, exist_ok=True)

    slug = re.sub(r"[^a-z0-9]+", "-", step_name.lower()).strip("-") or "draft"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = base / f"{stamp}-{slug}.json"
    artifact = {
        "step_name": step_name,
        "created_at": datetime.now(UTC).isoformat(),
        "status": "pending_human_review",
        "context": context,
    }
    path.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")
    return {
        "status": "draft_written",
        "adapter": "draft_only_writer",
        "draft_path": str(path),
        "safety_note": "Nothing was sent externally; a human must review and forward this draft.",
    }


def _resolve_webhook_url(context: dict[str, Any]) -> str:
    url = str(context.get("webhook_url", "")).strip()
    if not url:
        raise ValueError(
            "INTERNAL_ACTION step needs context['webhook_url'] pointing at your "
            "internal endpoint (Jira/CRM/ITSM bridge)."
        )
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(f"Refusing non-HTTP webhook URL: {url!r}")
    if parsed.hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1") and not os.getenv(
        "AUTOPILOT_ALLOW_LOCAL_WEBHOOKS"
    ):
        raise ValueError(
            "Refusing loopback webhook URL; set AUTOPILOT_ALLOW_LOCAL_WEBHOOKS=1 "
            "for local integration testing."
        )
    return url


def _post_webhook(step_name: str, context: dict[str, Any]) -> dict[str, Any]:
    """INTERNAL_ACTION adapter: relay the payload to an internal system."""
    url = _resolve_webhook_url(context)
    payload = {"step_name": step_name, "context": context}
    body = json.dumps(payload, default=str).encode()
    if len(body) > _MAX_WEBHOOK_PAYLOAD_BYTES:
        raise ValueError("Webhook payload exceeds 64 KiB; trim the context first.")
    headers = {"Content-Type": "application/json"}
    token = os.getenv("AUTOPILOT_WEBHOOK_BEARER_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with httpx.Client(timeout=_DEFAULT_TIMEOUT_SECONDS, follow_redirects=False) as client:
        response = client.post(url, content=body, headers=headers)
    return {
        "status": "dispatched",
        "adapter": "internal_webhook",
        "endpoint_host": parsed_host(url),
        "response_status_code": response.status_code,
        "accepted": 200 <= response.status_code < 300,
    }


def parsed_host(url: str) -> str:
    return urlparse(url).hostname or ""


_HANDLERS = {
    StepActionType.READ_ONLY: _format_context,
    StepActionType.DRAFT_ONLY: _write_draft,
    StepActionType.INTERNAL_ACTION: _post_webhook,
    # EXTERNAL_WRITE and CRITICAL_TRANSACTION have no handler on purpose.
}

__all__ = [
    "StructuralGateError",
    "classify_step",
    "execute_agent_step",
]
