"""Enterprise agent execution runtime with idempotency keys and write-ahead log (WAL) state persistence."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from collections.abc import Callable

logger = logging.getLogger(__name__)


class AgentRuntimeError(Exception):
    """Base exception for agent runtime errors."""


class IdempotencyViolationError(AgentRuntimeError):
    """Raised when an idempotency conflict occurs."""


class PolicyRejectionError(AgentRuntimeError):
    """Raised when an action violates safety or enterprise policy."""


class ToolExecutionError(AgentRuntimeError):
    """Raised when a registered tool fails during execution."""


@dataclass
class AgentStep:
    step_id: str
    tool_name: str
    inputs: dict[str, Any]
    idempotency_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolDefinition:
    name: str
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    schema: dict[str, type] | None = None
    policy_check: Callable[[AgentStep], bool] | None = None


class AgentExecutionRuntime:
    """Enterprise execution runtime for multi-step agent actions with WAL state persistence and idempotency."""

    def __init__(self, wal_path: Path | str | None = None) -> None:
        self.wal_path = Path(wal_path) if wal_path else None
        self._tools: dict[str, ToolDefinition] = {}
        self._idempotency_cache: dict[str, dict[str, Any]] = {}
        self._traces: list[dict[str, Any]] = []

        if self.wal_path and self.wal_path.exists():
            self._recover_from_wal()

    def register_tool(
        self,
        name: str,
        handler: Callable[[dict[str, Any]], dict[str, Any]],
        schema: dict[str, type] | None = None,
        policy_check: Callable[[AgentStep], bool] | None = None,
    ) -> None:
        """Register a tool handler with optional schema and policy guard."""
        self._tools[name] = ToolDefinition(
            name=name,
            handler=handler,
            schema=schema,
            policy_check=policy_check,
        )

    def is_idempotency_key_executed(self, key: str) -> bool:
        """Return True if the idempotency key has already been successfully processed."""
        return key in self._idempotency_cache

    def execute_step(self, step: AgentStep) -> dict[str, Any]:
        """Execute an agent step with idempotency checks, policy validation, and WAL journaling."""
        # 1. Idempotency check: return cached result without re-executing
        if step.idempotency_key and step.idempotency_key in self._idempotency_cache:
            logger.info("Idempotent replay for key=%s step_id=%s", step.idempotency_key, step.step_id)
            return self._idempotency_cache[step.idempotency_key]

        tool = self._tools.get(step.tool_name)
        if not tool:
            raise ToolExecutionError(f"Tool {step.tool_name!r} is not registered in runtime.")

        # 2. Schema validation
        if tool.schema:
            for param, expected_type in tool.schema.items():
                if param not in step.inputs:
                    raise ToolExecutionError(f"Missing required parameter {param!r} for tool {step.tool_name!r}")
                if not isinstance(step.inputs[param], expected_type):
                    raise ToolExecutionError(
                        f"Parameter {param!r} expected {expected_type.__name__}, got {type(step.inputs[param]).__name__}"
                    )

        # 3. Policy evaluation
        if tool.policy_check and not tool.policy_check(step):
            raise PolicyRejectionError(f"Step {step.step_id!r} rejected by enterprise safety policy.")

        # 4. Tool execution with timing instrumentation
        start_time = time.perf_counter()
        try:
            output = tool.handler(step.inputs)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            status = "SUCCESS"
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            self._record_trace(step, status="FAILED", duration_ms=duration_ms, error=str(exc))
            raise ToolExecutionError(f"Tool {step.tool_name!r} failed: {exc}") from exc

        # 5. Idempotency record & WAL commit
        if step.idempotency_key:
            self._idempotency_cache[step.idempotency_key] = output
            if self.wal_path:
                self._append_wal(step.idempotency_key, output)

        self._record_trace(step, status=status, duration_ms=duration_ms, output=output)
        return output

    def _record_trace(
        self,
        step: AgentStep,
        status: str,
        duration_ms: float,
        output: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self._traces.append({
            "step_id": step.step_id,
            "tool_name": step.tool_name,
            "inputs": step.inputs,
            "status": status,
            "duration_ms": duration_ms,
            "output": output,
            "error": error,
            "timestamp": time.time(),
        })

    def get_traces(self) -> list[dict[str, Any]]:
        return list(self._traces)

    def _append_wal(self, idempotency_key: str, output: dict[str, Any]) -> None:
        if not self.wal_path:
            return
        self.wal_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"key": idempotency_key, "output": output, "recorded_at": time.time()}
        with open(self.wal_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def _recover_from_wal(self) -> None:
        if not self.wal_path or not self.wal_path.exists():
            return
        with open(self.wal_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    self._idempotency_cache[entry["key"]] = entry["output"]
                except (json.JSONDecodeError, KeyError):
                    continue
