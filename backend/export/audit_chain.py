"""Tamper-evident audit chains for agent actions.

Every deployed agent already records an ordered audit trail
(``agent.metrics["audit"]``). This module seals that trail into a
**hash chain**: each event carries the SHA-256 of the canonical JSON of its
predecessor's record, so any later edit, deletion, or reordering is
detectable in O(n) by :func:`verify_chain`.

Posture this supports: EU AI Act Article 12-style record-keeping where an
inspector must be able to retrieve explainable action history and prove it
was not altered after the fact. The chain is deterministic and offline — no
key material, no trusted timestamp authority; tamper-evidence, not signing.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

GENESIS_PREV_HASH = "0" * 64


def _canonical(event: dict[str, Any]) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"), default=str)


def _digest(prev_hash: str, event: dict[str, Any]) -> str:
    return hashlib.sha256(f"{prev_hash}{_canonical(event)}".encode()).hexdigest()


def chain_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Seal an ordered audit trail into chained records.

    The original event fields are preserved untouched under ``event``;
    integrity fields live beside them so consumers can ignore the chain.
    """
    chained: list[dict[str, Any]] = []
    prev_hash = GENESIS_PREV_HASH
    for sequence, event in enumerate(events):
        record_hash = _digest(prev_hash, event)
        chained.append({
            "seq": sequence,
            "prev_hash": prev_hash,
            "hash": record_hash,
            "event": event,
        })
        prev_hash = record_hash
    return chained


def verify_chain(chained: list[dict[str, Any]]) -> tuple[bool, str | None]:
    """Recompute the chain; return ``(ok, first_failure_reason)``.

    Detects tampering with event contents, hashes, ordering (via seq), and
    truncation is detectable by whoever holds a later head hash.
    """
    prev_hash = GENESIS_PREV_HASH
    for index, record in enumerate(chained):
        if record.get("seq") != index:
            return False, f"seq mismatch at position {index}"
        if record.get("prev_hash") != prev_hash:
            return False, f"prev_hash mismatch at position {index}"
        expected = _digest(prev_hash, record.get("event", {}))
        if record.get("hash") != expected:
            return False, f"hash mismatch at position {index} (event tampered)"
        prev_hash = record["hash"]
    return True, None


def export_agent_chain(
    agent_id: str,
    audit_events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Full export envelope for one agent: chained events + head hash."""
    chained = chain_events(audit_events)
    return {
        "agent_id": agent_id,
        "exported_at": datetime.now(UTC).isoformat(),
        "algorithm": "sha256-canonical-json",
        "genesis_prev_hash": GENESIS_PREV_HASH,
        "head_hash": chained[-1]["hash"] if chained else GENESIS_PREV_HASH,
        "event_count": len(chained),
        "events": chained,
    }
