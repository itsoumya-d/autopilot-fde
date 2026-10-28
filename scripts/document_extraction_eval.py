"""Evaluate document-extraction outputs on accuracy, latency, and cost per call."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import ceil

from backend.archetypes.project3_document_intel import DocumentIntelligenceEngine
from backend.models.schema import ExtractedInvoice

Extractor = Callable[[str], ExtractedInvoice]


@dataclass(frozen=True)
class ExtractionCase:
    case_id: str
    raw_text: str
    expected: ExtractedInvoice


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    schema_valid: bool
    field_matches: dict[str, bool]
    latency_ms: float
    cost_usd: float


@dataclass(frozen=True)
class EvalSummary:
    case_count: int
    schema_validity_rate: float
    field_accuracy: float
    exact_match_rate: float
    total_cost_usd: float
    p50_latency_ms: float
    p95_latency_ms: float

    def as_dict(self) -> dict[str, object]:
        return {
            "case_count": self.case_count,
            "schema_validity_rate": self.schema_validity_rate,
            "field_accuracy": self.field_accuracy,
            "exact_match_rate": self.exact_match_rate,
            "total_cost_usd": self.total_cost_usd,
            "p50_latency_ms": self.p50_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
        }


def invoice_fields(invoice: ExtractedInvoice) -> dict[str, object]:
    return {
        "invoice_id": invoice.invoice_id,
        "vendor": invoice.vendor,
        "date": invoice.date,
        "line_item_count": len(invoice.line_items),
        "subtotal": invoice.subtotal,
        "tax": invoice.tax,
        "total_amount": invoice.total_amount,
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, ceil(percentile * len(ordered)) - 1)
    return ordered[min(index, len(ordered) - 1)]


def evaluate(
    cases: Sequence[ExtractionCase],
    extractor: Extractor,
    cost_per_call_usd: float = 0.0,
) -> EvalSummary:
    results: list[CaseResult] = []

    for case in cases:
        started = time.perf_counter()
        actual: ExtractedInvoice | None
        schema_valid = True
        try:
            actual = extractor(case.raw_text)
        except Exception:
            actual = None
            schema_valid = False
        latency_ms = (time.perf_counter() - started) * 1000

        expected_fields = invoice_fields(case.expected)
        if actual is None:
            matches = {key: False for key in expected_fields}
        else:
            actual_fields = invoice_fields(actual)
            matches = {key: actual_fields.get(key) == value for key, value in expected_fields.items()}

        results.append(
            CaseResult(
                case_id=case.case_id,
                schema_valid=schema_valid,
                field_matches=matches,
                latency_ms=latency_ms,
                cost_usd=cost_per_call_usd,
            )
        )

    if not results:
        return EvalSummary(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    total_fields = sum(len(result.field_matches) for result in results)
    matched_fields = sum(sum(result.field_matches.values()) for result in results)
    exact_matches = sum(all(result.field_matches.values()) for result in results)
    latencies = [result.latency_ms for result in results]

    return EvalSummary(
        case_count=len(results),
        schema_validity_rate=sum(result.schema_valid for result in results) / len(results),
        field_accuracy=matched_fields / total_fields,
        exact_match_rate=exact_matches / len(results),
        total_cost_usd=sum(result.cost_usd for result in results),
        p50_latency_ms=_percentile(latencies, 0.50),
        p95_latency_ms=_percentile(latencies, 0.95),
    )


def synthetic_cases() -> list[ExtractionCase]:
    expected = DocumentIntelligenceEngine.parse_raw_text("")
    return [
        ExtractionCase("invoice-clean", "Synthetic clean invoice", expected),
        ExtractionCase("invoice-multiline", "Synthetic invoice with wrapped line items", expected),
        ExtractionCase("invoice-noisy-ocr", "Synthetic invoice with OCR noise", expected),
    ]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the summary as JSON.")
    parser.add_argument("--cost-per-call", type=float, default=0.0, help="Estimated USD cost per extraction.")
    args = parser.parse_args(argv)

    summary = evaluate(
        synthetic_cases(),
        DocumentIntelligenceEngine.parse_raw_text,
        cost_per_call_usd=args.cost_per_call,
    )

    if args.json:
        print(json.dumps(summary.as_dict(), indent=2, sort_keys=True))
    else:
        print("| Metric | Value |")
        print("|---|---:|")
        print(f"| Cases | {summary.case_count} |")
        print(f"| Schema validity | {summary.schema_validity_rate:.2%} |")
        print(f"| Field accuracy | {summary.field_accuracy:.2%} |")
        print(f"| Exact match | {summary.exact_match_rate:.2%} |")
        print(f"| p50 latency | {summary.p50_latency_ms:.3f} ms |")
        print(f"| p95 latency | {summary.p95_latency_ms:.3f} ms |")
        print(f"| Total cost | ${summary.total_cost_usd:.4f} |")

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
