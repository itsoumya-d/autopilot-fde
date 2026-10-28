"""Document-extraction eval harness: accuracy, schema validity, latency, and cost."""

import json

from backend.archetypes.project3_document_intel import DocumentIntelligenceEngine
from scripts.document_extraction_eval import (
    ExtractionCase,
    evaluate,
    main,
    synthetic_cases,
)


def test_fixture_extractor_scores_perfectly() -> None:
    summary = evaluate(synthetic_cases(), DocumentIntelligenceEngine.parse_raw_text, cost_per_call_usd=0.01)

    assert summary.case_count == 3
    assert summary.schema_validity_rate == 1.0
    assert summary.field_accuracy == 1.0
    assert summary.exact_match_rate == 1.0
    assert summary.total_cost_usd == 0.03
    assert summary.p50_latency_ms >= 0
    assert summary.p95_latency_ms >= summary.p50_latency_ms


def test_wrong_field_lowers_accuracy_and_exact_match() -> None:
    def wrong_vendor(raw_text: str):
        invoice = DocumentIntelligenceEngine.parse_raw_text(raw_text)
        return invoice.model_copy(update={"vendor": "Wrong Vendor"})

    summary = evaluate(synthetic_cases(), wrong_vendor)

    assert summary.schema_validity_rate == 1.0
    assert summary.field_accuracy < 1.0
    assert summary.exact_match_rate == 0.0


def test_extraction_failure_counts_as_invalid_schema() -> None:
    def fail(_raw_text: str):
        raise ValueError("provider timeout")

    summary = evaluate(synthetic_cases(), fail)

    assert summary.schema_validity_rate == 0.0
    assert summary.field_accuracy == 0.0
    assert summary.exact_match_rate == 0.0


def test_empty_case_set_returns_zeroes() -> None:
    summary = evaluate([], DocumentIntelligenceEngine.parse_raw_text)

    assert summary.case_count == 0
    assert summary.schema_validity_rate == 0.0
    assert summary.field_accuracy == 0.0
    assert summary.exact_match_rate == 0.0
    assert summary.total_cost_usd == 0.0
    assert summary.p50_latency_ms == 0.0
    assert summary.p95_latency_ms == 0.0


def test_cli_json_output(capsys) -> None:
    assert main(["--json", "--cost-per-call", "0.01"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["case_count"] == 3
    assert payload["schema_validity_rate"] == 1.0
    assert payload["field_accuracy"] == 1.0
    assert payload["total_cost_usd"] == 0.03


def test_cli_markdown_output(capsys) -> None:
    assert main([]) == 0

    output = capsys.readouterr().out
    assert "| Field accuracy | 100.00% |" in output
    assert "| p50 latency |" in output
    assert "| Total cost |" in output


def test_case_id_is_preserved() -> None:
    case = ExtractionCase(
        case_id="single-case",
        raw_text="Synthetic invoice",
        expected=DocumentIntelligenceEngine.parse_raw_text(""),
    )

    summary = evaluate([case], DocumentIntelligenceEngine.parse_raw_text)

    assert summary.case_count == 1
    assert summary.exact_match_rate == 1.0
