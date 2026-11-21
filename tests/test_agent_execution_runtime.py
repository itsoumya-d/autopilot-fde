"""Unit tests for the enterprise agent execution runtime with idempotency and WAL state persistence."""

import json
import tempfile
from pathlib import Path
import pytest

from backend.runtime.agent_execution_runtime import (
    AgentExecutionRuntime,
    AgentStep,
    IdempotencyViolationError,
    PolicyRejectionError,
    ToolExecutionError,
)


def test_tool_registration_and_execution():
    runtime = AgentExecutionRuntime()

    def multiply(args: dict) -> dict:
        return {"result": args["a"] * args["b"]}

    runtime.register_tool(
        name="multiply",
        handler=multiply,
        schema={"a": int, "b": int},
    )

    step = AgentStep(
        step_id="step-1",
        tool_name="multiply",
        inputs={"a": 6, "b": 7},
        idempotency_key="calc-order-101",
    )

    result = runtime.execute_step(step)
    assert result == {"result": 42}
    assert runtime.is_idempotency_key_executed("calc-order-101")


def test_idempotency_prevents_duplicate_execution():
    runtime = AgentExecutionRuntime()
    call_count = 0

    def process_payment(args: dict) -> dict:
        nonlocal call_count
        call_count += 1
        return {"transaction_id": f"txn_{args['invoice_id']}", "status": "completed"}

    runtime.register_tool(
        name="process_payment",
        handler=process_payment,
        schema={"invoice_id": str, "amount": float},
    )

    step = AgentStep(
        step_id="pay-1",
        tool_name="process_payment",
        inputs={"invoice_id": "INV-2026-99", "amount": 1500.00},
        idempotency_key="idemp-key-inv-99",
    )

    first_result = runtime.execute_step(step)
    assert call_count == 1
    assert first_result["status"] == "completed"

    # Second execution with same idempotency key must not call handler again
    second_result = runtime.execute_step(step)
    assert call_count == 1
    assert second_result == first_result


def test_wal_checkpoint_and_crash_recovery():
    with tempfile.TemporaryDirectory() as tmpdir:
        wal_path = Path(tmpdir) / "agent_journal.wal"
        runtime1 = AgentExecutionRuntime(wal_path=wal_path)

        def step_fn(args: dict) -> dict:
            return {"processed": args["data"].upper()}

        runtime1.register_tool("transform", step_fn, schema={"data": str})

        step1 = AgentStep("s1", "transform", {"data": "alpha"}, idempotency_key="k1")
        step2 = AgentStep("s2", "transform", {"data": "beta"}, idempotency_key="k2")

        runtime1.execute_step(step1)
        runtime1.execute_step(step2)

        assert wal_path.exists()

        # Simulate crash & restart in a fresh runtime instance pointing to same WAL file
        runtime2 = AgentExecutionRuntime(wal_path=wal_path)
        runtime2.register_tool("transform", step_fn, schema={"data": str})

        assert runtime2.is_idempotency_key_executed("k1")
        assert runtime2.is_idempotency_key_executed("k2")

        # Step 1 should return from recovered journal without re-running
        recovered_res = runtime2.execute_step(step1)
        assert recovered_res == {"processed": "ALPHA"}


def test_policy_rejection_halts_execution():
    runtime = AgentExecutionRuntime()

    def unsafe_action(args: dict) -> dict:
        return {"status": "unreachable"}

    def policy_guard(step: AgentStep) -> bool:
        # Deny actions with amount exceeding limit
        if step.inputs.get("amount", 0) > 10000:
            return False
        return True

    runtime.register_tool("transfer", unsafe_action, schema={"amount": int}, policy_check=policy_guard)

    step = AgentStep("s-denied", "transfer", {"amount": 50000}, idempotency_key="k-deny")

    with pytest.raises(PolicyRejectionError):
        runtime.execute_step(step)

    assert not runtime.is_idempotency_key_executed("k-deny")


def test_execution_trace_generation():
    runtime = AgentExecutionRuntime()
    runtime.register_tool("echo", lambda args: {"val": args["msg"]}, schema={"msg": str})

    runtime.execute_step(AgentStep("trace-1", "echo", {"msg": "hello"}, idempotency_key="t1"))
    runtime.execute_step(AgentStep("trace-2", "echo", {"msg": "world"}, idempotency_key="t2"))

    traces = runtime.get_traces()
    assert len(traces) == 2
    assert traces[0]["tool_name"] == "echo"
    assert traces[0]["status"] == "SUCCESS"
    assert "duration_ms" in traces[0]
