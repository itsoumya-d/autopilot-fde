"""Connector profiles: declarative bridges from steps to internal systems.

An FDE wires a discovered step to ServiceNow / Salesforce / Jira by choosing
a profile and filling in the instance URL + credential env var. Profiles map
onto the governed INTERNAL_ACTION webhook adapter, so every dispatch keeps
the same guarantees: risk-tier gating, per-agent quota, idempotency,
dead-lettering on failure, and the tool-governance host allowlist.

Nothing here talks to a vendor API directly — each system's *inbound*
webhook/REST endpoint is called with the payload the profile defines.
Credentials are referenced by ENV VAR NAME only; values are read at call
time and never persisted or logged.
"""

from __future__ import annotations

from typing import Any

from ..models.schema import StepActionType
from .tool_adapters import execute_agent_step


class UnknownConnectorProfile(KeyError):
    pass


PROFILES: dict[str, dict[str, Any]] = {
    "servicenow": {
        "display_name": "ServiceNow ITSM",
        "default_path": "/api/now/table/incident",
        "credential_env": "SERVICENOW_TOKEN",
        "auth_style": "bearer",
        "payload_builder": None,
        "risk_tier": StepActionType.INTERNAL_ACTION,
    },
    "salesforce": {
        "display_name": "Salesforce CRM",
        "default_path": "/services/data/v62.0/sobjects/Case",
        "credential_env": "SALESFORCE_TOKEN",
        "auth_style": "bearer",
        "payload_builder": None,
        "risk_tier": StepActionType.INTERNAL_ACTION,
    },
    "jira": {
        "display_name": "Jira Software",
        "default_path": "/rest/api/3/issue",
        "credential_env": "JIRA_TOKEN",
        "auth_style": "bearer",
        "payload_builder": None,
        "risk_tier": StepActionType.INTERNAL_ACTION,
    },
}


def build_connector_context(profile_name: str,
                            instance_url: str,
                            summary: str,
                            fields: dict[str, Any] | None = None) -> dict[str, Any]:
    """Context dict ready for ``execute_agent_step`` on an INTERNAL step."""
    try:
        profile = PROFILES[profile_name]
    except KeyError:
        raise UnknownConnectorProfile(profile_name) from None
    builder = profile["payload_builder"] or _generic_payload
    return {
        "webhook_url": f"{instance_url.rstrip('/')}{profile['default_path']}",
        "connector_profile": profile_name,
        "credential_env": profile["credential_env"],
        "payload": builder(summary, fields or {}),
    }


def _generic_payload(summary: str, fields: dict[str, Any]) -> dict[str, Any]:
    return {"summary": summary, **fields}


def _servicenow_payload(summary: str, fields: dict[str, Any]) -> dict[str, Any]:
    return {"short_description": summary,
            "description": fields.get("description", summary), **fields}


def _salesforce_payload(summary: str, fields: dict[str, Any]) -> dict[str, Any]:
    return {"Subject": summary,
            "Description": fields.get("Description", summary), **fields}


def _jira_payload(summary: str, fields: dict[str, Any]) -> dict[str, Any]:
    return {"fields": {"summary": summary, **(fields.get("fields", {}))}}


PROFILES["servicenow"]["payload_builder"] = _servicenow_payload
PROFILES["salesforce"]["payload_builder"] = _salesforce_payload
PROFILES["jira"]["payload_builder"] = _jira_payload


def dispatch_connector_step(step_name: str, profile_name: str,
                            instance_url: str, summary: str,
                            fields: dict[str, Any] | None = None,
                            *,
                            agent_id: str | None = None,
                            idempotency_key: str | None = None) -> dict[str, Any]:
    """Full guarded path: profile context -> risk-tiered adapter."""
    context = build_connector_context(profile_name, instance_url, summary, fields)
    if idempotency_key:
        context["idempotency_key"] = idempotency_key
    tier = PROFILES[profile_name]["risk_tier"]
    if tier is not StepActionType.INTERNAL_ACTION:  # pragma: no cover - table guard
        raise ValueError(f"Profile '{profile_name}' is not dispatchable automatically.")
    return execute_agent_step(step_name, context, agent_id=agent_id)
