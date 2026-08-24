"""Execution guards for generated-agent tool dispatch (v0.6 Governed Autonomy).

Four controls, one module:

- **Per-agent quotas** — sliding-window limit per agent id (in-process,
  sized for the single-process self-hosted control plane).
- **Idempotency keys** — replay-safe retries for exactly-once semantics.
  Uses a dedicated synchronous SQLite handle because generated LangGraph
  nodes call ``execute_agent_step`` synchronously; the main repository stays
  async (aiosqlite). Same workspace file, separate concern, WAL-friendly.
- **Dead-letter queue** — failed INTERNAL_ACTION webhooks are preserved with
  full context for human review instead of vanishing into a stack trace.
- **Tool-governance allowlist** — an optional policy file restricts which
  webhook hosts internal actions may touch. No file = unchanged behavior;
  a file with hosts = deny-by-default for anything not listed.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..security import RateLimiter  # noqa: F401 - re-exported for callers

_GUARD_DB_ENV = "AUTOPILOT_GUARD_DB"
_POLICY_ENV = "AUTOPILOT_TOOLS_POLICY"

_agent_limiter = RateLimiter()
_policy_cache: dict[str, Any] = {"path": None, "mtime": None, "hosts": None}
_sqlite_lock = threading.Lock()
_connection: sqlite3.Connection | None = None


def _db_path() -> Path:
    """Guard store location; defaults beside the main workspace, never inside
    a caller's temp dir (a stale path there must not break guard writes)."""
    override = os.getenv(_GUARD_DB_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    env_workspace = os.getenv("AUTOPILOT_DB_PATH", "").strip()
    if env_workspace:
        candidate = Path(env_workspace).expanduser().parent
        if candidate.exists():
            return candidate / "autopilot-guards.db"
    return Path(__file__).resolve().parents[1] / "autopilot.db"


def _conn() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        with _sqlite_lock:
            if _connection is None:
                conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS idempotency (
                        key TEXT PRIMARY KEY,
                        result_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )""")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS dead_letters (
                        id TEXT PRIMARY KEY,
                        agent_id TEXT,
                        step_name TEXT NOT NULL,
                        error TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        created_at TEXT NOT NULL,
                        reviewed_by TEXT,
                        review_notes TEXT
                    )""")
                conn.commit()
                _connection = conn
    return _connection


def close_guards() -> None:
    global _connection
    with _sqlite_lock:
        if _connection is not None:
            _connection.close()
            _connection = None


# ── Per-agent quotas ────────────────────────────────────────────────────────

class AgentQuotaExceeded(RuntimeError):
    pass


def check_agent_quota(agent_id: str | None) -> None:
    """Sliding-window action budget per deployed branch."""
    if not agent_id:
        return
    try:
        _agent_limiter.check(f"agent:{agent_id}")
    except Exception as error:  # limiter raises HTTPException (FastAPI-coupled)
        raise AgentQuotaExceeded(str(getattr(error, "detail", error))) from error


# ── Idempotency ─────────────────────────────────────────────────────────────

def get_idempotent_result(key: str) -> dict[str, Any] | None:
    row = _conn().execute(
        "SELECT result_json FROM idempotency WHERE key = ?", (key,)
    ).fetchone()
    return json.loads(row[0]) if row else None


def record_idempotent(key: str, result: dict[str, Any]) -> bool:
    """Store a result under the key; False when somebody else already did."""
    cursor = _conn().execute(
        "INSERT OR IGNORE INTO idempotency (key, result_json, created_at) VALUES (?, ?, ?)",
        (key, json.dumps(result, default=str), datetime.now(UTC).isoformat()),
    )
    _conn().commit()
    return cursor.rowcount > 0


# ── Dead-letter queue ───────────────────────────────────────────────────────

def dead_letter_push(agent_id: str | None, step_name: str,
                     error: str, payload: dict[str, Any]) -> str:
    from uuid import uuid4

    entry_id = f"dlq-{uuid4().hex[:10]}"
    _conn().execute(
        """INSERT INTO dead_letters
           (id, agent_id, step_name, error, payload_json, status, created_at)
           VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
        (entry_id, agent_id, step_name, error,
         json.dumps(payload, default=str), datetime.now(UTC).isoformat()),
    )
    _conn().commit()
    return entry_id


def dead_letter_list(status: str = "pending") -> list[dict[str, Any]]:
    rows = _conn().execute(
        """SELECT id, agent_id, step_name, error, payload_json, status,
                  created_at, reviewed_by, review_notes
           FROM dead_letters WHERE status = ? ORDER BY created_at""",
        (status,),
    ).fetchall()
    return [
        {
            "id": r[0], "agent_id": r[1], "step_name": r[2], "error": r[3],
            "payload": json.loads(r[4]), "status": r[5], "created_at": r[6],
            "reviewed_by": r[7], "review_notes": r[8],
        }
        for r in rows
    ]


class DeadLetterNotFound(KeyError):
    pass


class DeadLetterAlreadyReviewed(RuntimeError):
    pass


def dead_letter_review(entry_id: str, reviewer: str, decision: str,
                       notes: str = "") -> dict[str, Any]:
    """Human verdict on a failed action: 'discard' or 'requeue' (audit only)."""
    if decision not in ("discard", "requeue"):
        raise ValueError("decision must be 'discard' or 'requeue'")
    row = _conn().execute(
        "SELECT status FROM dead_letters WHERE id = ?", (entry_id,)
    ).fetchone()
    if not row:
        raise DeadLetterNotFound(entry_id)
    if row[0] != "pending":
        raise DeadLetterAlreadyReviewed(entry_id)
    _conn().execute(
        """UPDATE dead_letters SET status = ?, reviewed_by = ?, review_notes = ?
           WHERE id = ?""",
        (f"reviewed:{decision}", reviewer, notes, entry_id),
    )
    _conn().commit()
    return {"id": entry_id, "status": f"reviewed:{decision}",
            "reviewed_by": reviewer}


# ── Tool-governance allowlist ───────────────────────────────────────────────

class WebhookHostNotAllowed(PermissionError):
    pass


def _policy_hosts() -> set[str] | None:
    """Allowed webhook hosts from the policy file; None when unrestricted."""
    raw_path = os.getenv(_POLICY_ENV, "").strip() or ".autopilot/tools.policy.json"
    path = Path(raw_path).expanduser()
    if not path.exists():
        return None
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    if (_policy_cache["path"], _policy_cache["mtime"]) != (str(path), mtime):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            hosts = {h.lower().lstrip("*.") for h in data.get("allowed_webhook_hosts", [])}
        except (ValueError, AttributeError):
            hosts = set()
        _policy_cache.update(path=str(path), mtime=mtime, hosts=hosts)
    return _policy_cache["hosts"]


def enforce_webhook_policy(url: str) -> None:
    """Deny-by-default when a policy file lists any hosts."""
    allowed = _policy_hosts()
    if not allowed:
        return
    host = (urlparse(url).hostname or "").lower()
    if host not in allowed and not any(host.endswith(f".{h}") for h in allowed):
        raise WebhookHostNotAllowed(
            f"Webhook host '{host}' is not in the tool-governance allowlist "
            f"({_POLICY_ENV}={raw_policy_path()}).")


def raw_policy_path() -> str:
    return os.getenv(_POLICY_ENV, "").strip() or ".autopilot/tools.policy.json"
