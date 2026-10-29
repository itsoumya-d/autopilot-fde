"""Tenant-safe enterprise data ingestion.

This module provides a deterministic, dependency-free ingestion core for
multi-source data platforms. It validates record envelopes, enforces tenant
isolation, retries transient sink failures with exponential backoff, records
dead letters, and deduplicates successful writes by an idempotency key.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol


class IngestionError(ValueError):
    """Base error for invalid ingestion configuration or records."""


class SchemaValidationError(IngestionError):
    """Raised when a record does not match the ingestion envelope."""


class TenantIsolationError(IngestionError):
    """Raised when a record claims a tenant different from the batch tenant."""


@dataclass(frozen=True)
class RecordEnvelope:
    tenant_id: str
    source_id: str
    record_id: str
    version: int
    payload: dict[str, Any]
    idempotency_key: str


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.05
    max_delay_seconds: float = 1.0

    def delay_for(self, attempt: int) -> float:
        """Return capped exponential backoff for a 1-based attempt number."""
        if attempt < 1:
            raise ValueError("attempt must be >= 1")
        return min(self.max_delay_seconds, self.base_delay_seconds * (2 ** (attempt - 1)))


@dataclass
class IngestionResult:
    accepted: int = 0
    duplicates: int = 0
    failed: int = 0
    dead_letters: list[dict[str, Any]] = field(default_factory=list)


class Sink(Protocol):
    """Destination that receives validated record envelopes."""

    def write(self, envelope: RecordEnvelope) -> None: ...


class DataPlatformIngestor:
    """Ingest records into a sink with idempotency and tenant isolation."""

    def __init__(
        self,
        sink: Sink,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._sink = sink
        self._retry = retry_policy or RetryPolicy()
        self._sleep = sleep
        self._seen: set[str] = set()

    def ingest(
        self, tenant_id: str, source_id: str, records: Iterable[dict[str, Any]]
    ) -> IngestionResult:
        """Validate, deduplicate, and write records for one tenant/source."""
        if not tenant_id or not source_id:
            raise IngestionError("tenant_id and source_id are required")

        result = IngestionResult()
        for index, record in enumerate(records):
            try:
                envelope = self._build_envelope(tenant_id, source_id, record)
            except IngestionError as exc:
                result.failed += 1
                result.dead_letters.append(
                    self._dead_letter(tenant_id, source_id, index, record, str(exc))
                )
                continue

            if envelope.idempotency_key in self._seen:
                result.duplicates += 1
                continue

            ok, error = self._write_with_retry(envelope)
            if ok:
                self._seen.add(envelope.idempotency_key)
                result.accepted += 1
            else:
                result.failed += 1
                result.dead_letters.append(
                    self._dead_letter(
                        tenant_id,
                        source_id,
                        index,
                        record,
                        error or "sink write failed",
                    )
                )
        return result

    def _build_envelope(
        self, tenant_id: str, source_id: str, record: dict[str, Any]
    ) -> RecordEnvelope:
        if not isinstance(record, dict):
            raise SchemaValidationError("record must be an object")

        record_tenant = record.get("tenant_id", tenant_id)
        if record_tenant != tenant_id:
            raise TenantIsolationError("record tenant does not match batch tenant")

        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id.strip():
            raise SchemaValidationError("record id is required")

        payload = record.get("payload", {})
        if not isinstance(payload, dict):
            raise SchemaValidationError("payload must be an object")

        version = record.get("version", 1)
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise SchemaValidationError("version must be a positive integer")

        key = f"{tenant_id}:{source_id}:{record_id}:{version}"
        return RecordEnvelope(
            tenant_id=tenant_id,
            source_id=source_id,
            record_id=record_id,
            version=version,
            payload=payload,
            idempotency_key=key,
        )

    def _write_with_retry(self, envelope: RecordEnvelope) -> tuple[bool, str | None]:
        last_error: str | None = None
        for attempt in range(1, self._retry.max_attempts + 1):
            try:
                self._sink.write(envelope)
                return True, None
            except Exception as exc:  # sink failures are isolated per record
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < self._retry.max_attempts:
                    self._sleep(self._retry.delay_for(attempt))
        return False, last_error

    @staticmethod
    def _dead_letter(
        tenant_id: str,
        source_id: str,
        index: int,
        record: Any,
        error: str,
    ) -> dict[str, Any]:
        record_id = record.get("id") if isinstance(record, dict) else None
        return {
            "tenant_id": tenant_id,
            "source_id": source_id,
            "index": index,
            "record_id": record_id,
            "error": error,
        }
