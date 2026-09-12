"""FastAPI router for the 5 Production-Grade FDE Enterprise Archetypes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..archetypes.project1_knowledge_rag import PermissionAwareRAG
from ..archetypes.project2_intake_resolution import IntakeOrchestrator
from ..archetypes.project3_document_intel import DocumentIntelligenceEngine
from ..archetypes.project4_data_onboarding import DataOnboardingPipeline
from ..archetypes.project5_operations_cmd import OperationsCommandCenter
from ..models.schema import (
    ChannelType,
    CorrelatedIncident,
    DocumentValidationReport,
    ExtractedInvoice,
    IntakeTicket,
    KnowledgeQueryResult,
    OnboardingBatchReport,
    OnboardingRow,
    TelemetryAlert,
    UserRole,
)

router = APIRouter()

# Global state instances for interactive demos
_rag_engine = PermissionAwareRAG()
_intake_orchestrator = IntakeOrchestrator()
_cmd_center = OperationsCommandCenter()


# ── Project 1: Permission-Aware Knowledge RAG ──────────────────────────────

class KnowledgeQueryRequest(BaseModel):
    query: str
    user_role: UserRole = UserRole.ENGINEERING


@router.post("/project1/query", response_model=KnowledgeQueryResult, summary="Query permission-scoped knowledge fabric")
async def query_knowledge(req: KnowledgeQueryRequest) -> KnowledgeQueryResult:
    return _rag_engine.query(req.query, req.user_role)


# ── Project 2: Intake-to-Resolution Orchestrator ───────────────────────────

class IngestTicketRequest(BaseModel):
    customer: str
    channel: ChannelType = ChannelType.SLACK
    content: str


class ApproveTicketRequest(BaseModel):
    ticket_id: str
    approval_token: str
    operator: str = "Lead FDE"


@router.post("/project2/ticket", response_model=IntakeTicket, summary="Ingest request into stateful LangGraph-style workflow")
async def ingest_ticket(req: IngestTicketRequest) -> IntakeTicket:
    return _intake_orchestrator.ingest_ticket(req.customer, req.channel, req.content)


@router.post("/project2/approve", response_model=IntakeTicket, summary="Resume paused state machine with human approval")
async def approve_ticket(req: ApproveTicketRequest) -> IntakeTicket:
    try:
        return _intake_orchestrator.approve_ticket(req.ticket_id, req.approval_token, req.operator)
    except KeyError:
        raise HTTPException(status_code=404, detail="Ticket not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/project2/tickets", response_model=list[IntakeTicket], summary="List all active intake tickets")
async def list_tickets() -> list[IntakeTicket]:
    return _intake_orchestrator.list_tickets()


# ── Project 3: Dual-Stage Document Intelligence ────────────────────────────

class ValidateInvoiceRequest(BaseModel):
    invoice: ExtractedInvoice | None = None
    simulate_discrepancy: bool = False


@router.post("/project3/validate-invoice", response_model=DocumentValidationReport, summary="Decoupled document extraction and deterministic math validation")
async def validate_invoice(req: ValidateInvoiceRequest) -> DocumentValidationReport:
    invoice = req.invoice or DocumentIntelligenceEngine.parse_raw_text("")
    if req.simulate_discrepancy:
        # Intentionally inject a 10 dollar arithmetic mismatch
        invoice.total_amount += 10.0
    return DocumentIntelligenceEngine.validate_invoice(invoice)


# ── Project 4: Customer Data Onboarding Pipeline ───────────────────────────

class OnboardDataRequest(BaseModel):
    filename: str = "customer_dirty_export.csv"
    rows: list[dict[str, Any]] | None = None


@router.post("/project4/onboard-data", summary="Fuzzy schema reconciliation and Quarantine DLQ processing")
async def onboard_data(req: OnboardDataRequest) -> dict[str, Any]:
    sample_rows = req.rows or [
        {"Client_ID": "CUST-101", "Full Name": "Alice Henderson", "Email Address": "alice@henderson.com", "ARR": 45000.0},
        {"Client_ID": "CUST-102", "Full Name": "Bob Jenkins", "Email Address": "bad-email-format", "ARR": 12000.0},
        {"Client_ID": "", "Full Name": "Charlie Day", "Email Address": "charlie@paddys.com", "ARR": 8500.0},
        {"Client_ID": "CUST-104", "Full Name": "Diana Prince", "Email Address": "diana@themyscira.io", "ARR": -500.0},
        {"Client_ID": "CUST-105", "Full Name": "Evan Wright", "Email Address": "evan@wright.org", "ARR": 92000.0},
    ]
    report, processed = DataOnboardingPipeline.process_batch(req.filename, sample_rows)
    return {"report": report, "rows": processed}


# ── Project 5: Operations Command Center & Action Loop ─────────────────────

class IngestAlertRequest(BaseModel):
    service: str
    metric: str
    severity: str
    value: float
    threshold: float


@router.post("/project5/alert", summary="Ingest telemetry alert into operations command stream")
async def ingest_alert(req: IngestAlertRequest) -> dict[str, str]:
    import uuid
    alert = TelemetryAlert(
        id=f"ALT-{uuid.uuid4().hex[:6].upper()}",
        service=req.service,
        metric=req.metric,
        severity=req.severity,
        value=req.value,
        threshold=req.threshold,
    )
    _cmd_center.ingest_alert(alert)
    return {"status": "alert_ingested", "alert_id": alert.id}


@router.post("/project5/correlate-and-remediate", summary="Correlate alerts into incident and execute closed-loop remediation")
async def correlate_and_remediate(simulate_incident: bool = True) -> dict[str, Any]:
    if simulate_incident:
        _cmd_center.ingest_alert(TelemetryAlert(id="ALT-01", service="postgresql-primary", metric="connection_pool_saturation", severity="critical", value=98.5, threshold=85.0))
        _cmd_center.ingest_alert(TelemetryAlert(id="ALT-02", service="api-gateway", metric="http_504_gateway_timeout_rate", severity="critical", value=14.2, threshold=1.0))

    incidents = _cmd_center.correlate_incidents()
    if not incidents:
        return {"status": "no_incidents", "incidents": []}

    inc = incidents[0]
    remediated = _cmd_center.execute_remediation(inc.incident_id)
    return {
        "status": "remediation_executed",
        "incident": remediated,
        "rollback_ready": True,
        "rollback_token": remediated.rollback_token,
    }


class RollbackRequest(BaseModel):
    incident_id: str
    rollback_token: str
    operator: str = "On-Call SRE Lead"


@router.post("/project5/rollback", summary="1-click transactional rollback for executed remediation")
async def rollback_action(req: RollbackRequest) -> dict[str, Any]:
    try:
        return _cmd_center.rollback_action(req.incident_id, req.rollback_token, req.operator)
    except KeyError:
        raise HTTPException(status_code=404, detail="Incident not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
