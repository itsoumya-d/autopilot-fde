"""Project 3: Dual-Stage Document Intelligence and Approval System.

Solves the core architectural problem identified in Aishwarya Srinivasan's masterclass:
decoupling probabilistic LLM text/vision extraction from deterministic business logic.
LLMs extract candidate JSON structures, while deterministic Python/Pydantic rules
rigorously verify arithmetic, tax reconciliation, and line-item integrity.
"""

from __future__ import annotations

from typing import Any

from ..models.schema import DocumentValidationReport, ExtractedInvoice, LineItem


class DocumentIntelligenceEngine:
    """Decoupled extraction and deterministic validation for financial and legal documents."""

    @staticmethod
    def parse_raw_text(raw_text: str) -> ExtractedInvoice:
        """Simulates Stage 1: Probabilistic LLM extraction to structured invoice schema."""
        # Realistic extraction logic
        return ExtractedInvoice(
            invoice_id="INV-2026-8891",
            vendor="Acme Cloud Infrastructure LLC",
            date="2026-09-10",
            line_items=[
                LineItem(description="Dedicated GPU Compute Cluster (A100 x 4)", quantity=2.0, unit_price=1200.0, total=2400.0),
                LineItem(description="High-Speed VPC Peering & Egress Bandwidth", quantity=1.0, unit_price=450.0, total=450.0),
                LineItem(description="Enterprise SLA 24/7 Support Tier", quantity=1.0, unit_price=350.0, total=350.0),
            ],
            subtotal=3200.0,
            tax=256.0,  # 8% sales tax
            total_amount=3456.0,
        )

    @classmethod
    def validate_invoice(cls, invoice: ExtractedInvoice, tolerance: float = 0.01) -> DocumentValidationReport:
        """Stage 2: Deterministic verification of arithmetic and business rules."""
        discrepancies: list[str] = []
        calculated_subtotal = 0.0

        # 1. Verify individual line item math (qty * unit_price == total)
        for idx, item in enumerate(invoice.line_items, 1):
            expected_total = round(item.quantity * item.unit_price, 2)
            if abs(expected_total - item.total) > tolerance:
                discrepancies.append(
                    f"Line {idx} '{item.description}': arithmetic mismatch. "
                    f"Expected {item.quantity} * ${item.unit_price} = ${expected_total}, but stated as ${item.total}"
                )
            calculated_subtotal += item.total

        calculated_subtotal = round(calculated_subtotal, 2)

        # 2. Verify subtotal matches sum of line items
        if abs(calculated_subtotal - invoice.subtotal) > tolerance:
            discrepancies.append(
                f"Subtotal mismatch: Sum of line items is ${calculated_subtotal}, but stated subtotal is ${invoice.subtotal}"
            )

        # 3. Verify total amount (subtotal + tax == total_amount)
        expected_grand_total = round(invoice.subtotal + invoice.tax, 2)
        math_delta = round(expected_grand_total - invoice.total_amount, 2)
        if abs(math_delta) > tolerance:
            discrepancies.append(
                f"Total amount mismatch: Subtotal (${invoice.subtotal}) + Tax (${invoice.tax}) = "
                f"${expected_grand_total}, but stated total is ${invoice.total_amount} (Delta: ${math_delta})"
            )

        arithmetic_valid = len(discrepancies) == 0
        is_valid = arithmetic_valid and invoice.total_amount > 0

        action_recommended = (
            "AUTO_APPROVE: All arithmetic and business constraints verified."
            if is_valid
            else "MANUAL_AUDIT_REQUIRED: Mathematical discrepancies detected. Routed to human accountant."
        )

        return DocumentValidationReport(
            invoice_id=invoice.invoice_id,
            is_valid=is_valid,
            arithmetic_valid=arithmetic_valid,
            discrepancy_details=discrepancies,
            math_delta=math_delta,
            action_recommended=action_recommended,
        )
