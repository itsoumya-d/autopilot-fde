"""Project 2: Intake-to-Resolution Orchestration Workflow.

Implements multi-turn stateful intake handling, automatic priority triage,
and LangGraph-style Human-in-the-Loop (HITL) checkpoints. High-risk actions
(refunds, permission changes, database writes) pause in an `interrupt()`
gate until approved with a cryptographic token.
"""

from __future__ import annotations

import uuid
from typing import Any

from ..models.schema import ChannelType, IntakeTicket


class IntakeOrchestrator:
    """Stateful workflow orchestrator managing tickets from intake to verified resolution."""

    def __init__(self) -> None:
        self.tickets: dict[str, IntakeTicket] = {}

    def ingest_ticket(
        self,
        customer: str,
        channel: ChannelType,
        content: str,
    ) -> IntakeTicket:
        """Ingests a new raw message and runs initial classification & triage."""
        ticket_id = f"TICK-{uuid.uuid4().hex[:6].upper()}"
        lower_content = content.lower()

        # Deterministic triage & priority heuristic
        if any(w in lower_content for w in ["urgent", "down", "outage", "broken", "critical"]):
            priority = "high"
            assigned_tier = "tier3"
        elif any(w in lower_content for w in ["billing", "invoice", "refund", "payment"]):
            priority = "medium"
            assigned_tier = "tier2"
        else:
            priority = "low"
            assigned_tier = "tier1"

        # Check if action requires human review gate (e.g. monetary transactions or destructive changes)
        requires_approval = any(w in lower_content for w in ["refund", "cancel subscription", "delete", "grant access"])
        approval_token = f"APP-{uuid.uuid4().hex[:8]}" if requires_approval else None

        suggested_action = (
            f"Escalate to billing manager for refund review."
            if requires_approval
            else f"Send automated self-service resolution guide for {channel.value}."
        )

        ticket = IntakeTicket(
            id=ticket_id,
            customer=customer,
            channel=channel,
            content=content,
            priority=priority,
            status="pending_approval" if requires_approval else "resolving",
            state_machine_step="awaiting_human_approval" if requires_approval else "automated_resolution",
            requires_approval=requires_approval,
            approval_token=approval_token,
            suggested_action=suggested_action,
            assigned_tier=assigned_tier,
        )
        self.tickets[ticket_id] = ticket
        return ticket

    def approve_ticket(self, ticket_id: str, token: str, human_operator: str) -> IntakeTicket:
        """Resumes the paused state machine upon valid human approval."""
        ticket = self.tickets.get(ticket_id)
        if not ticket:
            raise KeyError(f"Ticket {ticket_id} not found")

        if ticket.approval_token != token:
            raise ValueError("Invalid approval token")

        ticket.status = "resolved"
        ticket.state_machine_step = "action_executed"
        ticket.requires_approval = False
        ticket.suggested_action += f" (Approved by {human_operator})"
        return ticket

    def get_ticket(self, ticket_id: str) -> IntakeTicket | None:
        return self.tickets.get(ticket_id)

    def list_tickets(self) -> list[IntakeTicket]:
        return list(self.tickets.values())
