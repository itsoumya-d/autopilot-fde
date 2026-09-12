"""Autonomous FDE Workflow Synthesizer.

Maps discovered communication graphs (mined from Slack, WhatsApp, Email) into
concrete, executable instances of the 5 production-grade Enterprise Archetypes:
- Knowledge RAG
- Intake-to-Resolution LangGraph
- Document Intelligence & Approval
- Customer Data Onboarding
- Operations Command Center
"""

from __future__ import annotations

from typing import Any

from ..models.schema import ArchetypeType, Process


class WorkflowSynthesizer:
    """Classifies and synthesizes discovered enterprise workflows into production archetypes."""

    @staticmethod
    def classify_archetype(process: Process) -> ArchetypeType:
        """Determines the best-fit enterprise archetype from process metadata and activity semantics."""
        name_and_steps = (process.name + " " + " ".join(a.name for a in process.activities)).lower()
        category = (process.category or "").lower()

        # Project 5: Operations Command Center
        if any(w in name_and_steps for w in ["incident", "alert", "outage", "monitor", "telemetry", "devops", "sre", "crash"]):
            return ArchetypeType.PROJECT5_OPERATIONS_CMD

        # Project 3: Document Intelligence & Approval
        if any(w in name_and_steps for w in ["invoice", "receipt", "contract", "billing", "reconciliation", "accounting"]):
            return ArchetypeType.PROJECT3_DOCUMENT_INTEL

        # Project 4: Customer Data Onboarding
        if any(w in name_and_steps for w in ["onboard", "migration", "csv", "import", "sync", "data pipeline", "etl"]):
            return ArchetypeType.PROJECT4_DATA_ONBOARDING

        # Project 1: Permission-Aware Knowledge System
        if any(w in name_and_steps for w in ["policy", "wiki", "handbook", "knowledge", "faq", "documentation"]):
            return ArchetypeType.PROJECT1_KNOWLEDGE_RAG

        # Project 2: Default Intake-to-Resolution Workflow
        return ArchetypeType.PROJECT2_INTAKE_RESOLUTION

    @classmethod
    def synthesize(cls, process: Process) -> dict[str, Any]:
        """Synthesizes deployment blueprint, architecture recommendations, and safety requirements."""
        archetype = cls.classify_archetype(process)

        blueprints: dict[ArchetypeType, dict[str, Any]] = {
            ArchetypeType.PROJECT1_KNOWLEDGE_RAG: {
                "archetype": ArchetypeType.PROJECT1_KNOWLEDGE_RAG.value,
                "title": "Permission-Aware Enterprise Knowledge System",
                "recommended_stack": "FastAPI + Hybrid BM25/Dense Vector + RBAC Filter",
                "safety_guardrails": "Pre-retrieval role ACL gate + Grounding Verification Check",
                "latency_sla_ms": 250,
                "estimated_automation_rate": 0.85,
            },
            ArchetypeType.PROJECT2_INTAKE_RESOLUTION: {
                "archetype": ArchetypeType.PROJECT2_INTAKE_RESOLUTION.value,
                "title": "Intake-to-Resolution Orchestration Workflow",
                "recommended_stack": "LangGraph State Machine + SQLite Checkpointer + Webhook Triggers",
                "safety_guardrails": "Native interrupt() approval gates on high-risk write actions",
                "latency_sla_ms": 500,
                "estimated_automation_rate": 0.78,
            },
            ArchetypeType.PROJECT3_DOCUMENT_INTEL: {
                "archetype": ArchetypeType.PROJECT3_DOCUMENT_INTEL.value,
                "title": "Dual-Stage Document Intelligence & Approval",
                "recommended_stack": "Multimodal LLM Extraction + Pydantic Arithmetic Engine",
                "safety_guardrails": "Decoupled deterministic validation (Line Items + Tax == Total)",
                "latency_sla_ms": 1200,
                "estimated_automation_rate": 0.94,
            },
            ArchetypeType.PROJECT4_DATA_ONBOARDING: {
                "archetype": ArchetypeType.PROJECT4_DATA_ONBOARDING.value,
                "title": "Customer Data Onboarding Pipeline",
                "recommended_stack": "Fuzzy Column Matcher + Semantic Reconciler + Quarantine DLQ",
                "safety_guardrails": "Zero unverified row insertion; Quarantine DLQ for corrupt records",
                "latency_sla_ms": 3000,
                "estimated_automation_rate": 0.90,
            },
            ArchetypeType.PROJECT5_OPERATIONS_CMD: {
                "archetype": ArchetypeType.PROJECT5_OPERATIONS_CMD.value,
                "title": "Operations Command Center with Action Loop",
                "recommended_stack": "Event Stream Correlator + Dry-Run Canary + 1-Click Rollback Ledger",
                "safety_guardrails": "Mandatory dry-run simulation before execution; cryptographic rollback token",
                "latency_sla_ms": 150,
                "estimated_automation_rate": 0.72,
            },
        }

        spec = blueprints[archetype]
        spec["process_id"] = process.id
        spec["process_name"] = process.name
        return spec
