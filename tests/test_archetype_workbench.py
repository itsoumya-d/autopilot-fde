"""ASGI contract journeys for the synthetic, in-memory archetype workbench.

These exercise the real app routes without starting its unrelated demo-database
lifespan. They neither contact customer services nor execute real remediations.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import backend.api.archetypes as archetypes_api
from backend.archetypes.project2_intake_resolution import IntakeOrchestrator, IntakeTransitionError
from backend.archetypes.project5_operations_cmd import IncidentTransitionError, OperationsCommandCenter
from backend.main import app
from backend.models.schema import ChannelType, TelemetryAlert

PREFIX = "/api/archetypes"


@pytest.fixture
def workbench(monkeypatch):
    intake = IntakeOrchestrator()
    operations = OperationsCommandCenter()
    monkeypatch.setattr(archetypes_api, "_intake_orchestrator", intake)
    monkeypatch.setattr(archetypes_api, "_cmd_center", operations)
    client = TestClient(app)
    yield client, intake, operations
    client.close()


def test_intake_pending_approval_to_resolved_contract(workbench):
    client, intake, _ = workbench
    response = client.post(f"{PREFIX}/project2/ticket", json={
        "customer": "Synthetic customer",
        "channel": "email",
        "content": "Please review a refund for this synthetic invoice.",
    })
    assert response.status_code == 200
    pending = response.json()
    assert pending["status"] == "pending_approval"
    assert pending["state_machine_step"] == "awaiting_human_approval"
    assert pending["requires_approval"] is True
    assert pending["approval_token"]
    approval = {
        "ticket_id": pending["id"],
        "approval_token": pending["approval_token"],
        "operator": "Synthetic operator",
    }

    # Missing inputs, unknown records, and wrong tokens must not mutate state.
    for field in ("ticket_id", "approval_token"):
        missing = {key: value for key, value in approval.items() if key != field}
        assert client.post(f"{PREFIX}/project2/approve", json=missing).status_code == 422
    unknown = client.post(f"{PREFIX}/project2/approve", json={**approval, "ticket_id": "TICK-UNKNOWN"})
    assert unknown.status_code == 404
    assert unknown.json() == {"detail": "Ticket not found"}
    invalid = client.post(f"{PREFIX}/project2/approve", json={**approval, "approval_token": "wrong-token"})
    assert invalid.status_code == 400
    assert invalid.json() == {"detail": "Invalid approval token"}
    assert intake.get_ticket(pending["id"]).model_dump(mode="json") == pending
    assert client.get(f"{PREFIX}/project2/tickets").json() == [pending]

    approved = client.post(f"{PREFIX}/project2/approve", json=approval)
    assert approved.status_code == 200
    resolved = approved.json()
    assert resolved["id"] == pending["id"]
    assert resolved["status"] == "resolved"
    assert resolved["state_machine_step"] == "action_executed"
    assert resolved["requires_approval"] is False
    assert resolved["approval_token"] is None
    assert resolved["suggested_action"].count("Approved by Synthetic operator") == 1

    repeated = client.post(f"{PREFIX}/project2/approve", json=approval)
    assert repeated.status_code == 409
    assert repeated.json() == {"detail": "Ticket is not awaiting approval"}
    assert client.get(f"{PREFIX}/project2/tickets").json() == [resolved]


def test_approval_is_bound_to_the_pending_ticket(workbench):
    client, intake, _ = workbench
    first = intake.ingest_ticket("Synthetic one", ChannelType.EMAIL, "Refund review")
    second = intake.ingest_ticket("Synthetic two", ChannelType.EMAIL, "Refund review")
    invalid = client.post(f"{PREFIX}/project2/approve", json={
        "ticket_id": second.id, "approval_token": first.approval_token,
    })
    assert invalid.status_code == 400
    assert second.status == "pending_approval"
    ordinary = intake.ingest_ticket("Synthetic three", ChannelType.EMAIL, "Help with a guide")
    refused = client.post(f"{PREFIX}/project2/approve", json={
        "ticket_id": ordinary.id, "approval_token": first.approval_token,
    })
    assert refused.status_code == 409
    assert ordinary.status == "resolving"
    # The domain guard also rejects a ticket whose approval flag is disabled.
    second.requires_approval = False
    with pytest.raises(IntakeTransitionError):
        intake.approve_ticket(second.id, second.approval_token, "Synthetic operator")


def test_incident_remediation_and_single_use_rollback_contract(workbench):
    client, _, operations = workbench
    endpoint = f"{PREFIX}/project5/correlate-and-remediate"
    empty = client.post(endpoint, params={"simulate_incident": False})
    assert empty.json() == {"status": "no_incidents", "incidents": []}

    response = client.post(endpoint, params={"simulate_incident": True})
    assert response.status_code == 200
    result = response.json()
    remediated = result["incident"]
    assert result["status"] == "remediation_executed"
    assert result["rollback_ready"] is True
    assert remediated["state"] == "remediated"
    assert remediated["can_rollback"] is True
    assert result["rollback_token"] == remediated["rollback_token"]
    rollback = {
        "incident_id": remediated["incident_id"],
        "rollback_token": result["rollback_token"],
        "operator": "Synthetic SRE",
    }

    for field in ("incident_id", "rollback_token"):
        missing = {key: value for key, value in rollback.items() if key != field}
        assert client.post(f"{PREFIX}/project5/rollback", json=missing).status_code == 422
    unknown = client.post(f"{PREFIX}/project5/rollback", json={**rollback, "incident_id": "INC-UNKNOWN"})
    assert unknown.status_code == 404
    assert unknown.json() == {"detail": "Incident not found"}
    invalid = client.post(f"{PREFIX}/project5/rollback", json={**rollback, "rollback_token": "wrong-token"})
    assert invalid.status_code == 400
    assert invalid.json() == {"detail": "Invalid rollback token"}
    assert operations.incidents[rollback["incident_id"]].model_dump() == remediated
    assert operations.rollback_history == []

    # Reading/correlating without new alerts must not replay an old remediation.
    assert client.post(endpoint, params={"simulate_incident": False}).json() == empty.json()
    rolled_back = client.post(f"{PREFIX}/project5/rollback", json=rollback)
    assert rolled_back.status_code == 200
    event = rolled_back.json()
    assert event["status"] == "success"
    assert event["incident_id"] == rollback["incident_id"]
    assert event["operator"] == "Synthetic SRE"
    snapshot = event["incident"]
    assert snapshot["state"] == "rolled_back"
    assert snapshot["can_rollback"] is False
    assert snapshot["rollback_token"] == ""
    assert snapshot == operations.incidents[rollback["incident_id"]].model_dump()
    assert len(operations.rollback_history) == 1

    repeated = client.post(f"{PREFIX}/project5/rollback", json=rollback)
    assert repeated.status_code == 409
    assert repeated.json() == {"detail": "Incident is not eligible for rollback"}
    assert len(operations.rollback_history) == 1
    assert client.post(endpoint, params={"simulate_incident": False}).json() == empty.json()
    assert operations.incidents[rollback["incident_id"]].model_dump() == snapshot

    # A second simulation must advance its NEW incident, leaving history intact.
    fresh = client.post(endpoint, params={"simulate_incident": True}).json()
    assert fresh["incident"]["incident_id"] != rollback["incident_id"]
    assert fresh["incident"]["state"] == "remediated"
    assert fresh["rollback_token"] != rollback["rollback_token"]
    assert operations.incidents[rollback["incident_id"]].model_dump() == snapshot
    mismatched = client.post(f"{PREFIX}/project5/rollback", json={
        **rollback, "incident_id": fresh["incident"]["incident_id"],
    })
    assert mismatched.status_code == 400
    assert len(operations.rollback_history) == 1


def test_domain_incident_guards_reject_unexecuted_and_consumed_transitions():
    operations = OperationsCommandCenter()
    for service in ("postgresql-primary", "api-gateway"):
        operations.ingest_alert(TelemetryAlert(
            id=f"SYNTHETIC-{service}", service=service, metric="test",
            severity="critical", value=99, threshold=80,
        ))
    incident = operations.correlate_incidents()[0]
    token = incident.rollback_token
    with pytest.raises(IncidentTransitionError, match="not eligible for rollback"):
        operations.rollback_action(incident.incident_id, token, "Synthetic SRE")
    operations.execute_remediation(incident.incident_id)
    with pytest.raises(IncidentTransitionError, match="not ready for remediation"):
        operations.execute_remediation(incident.incident_id)
    incident.can_rollback = False
    with pytest.raises(IncidentTransitionError, match="not eligible for rollback"):
        operations.rollback_action(incident.incident_id, token, "Synthetic SRE")
    incident.can_rollback = True
    operations.rollback_action(incident.incident_id, token, "Synthetic SRE")
    with pytest.raises(IncidentTransitionError, match="not ready for remediation"):
        operations.execute_remediation(incident.incident_id)
    assert incident.state == "rolled_back"
    assert len(operations.rollback_history) == 1
