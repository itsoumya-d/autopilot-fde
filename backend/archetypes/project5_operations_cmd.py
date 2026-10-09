"""Project 5: Synthetic Operations Command Center with an Action Loop.

Demonstrates alert correlation and guarded remediation/rollback transitions in
process-local memory. Root causes and action descriptions are canned examples;
no canary check, infrastructure change, or real transactional rollback occurs.
"""

from __future__ import annotations

import uuid
from typing import Any

from ..models.schema import CorrelatedIncident, TelemetryAlert


class IncidentTransitionError(ValueError):
    """The incident is not in the state required for the requested transition."""


class OperationsCommandCenter:
    """In-memory incident demo; remediation and rollback do not touch real services."""

    def __init__(self) -> None:
        self.alerts: list[TelemetryAlert] = []
        self.incidents: dict[str, CorrelatedIncident] = {}
        self.rollback_history: list[dict[str, Any]] = []

    def ingest_alert(self, alert: TelemetryAlert) -> None:
        self.alerts.append(alert)

    def correlate_incidents(self) -> list[CorrelatedIncident]:
        """Correlates recent alerts into unified root-cause incidents."""
        if not self.alerts:
            return list(self.incidents.values())

        # Group alerts by service or downstream impact
        services = {a.service for a in self.alerts}
        has_db_issue = any(any(k in s.lower() for k in ["database", "db", "postgres", "sql", "redis"]) for s in services)
        has_api_issue = any("api" in s.lower() or "gateway" in s.lower() for s in services)

        if has_db_issue and has_api_issue:
            incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
            rollback_token = f"RBK-{uuid.uuid4().hex[:8].upper()}"
            incident = CorrelatedIncident(
                incident_id=incident_id,
                title="Cascading API Latency from Database Connection Pool Exhaustion",
                severity="critical",
                correlated_alerts=[a.id for a in self.alerts],
                probable_root_cause="Simulated hypothesis: PostgreSQL max_connections reached during peak batch ETL (not verified).",
                canary_action="Example plan: scale read replica pool from 2 to 4 pods; no canary or dry-run performed.",
                remediation_action="Simulate connection pool expansion and batch-worker throttling in memory; no infrastructure changed.",
                can_rollback=True,
                rollback_token=rollback_token,
                state="ready_for_execution",
            )
            self.incidents[incident_id] = incident
            self.alerts = []  # Clear consumed alerts

        return list(self.incidents.values())

    def execute_remediation(self, incident_id: str) -> CorrelatedIncident:
        """Advance a ready incident's simulated remediation state in memory."""
        incident = self.incidents.get(incident_id)
        if not incident:
            raise KeyError(f"Incident {incident_id} not found")

        if incident.state != "ready_for_execution":
            raise IncidentTransitionError("Incident is not ready for remediation")

        incident.state = "remediated"
        return incident

    def rollback_action(self, incident_id: str, rollback_token: str, operator: str) -> dict[str, Any]:
        """Record one simulated rollback of a previously remediated incident."""
        incident = self.incidents.get(incident_id)
        if not incident:
            raise KeyError(f"Incident {incident_id} not found")

        if incident.state != "remediated" or not incident.can_rollback:
            raise IncidentTransitionError("Incident is not eligible for rollback")

        if incident.rollback_token != rollback_token:
            raise ValueError("Invalid rollback token")

        incident.state = "rolled_back"
        incident.can_rollback = False
        incident.rollback_token = ""
        event = {
            "incident_id": incident_id,
            "rollback_token": rollback_token,
            "operator": operator,
            "status": "success",
            "action": f"Simulated rollback for '{incident.title}'; no infrastructure changed.",
            "incident": incident.model_dump(),
        }
        self.rollback_history.append(event)
        return event
