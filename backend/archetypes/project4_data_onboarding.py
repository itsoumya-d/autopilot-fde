"""Project 4: Customer Data Onboarding Pipeline.

Automates the messy reality of enterprise data ingestion: incoming client CSVs
have mismatched column names, dirty formats, missing values, and corrupted data.
This engine performs fuzzy schema reconciliation, column normalization, and
isolates unprocessable rows into an actionable Quarantine Dead-Letter Queue (DLQ).
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from ..models.schema import OnboardingBatchReport, OnboardingRow


class DataOnboardingPipeline:
    """Ingests dirty customer tabular data, reconciles schema, and manages Quarantine DLQ."""

    CANONICAL_SCHEMA = {
        "customer_id": [r"cust.*id", r"client.*id", r"user.*id", r"id"],
        "full_name": [r"name", r"customer.*name", r"full.*name", r"contact"],
        "email": [r"email", r"e-mail", r"mail.*addr"],
        "annual_spend": [r"spend", r"revenue", r"amount", r"arr", r"val"],
    }

    @classmethod
    def match_column(cls, raw_col: str) -> str | None:
        """Fuzzy matches an incoming raw header against the canonical schema regexes."""
        clean_col = raw_col.strip().lower().replace("_", "").replace(" ", "").replace("-", "")
        for canonical, patterns in cls.CANONICAL_SCHEMA.items():
            for pat in patterns:
                if re.search(pat, raw_col.lower()) or re.search(pat, clean_col):
                    return canonical
        return None

    @classmethod
    def process_batch(cls, filename: str, rows: list[dict[str, Any]]) -> tuple[OnboardingBatchReport, list[OnboardingRow]]:
        """Processes a batch of raw customer rows, reconciling headers and quarantining dirty rows."""
        batch_id = f"BATCH-{uuid.uuid4().hex[:6].upper()}"
        if not rows:
            return (
                OnboardingBatchReport(
                    batch_id=batch_id,
                    source_filename=filename,
                    total_rows=0,
                    accepted_rows=0,
                    quarantined_rows=0,
                    schema_match_pct=0.0,
                    detected_headers=[],
                    mapped_headers={},
                ),
                [],
            )

        detected_headers = list(rows[0].keys())
        mapped_headers: dict[str, str] = {}
        for h in detected_headers:
            matched = cls.match_column(h)
            if matched:
                mapped_headers[h] = matched

        schema_match_pct = (len(mapped_headers) / len(cls.CANONICAL_SCHEMA)) * 100.0

        processed_rows: list[OnboardingRow] = []
        accepted_count = 0
        quarantined_count = 0

        for idx, r in enumerate(rows, 1):
            mapped_data: dict[str, Any] = {}
            for raw_k, raw_v in r.items():
                target_k = mapped_headers.get(raw_k, raw_k)
                mapped_data[target_k] = raw_v

            # Validation constraints
            is_valid = True
            quarantine_reason = None

            # Email check
            email_val = str(mapped_data.get("email", ""))
            if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email_val):
                is_valid = False
                quarantine_reason = f"Malformed email address: '{email_val}'"

            # Spend check
            try:
                spend_val = float(mapped_data.get("annual_spend", 0))
                if spend_val < 0:
                    is_valid = False
                    quarantine_reason = f"Negative annual spend: {spend_val}"
            except (ValueError, TypeError):
                is_valid = False
                quarantine_reason = f"Invalid numeric spend value: {mapped_data.get('annual_spend')}"

            # ID check
            if not mapped_data.get("customer_id"):
                is_valid = False
                quarantine_reason = "Missing mandatory customer_id"

            if is_valid:
                accepted_count += 1
            else:
                quarantined_count += 1

            processed_rows.append(
                OnboardingRow(
                    row_number=idx,
                    raw_data=r,
                    mapped_data=mapped_data,
                    is_valid=is_valid,
                    quarantine_reason=quarantine_reason,
                )
            )

        report = OnboardingBatchReport(
            batch_id=batch_id,
            source_filename=filename,
            total_rows=len(rows),
            accepted_rows=accepted_count,
            quarantined_rows=quarantined_count,
            schema_match_pct=round(min(100.0, schema_match_pct), 1),
            detected_headers=detected_headers,
            mapped_headers=mapped_headers,
        )

        return report, processed_rows
