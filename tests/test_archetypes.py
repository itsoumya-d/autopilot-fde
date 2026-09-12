"""Comprehensive tests for the 5 FDE Enterprise Archetypes and Synthesizer."""

from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
import unittest
import pytest
from fastapi.testclient import TestClient

import backend.database as database
import backend.main as main_mod
import backend.api.archetypes as archetypes_api
from backend.archetypes.project1_knowledge_rag import PermissionAwareRAG
from backend.archetypes.project2_intake_resolution import IntakeOrchestrator
from backend.archetypes.project3_document_intel import DocumentIntelligenceEngine
from backend.archetypes.project4_data_onboarding import DataOnboardingPipeline
from backend.archetypes.project5_operations_cmd import OperationsCommandCenter
from backend.discovery.synthesizer import WorkflowSynthesizer
from backend.models.schema import (
    ArchetypeType,
    ChannelType,
    ExtractedInvoice,
    KnowledgeDocument,
    LineItem,
    Process,
    TelemetryAlert,
    UserRole,
)


class TestArchetypesSuite(unittest.TestCase):
    def setUp(self):
        self._db = database
        self._tmp = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self._tmp.name) / "test.db"
        # Reset module-level instances for clean test isolation
        archetypes_api._cmd_center = OperationsCommandCenter()
        archetypes_api._intake_orchestrator = IntakeOrchestrator()
        archetypes_api._rag_engine = PermissionAwareRAG()
        self.client = TestClient(main_mod.app)
        self._ctx = self.client.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._db.close_db())
        finally:
            loop.close()
        self._tmp.cleanup()

    # ── Project 1 Tests ────────────────────────────────────────────────────

    def test_project1_permission_aware_rag(self):
        rag = PermissionAwareRAG()

        # Engineering querying architecture: should succeed
        eng_res = rag.query("Kubernetes clusters architecture", UserRole.ENGINEERING)
        assert eng_res.allowed is True
        assert len(eng_res.citations) > 0
        assert eng_res.grounding_score >= 0.85

        # Finance querying executive HR compensation: should be blocked by ACL
        blocked_res = rag.query("Executive compensation bonus", UserRole.FINANCE)
        assert blocked_res.allowed is False
        assert blocked_res.blocked_count > 0

        # Query completely unmatched
        unmatched = rag.query("Zookeeper quantum astronomy", UserRole.ENGINEERING)
        assert unmatched.allowed is True
        assert "No relevant knowledge found" in unmatched.answer

        # API test
        resp = self.client.post("/api/archetypes/project1/query", json={"query": "Vacation policy", "user_role": "guest"})
        assert resp.status_code == 200
        assert resp.json()["allowed"] is True

    # ── Project 2 Tests ────────────────────────────────────────────────────

    def test_project2_intake_resolution_workflow(self):
        orchestrator = IntakeOrchestrator()

        # Normal ticket: auto resolution
        ticket1 = orchestrator.ingest_ticket("Acme Corp", ChannelType.SLACK, "How do I invite a teammate?")
        assert ticket1.priority == "low"
        assert ticket1.requires_approval is False
        assert ticket1.status == "resolving"

        # Critical financial ticket: requires approval with token
        ticket2 = orchestrator.ingest_ticket("Beta LLC", ChannelType.EMAIL, "Urgent: issue a refund of $500 immediately")
        assert ticket2.priority == "high"
        assert ticket2.requires_approval is True
        assert ticket2.approval_token is not None
        assert ticket2.status == "pending_approval"

        # Verify get_ticket and list_tickets
        assert orchestrator.get_ticket(ticket2.id) is not None
        assert len(orchestrator.list_tickets()) == 2

        # Approve ticket with valid token
        resolved = orchestrator.approve_ticket(ticket2.id, ticket2.approval_token, "Senior Engineer")
        assert resolved.status == "resolved"
        assert resolved.requires_approval is False

        # Invalid token raises error
        with pytest.raises(ValueError):
            orchestrator.approve_ticket(ticket2.id, "WRONG-TOKEN", "Admin")

        # Unknown ticket raises error
        with pytest.raises(KeyError):
            orchestrator.approve_ticket("TICK-UNKNOWN", "TOKEN", "Admin")

        # API tests
        resp = self.client.post("/api/archetypes/project2/ticket", json={"customer": "Test", "content": "Refund $200"})
        assert resp.status_code == 200
        t_id = resp.json()["id"]
        t_token = resp.json()["approval_token"]

        # List tickets API
        list_resp = self.client.get("/api/archetypes/project2/tickets")
        assert list_resp.status_code == 200

        # Approve ticket API
        appr_resp = self.client.post("/api/archetypes/project2/approve", json={"ticket_id": t_id, "approval_token": t_token})
        assert appr_resp.status_code == 200
        assert appr_resp.json()["status"] == "resolved"

        # Approve with wrong token returns 400
        appr_fail = self.client.post("/api/archetypes/project2/approve", json={"ticket_id": t_id, "approval_token": "BAD-TOKEN"})
        assert appr_fail.status_code == 400

        # Approve unknown ticket returns 404
        appr_404 = self.client.post("/api/archetypes/project2/approve", json={"ticket_id": "TICK-UNKNOWN", "approval_token": "T"})
        assert appr_404.status_code == 404

    # ── Project 3 Tests ────────────────────────────────────────────────────

    def test_project3_document_intelligence_validation(self):
        # Valid invoice
        valid_inv = ExtractedInvoice(
            invoice_id="INV-001",
            vendor="CloudCorp",
            date="2026-09-12",
            line_items=[
                LineItem(description="Server", quantity=2.0, unit_price=100.0, total=200.0),
                LineItem(description="Storage", quantity=1.0, unit_price=50.0, total=50.0),
            ],
            subtotal=250.0,
            tax=20.0,
            total_amount=270.0,
        )
        report = DocumentIntelligenceEngine.validate_invoice(valid_inv)
        assert report.is_valid is True
        assert report.arithmetic_valid is True
        assert "AUTO_APPROVE" in report.action_recommended

        # Corrupt invoice with math discrepancy in line items AND subtotal mismatch
        corrupt_inv = ExtractedInvoice(
            invoice_id="INV-002",
            vendor="CloudCorp",
            date="2026-09-12",
            line_items=[
                LineItem(description="Server", quantity=2.0, unit_price=100.0, total=250.0),  # Line math mismatch
            ],
            subtotal=200.0,  # Subtotal mismatch: line item total is 250, stated is 200
            tax=20.0,
            total_amount=300.0,  # Total mismatch: 200 + 20 != 300
        )
        bad_report = DocumentIntelligenceEngine.validate_invoice(corrupt_inv)
        assert bad_report.is_valid is False
        assert bad_report.arithmetic_valid is False
        assert len(bad_report.discrepancy_details) >= 3

        # API test
        resp = self.client.post("/api/archetypes/project3/validate-invoice", json={"simulate_discrepancy": True})
        assert resp.status_code == 200
        assert resp.json()["is_valid"] is False

    # ── Project 4 Tests ────────────────────────────────────────────────────

    def test_project4_data_onboarding_pipeline(self):
        # Test unrecognized column match returns None
        assert DataOnboardingPipeline.match_column("unrecognized_column_gibberish_99") is None

        raw_batch = [
            {"client_id": "C-1", "contact_name": "John Doe", "e-mail": "john@doe.com", "revenue": 15000.0},
            {"client_id": "C-2", "contact_name": "Jane Bad", "e-mail": "invalid-email", "revenue": 8000.0},
            {"client_id": "C-3", "contact_name": "Negative Spend", "e-mail": "neg@test.com", "revenue": -200.0},
            {"client_id": "C-4", "contact_name": "Non-numeric", "e-mail": "nn@test.com", "revenue": "not-a-number"},
            {"client_id": "", "contact_name": "Missing ID", "e-mail": "no-id@test.com", "revenue": 100.0},
        ]
        report, rows = DataOnboardingPipeline.process_batch("test.csv", raw_batch)
        assert report.total_rows == 5
        assert report.accepted_rows == 1
        assert report.quarantined_rows == 4
        assert report.schema_match_pct > 50.0

        # Empty batch
        empty_report, empty_rows = DataOnboardingPipeline.process_batch("empty.csv", [])
        assert empty_report.total_rows == 0

        # API test
        resp = self.client.post("/api/archetypes/project4/onboard-data", json={"filename": "api_test.csv"})
        assert resp.status_code == 200
        assert resp.json()["report"]["total_rows"] == 5
        assert resp.json()["report"]["quarantined_rows"] > 0

    # ── Project 5 Tests ────────────────────────────────────────────────────

    def test_project5_operations_command_center(self):
        cmd = OperationsCommandCenter()
        assert cmd.correlate_incidents() == []

        cmd.ingest_alert(TelemetryAlert(id="A1", service="db-cluster", metric="connections", severity="critical", value=99.0, threshold=80.0))
        cmd.ingest_alert(TelemetryAlert(id="A2", service="api-gw", metric="errors", severity="critical", value=50.0, threshold=5.0))

        incidents = cmd.correlate_incidents()
        assert len(incidents) == 1
        inc = incidents[0]
        assert inc.can_rollback is True

        # Unknown incident error in remediation
        with pytest.raises(KeyError):
            cmd.execute_remediation("INC-UNKNOWN")

        # Execute remediation
        remediated = cmd.execute_remediation(inc.incident_id)
        assert remediated.state == "remediated"

        # Rollback error cases
        with pytest.raises(KeyError):
            cmd.rollback_action("INC-UNKNOWN", "T", "Op")
        with pytest.raises(ValueError):
            cmd.rollback_action(inc.incident_id, "WRONG-TOKEN", "Op")

        # Rollback remediation
        rollback_res = cmd.rollback_action(inc.incident_id, inc.rollback_token, "Lead SRE")
        assert rollback_res["status"] == "success"
        assert inc.state == "rolled_back"

        # API test: Correlate when no incidents exist initially
        resp_no_inc = self.client.post("/api/archetypes/project5/correlate-and-remediate?simulate_incident=false")
        assert resp_no_inc.status_code == 200
        assert resp_no_inc.json()["status"] == "no_incidents"

        # API tests: Ingest alert
        alert_resp = self.client.post(
            "/api/archetypes/project5/alert",
            json={"service": "frontend", "metric": "latency", "severity": "warning", "value": 350.0, "threshold": 200.0},
        )
        assert alert_resp.status_code == 200

        # Correlate and remediate API with simulation
        resp = self.client.post("/api/archetypes/project5/correlate-and-remediate?simulate_incident=true")
        assert resp.status_code == 200
        data = resp.json()
        assert "incident" in data
        inc_id = data["incident"]["incident_id"]
        rb_token = data["rollback_token"]

        # Rollback API
        rb_resp = self.client.post("/api/archetypes/project5/rollback", json={"incident_id": inc_id, "rollback_token": rb_token})
        assert rb_resp.status_code == 200
        assert rb_resp.json()["status"] == "success"

        # Rollback API error handling
        rb_fail = self.client.post("/api/archetypes/project5/rollback", json={"incident_id": inc_id, "rollback_token": "BAD-TOKEN"})
        assert rb_fail.status_code == 400

        rb_404 = self.client.post("/api/archetypes/project5/rollback", json={"incident_id": "INC-UNKNOWN", "rollback_token": "T"})
        assert rb_404.status_code == 404

    # ── Workflow Synthesizer Tests ─────────────────────────────────────────

    def test_workflow_synthesizer_classifies_archetypes(self):
        # SRE workflow -> Project 5
        p_ops = Process(id="P1", name="Database latency spike alert and pod scaling")
        assert WorkflowSynthesizer.classify_archetype(p_ops) == ArchetypeType.PROJECT5_OPERATIONS_CMD

        # Accounting workflow -> Project 3
        p_doc = Process(id="P2", name="Monthly vendor invoice reconciliation")
        assert WorkflowSynthesizer.classify_archetype(p_doc) == ArchetypeType.PROJECT3_DOCUMENT_INTEL

        # Onboarding workflow -> Project 4
        p_onb = Process(id="P3", name="Client CSV data import and CRM migration")
        assert WorkflowSynthesizer.classify_archetype(p_onb) == ArchetypeType.PROJECT4_DATA_ONBOARDING

        # Knowledge wiki -> Project 1
        p_wiki = Process(id="P4", name="Company vacation policy and employee FAQ handbook")
        assert WorkflowSynthesizer.classify_archetype(p_wiki) == ArchetypeType.PROJECT1_KNOWLEDGE_RAG

        # Default intake -> Project 2
        p_intake = Process(id="P5", name="Customer general ticket support inquiry")
        assert WorkflowSynthesizer.classify_archetype(p_intake) == ArchetypeType.PROJECT2_INTAKE_RESOLUTION

        # Synthesize specs for all 5 archetypes
        for p in [p_ops, p_doc, p_onb, p_wiki, p_intake]:
            spec = WorkflowSynthesizer.synthesize(p)
            assert "safety_guardrails" in spec
            assert "recommended_stack" in spec
            assert "latency_sla_ms" in spec
