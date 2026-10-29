"""Tests for tenant-safe enterprise data ingestion."""

from __future__ import annotations

from typing import Any

import pytest

from backend.ingestion.data_platform import (
    DataPlatformIngestor,
    IngestionError,
    RetryPolicy,
    SchemaValidationError,
    TenantIsolationError,
)


class RecordingSink:
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.written: list[Any] = []

    def write(self, envelope: Any) -> None:
        if self.failures:
            self.failures -= 1
            raise TimeoutError("transient")
        self.written.append(envelope)


def test_ingests_and_deduplicates_successful_records() -> None:
    sink = RecordingSink()
    ingestor = DataPlatformIngestor(sink)

    first = ingestor.ingest(
        "tenant-a", "crm", [{"id": "1", "payload": {"name": "Ada"}}, {"id": "2"}]
    )
    second = ingestor.ingest("tenant-a", "crm", [{"id": "1"}, {"id": "2"}])

    assert first.accepted == 2
    assert first.failed == 0
    assert second.duplicates == 2
    assert len(sink.written) == 2
    assert sink.written[0].idempotency_key == "tenant-a:crm:1:1"


def test_retries_transient_failures_with_backoff() -> None:
    sink = RecordingSink(failures=2)
    delays: list[float] = []
    ingestor = DataPlatformIngestor(
        sink, retry_policy=RetryPolicy(max_attempts=3), sleep=delays.append
    )

    result = ingestor.ingest("tenant-a", "erp", [{"id": "1"}])

    assert result.accepted == 1
    assert result.failed == 0
    assert delays == [0.05, 0.1]


def test_dead_letters_after_retry_exhaustion() -> None:
    sink = RecordingSink(failures=3)
    delays: list[float] = []
    ingestor = DataPlatformIngestor(
        sink, retry_policy=RetryPolicy(max_attempts=3), sleep=delays.append
    )

    result = ingestor.ingest("tenant-a", "erp", [{"id": "bad"}])

    assert result.accepted == 0
    assert result.failed == 1
    assert result.dead_letters[0]["record_id"] == "bad"
    assert "TimeoutError" in result.dead_letters[0]["error"]
    assert delays == [0.05, 0.1]


def test_rejects_invalid_records_and_cross_tenant_records() -> None:
    sink = RecordingSink()
    ingestor = DataPlatformIngestor(sink)
    records: list[Any] = [
        {"id": ""},
        {"id": "1", "payload": []},
        {"id": "1", "version": 0},
        {"id": "1", "version": True},
        {"id": "1", "tenant_id": "tenant-b"},
        "not-an-object",
    ]

    result = ingestor.ingest("tenant-a", "crm", records)

    assert result.failed == 6
    assert len(result.dead_letters) == 6
    assert result.dead_letters[0]["error"] == "record id is required"
    assert "payload must be an object" in result.dead_letters[1]["error"]
    assert "version must be a positive integer" in result.dead_letters[2]["error"]
    assert "version must be a positive integer" in result.dead_letters[3]["error"]
    assert "record tenant does not match batch tenant" in result.dead_letters[4]["error"]
    assert result.dead_letters[5]["record_id"] is None
    assert sink.written == []


def test_version_is_part_of_idempotency_key() -> None:
    sink = RecordingSink()
    ingestor = DataPlatformIngestor(sink)

    result = ingestor.ingest(
        "tenant-a", "crm", [{"id": "1"}, {"id": "1", "version": 2}]
    )

    assert result.accepted == 2
    assert [item.version for item in sink.written] == [1, 2]


def test_failed_record_is_not_marked_seen() -> None:
    sink = RecordingSink(failures=3)
    ingestor = DataPlatformIngestor(
        sink, retry_policy=RetryPolicy(max_attempts=3), sleep=lambda _: None
    )

    first = ingestor.ingest("tenant-a", "crm", [{"id": "1"}])
    second = ingestor.ingest("tenant-a", "crm", [{"id": "1"}])

    assert first.failed == 1
    assert second.accepted == 1


def test_empty_batch_and_missing_scope() -> None:
    ingestor = DataPlatformIngestor(RecordingSink())

    assert ingestor.ingest("tenant-a", "crm", []).accepted == 0
    with pytest.raises(IngestionError):
        ingestor.ingest("", "crm", [])
    with pytest.raises(IngestionError):
        ingestor.ingest("tenant-a", "", [])


def test_retry_policy_caps_delay_and_rejects_bad_attempt() -> None:
    policy = RetryPolicy(base_delay_seconds=0.5, max_delay_seconds=1.0)

    assert policy.delay_for(1) == 0.5
    assert policy.delay_for(2) == 1.0
    assert policy.delay_for(10) == 1.0
    with pytest.raises(ValueError):
        policy.delay_for(0)


def test_error_types_are_ingestion_errors() -> None:
    assert issubclass(SchemaValidationError, IngestionError)
    assert issubclass(TenantIsolationError, IngestionError)
