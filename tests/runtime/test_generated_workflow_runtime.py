"""Execute emitted workflows with real LangGraph and local recording adapters.

The core suite does not need optional agents dependencies. Run this suite with::

    pip install -r backend/requirements.txt -r requirements-agents.txt pytest
    AUTOPILOT_REQUIRE_RUNTIME_TESTS=1 PYTHONPATH=. pytest tests/runtime

CI sets the flag above so missing or broken runtime dependencies fail collection
instead of silently skipping this regression suite. No provider, account,
webhook, or real application adapter is invoked by these tests.
"""

import copy
import os
import sys
import types
from collections import Counter
from datetime import UTC, datetime
from uuid import uuid4

import pytest

if os.environ.get("AUTOPILOT_REQUIRE_RUNTIME_TESTS") != "1":
    pytest.importorskip("langgraph", reason="Install requirements-agents.txt for generated-runtime tests")
    pytest.importorskip("langgraph.checkpoint.sqlite", reason="Install requirements-agents.txt for SQLite tests")

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from backend.deployment.agent_factory import AgentFactory
from backend.models.schema import Activity, DeploymentConfig, Process, ProcessEdge

APPROVE = {"approved": True, "actor": "Synthetic reviewer"}
REJECT = {"approved": False, "actor": "Synthetic reviewer"}
GATED_STEPS = ("Read context", "Confirm request", "Prepare draft", "Final review")


def _process(steps, edges=()):
    return Process(
        id="runtime-fixture",
        name="Synthetic runtime fixture",
        category="testing",
        activities=[
            Activity(
                id=f"activity-{index}",
                name=step,
                category="testing",
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            )
            for index, step in enumerate(steps)
        ],
        edges=[ProcessEdge(source=source, target=target, probability=probability) for source, target, probability in edges],
    )


def _state(history=None):
    return {
        "case_id": "synthetic-case",
        "payload": {"source": "local-test"},
        "step_history": history if history is not None else [],
        "current_step": "",
        "is_escalated": False,
        "last_decision": {},
    }


def _config():
    return {"configurable": {"thread_id": str(uuid4())}}


class _GeneratedRuntime:
    def __init__(self, monkeypatch, backend):
        self.monkeypatch = monkeypatch
        self.backend = backend
        self.calls = []
        self.connections = []
        # Replace only the side-effect boundary. LangGraph, reducers, routing,
        # interrupts, and both checkpointer implementations are unmodified.
        adapter = types.ModuleType("backend.deployment.tool_adapters")
        adapter.execute_agent_step = self._record
        monkeypatch.setitem(sys.modules, adapter.__name__, adapter)

    def _record(self, *, step_name, context):
        self.calls.append(step_name)
        return {"status": "recorded_locally", "step": step_name, "source": context.get("source")}

    def generate(self, steps=GATED_STEPS, *, approval=True, edges=(), enabled_steps=None):
        generated = AgentFactory().generate_langgraph_code(
            _process(steps, edges),
            DeploymentConfig(approval_required=approval, enabled_steps=enabled_steps or []),
            "Runtime fixture"
        )
        module = types.ModuleType(f"_autopilot_generated_runtime_{uuid4().hex}")
        self.monkeypatch.setitem(sys.modules, module.__name__, module)
        # Do not inherit future annotations: LangGraph must see the emitted
        # Annotated history reducer exactly as it would in a standalone file.
        exec(compile(generated.python_code, "<generated-runtime>", "exec", dont_inherit=True), module.__dict__)
        if self.backend == "sqlite":
            assert isinstance(module.app.checkpointer, SqliteSaver)
            self.connections.append(module.app.checkpointer.conn)
        else:
            assert isinstance(module.app.checkpointer, InMemorySaver)
        return module, generated

    def reload_if_durable(self, module, **kwargs):
        if self.backend == "memory":
            return module
        # Close the original connection and compile a fresh module. No Python
        # graph/checkpointer state is reused: only the on-disk SQLite file is.
        connection = module.app.checkpointer.conn
        connection.close()
        self.connections.remove(connection)
        new_module, _ = self.generate(**kwargs)
        assert new_module.app.checkpointer is not module.app.checkpointer
        return new_module

    def close(self):
        for connection in self.connections:
            connection.close()


@pytest.fixture(params=("memory", "sqlite"))
def runtime(request, monkeypatch, tmp_path):
    if request.param == "sqlite":
        monkeypatch.setenv("AUTOPILOT_CHECKPOINT_DB", str(tmp_path / "checkpoint.sqlite"))
    else:
        monkeypatch.delenv("AUTOPILOT_CHECKPOINT_DB", raising=False)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    generated = _GeneratedRuntime(monkeypatch, request.param)
    yield generated
    generated.close()


@pytest.fixture(params=("sequential", "mined"))
def gated_edges(request):
    if request.param == "sequential":
        return ()
    # Deliberately put the highest-probability transition after the root.
    return tuple((source, target, 0.2 if index == 0 else 0.9)
                 for index, (source, target) in enumerate(zip(GATED_STEPS, GATED_STEPS[1:])))


def _assert_completed_without_replay(runtime, app, config, completed):
    calls = list(runtime.calls)
    history = copy.deepcopy(completed["step_history"])
    assert app.get_state(config).next == ()
    # A repeated completion resume must not append another approval row or
    # replay any adapter. The checkpoint remains completed for this thread.
    repeated = app.invoke(Command(resume=APPROVE), config)
    assert runtime.calls == calls
    assert repeated["step_history"] == history
    assert repeated["last_decision"] == completed["last_decision"]
    assert app.get_state(config).next == ()


def test_approved_resume_executes_downstream_once_and_survives_restart(runtime, gated_edges):
    module, _ = runtime.generate(edges=gated_edges)
    config = _config()
    paused = module.app.invoke(_state(), config)
    assert paused["__interrupt__"][0].value["step"] == "Confirm request"
    assert runtime.calls == ["Read context"]
    assert [row["step"] for row in paused["step_history"]] == ["Read context"]
    assert module.app.get_state(config).next == ("gate_confirm_request",)

    module = runtime.reload_if_durable(module, edges=gated_edges)
    assert module.app.get_state(config).next == ("gate_confirm_request",)
    approved = module.app.invoke(Command(resume=APPROVE), config)
    assert runtime.calls == ["Read context", "Prepare draft"]
    assert approved["__interrupt__"][0].value["step"] == "Final review"
    assert [row["step"] for row in approved["step_history"]] == list(GATED_STEPS[:3])
    assert [row["status"] for row in approved["step_history"]] == ["automated", "human_approved", "automated"]
    assert approved["last_decision"] == APPROVE

    module = runtime.reload_if_durable(module, edges=gated_edges)
    completed = module.app.invoke(Command(resume=APPROVE), config)
    assert not completed.get("__interrupt__")
    assert [row["step"] for row in completed["step_history"]] == list(GATED_STEPS)
    assert Counter(row["step"] for row in completed["step_history"]) == Counter(GATED_STEPS)
    assert completed["is_escalated"] is False
    module = runtime.reload_if_durable(module, edges=gated_edges)
    _assert_completed_without_replay(runtime, module.app, config, completed)


def test_rejected_resume_records_rejection_and_terminates_without_downstream_execution(runtime, gated_edges):
    module, _ = runtime.generate(edges=gated_edges)
    config = _config()
    assert module.app.invoke(_state(), config).get("__interrupt__")
    module = runtime.reload_if_durable(module, edges=gated_edges)
    rejected = module.app.invoke(Command(resume=REJECT), config)
    assert runtime.calls == ["Read context"]
    assert not rejected.get("__interrupt__")
    assert rejected["last_decision"] == REJECT
    assert rejected["is_escalated"] is True
    assert [row["step"] for row in rejected["step_history"]] == ["Read context", "Confirm request"]
    assert [row["status"] for row in rejected["step_history"]] == ["automated", "human_rejected"]
    assert rejected["step_history"][-1]["decision"] == REJECT
    module = runtime.reload_if_durable(module, edges=gated_edges)
    _assert_completed_without_replay(runtime, module.app, config, rejected)


MALFORMED_DECISIONS = [
    pytest.param(None, id="null-decision"),
    pytest.param(False, id="bare-false"),
    pytest.param(True, id="bare-true"),
    pytest.param("deny", id="string"),
    pytest.param([], id="list"),
    pytest.param({}, id="empty-object"),
    pytest.param({"approved": True}, id="missing-actor"),
    pytest.param({"actor": "Synthetic reviewer"}, id="missing-approved"),
    pytest.param({"approved": "true", "actor": "Synthetic reviewer"}, id="string-true"),
    pytest.param({"approved": "false", "actor": "Synthetic reviewer"}, id="string-false"),
    pytest.param({"approved": 1, "actor": "Synthetic reviewer"}, id="integer-one"),
    pytest.param({"approved": 0, "actor": "Synthetic reviewer"}, id="integer-zero"),
    pytest.param({"approved": None, "actor": "Synthetic reviewer"}, id="null-approved"),
    pytest.param({"approved": True, "actor": None}, id="null-actor"),
    pytest.param({"approved": True, "actor": ""}, id="empty-actor"),
    pytest.param({"approved": True, "actor": " \n\t "}, id="whitespace-actor"),
    pytest.param({"approved": True, "actor": 12}, id="numeric-actor"),
    pytest.param({"approved": False, "actor": []}, id="list-actor"),
]


@pytest.mark.parametrize("decision", MALFORMED_DECISIONS)
def test_malformed_resume_fails_closed_and_can_be_corrected_after_restart(runtime, decision):
    module, _ = runtime.generate()
    config = _config()
    paused = module.app.invoke(_state(), config)
    assert paused.get("__interrupt__")
    prior_history = copy.deepcopy(paused["step_history"])
    module = runtime.reload_if_durable(module)
    # An interrupt-ID mapping is necessary for None and {}: as top-level
    # Command.resume values they mean "no resume" and "no matching IDs".
    interrupted = module.app.invoke(Command(resume={paused["__interrupt__"][0].id: decision}), config)
    approval_request = interrupted["__interrupt__"][0].value
    assert approval_request["step"] == "Confirm request"
    assert "boolean" in approval_request["validation_error"]
    assert "actor" in approval_request["validation_error"]
    assert runtime.calls == ["Read context"]
    assert module.app.get_state(config).values["step_history"] == prior_history
    assert module.app.get_state(config).values["last_decision"] == {}

    module = runtime.reload_if_durable(module)
    corrected = module.app.invoke(Command(resume=APPROVE), config)
    assert runtime.calls == ["Read context", "Prepare draft"]
    assert corrected["__interrupt__"][0].value["step"] == "Final review"
    assert [row["step"] for row in corrected["step_history"]] == list(GATED_STEPS[:3])
    completed = module.app.invoke(Command(resume=APPROVE), config)
    _assert_completed_without_replay(runtime, module.app, config, completed)


def test_each_automated_node_contributes_one_delta_without_mutating_input(runtime):
    steps = ("Read alpha", "Read beta", "Read gamma")
    module, _ = runtime.generate(steps, approval=False)
    sentinel = {"step": "Existing event", "status": "retained", "nested": {"value": 1}}
    initial = _state([sentinel])
    original = copy.deepcopy(initial)
    delta = module.node_read_alpha(initial)
    assert initial == original
    assert delta["step_history"] is not initial["step_history"]
    assert len(delta["step_history"]) == 1
    assert delta["step_history"][0]["step"] == "Read alpha"
    runtime.calls.clear()

    result = module.app.invoke(initial, _config())
    assert initial == original
    assert runtime.calls == list(steps)
    assert result["step_history"][0] == sentinel
    assert Counter(row["step"] for row in result["step_history"]) == Counter(("Existing event", *steps))


@pytest.mark.parametrize("decision,status", [(APPROVE, "human_approved"), (REJECT, "human_rejected")])
def test_gate_returns_one_delta_without_mutating_input(runtime, decision, status, monkeypatch):
    module, _ = runtime.generate()
    # Direct invocation isolates the node's return contract; the tests above
    # exercise the real interrupt/resume mechanism without this patch.
    monkeypatch.setattr(module, "interrupt", lambda _request: decision)
    initial = _state([{"step": "Existing event", "status": "retained"}])
    original = copy.deepcopy(initial)
    decision_before = copy.deepcopy(decision)
    delta = module.gate_confirm_request(initial)
    assert initial == original
    assert decision == decision_before
    assert runtime.calls == []
    assert delta["step_history"] is not initial["step_history"]
    assert delta["step_history"] == [{"step": "Confirm request", "status": status, "decision": decision}]


def test_invalid_gate_decision_requests_correction_without_mutating_input(runtime, monkeypatch):
    module, _ = runtime.generate()
    decisions = iter((None, APPROVE))
    requests = []

    def interrupted(request):
        requests.append(request)
        return next(decisions)

    monkeypatch.setattr(module, "interrupt", interrupted)
    initial = _state([{"step": "Existing event", "status": "retained"}])
    original = copy.deepcopy(initial)
    delta = module.gate_confirm_request(initial)
    assert len(requests) == 2
    assert requests[0]["validation_error"] is None
    assert requests[1]["validation_error"]
    assert initial == original
    assert runtime.calls == []
    assert delta["step_history"] == [{"step": "Confirm request", "status": "human_approved", "decision": APPROVE}]


def test_mined_chain_starts_at_true_root_despite_probabilities_and_activity_order(runtime):
    steps = ("Read middle", "Read end", "Read root")
    edges = (("Read middle", "Read end", 0.99), ("Read root", "Read middle", 0.1))
    module, generated = runtime.generate(steps, approval=False, edges=edges)
    result = module.app.invoke(_state(), _config())
    assert generated.langgraph_spec["entrypoint_node"] == "node_read_root"
    assert generated.langgraph_spec["topology"] == "mined_edges"
    assert runtime.calls == ["Read root", "Read middle", "Read end"]
    assert [row["step"] for row in result["step_history"]] == runtime.calls
    assert result["current_step"] == "Read end"


@pytest.mark.parametrize("steps", [("Read only",), ("Read beta", "Read alpha", "Read gamma")])
def test_no_mined_edges_preserves_explicit_sequential_order(runtime, steps):
    module, _ = runtime.generate(steps, approval=False, edges=())
    config = _config()
    result = module.app.invoke(_state(), config)
    assert runtime.calls == list(steps)
    assert [row["step"] for row in result["step_history"]] == list(steps)
    assert module.app.get_state(config).next == ()


@pytest.mark.parametrize(
    "steps,edges",
    [
        pytest.param(("A", "B", "C"), (("A", "B", 0.8), ("A", "C", 0.2)), id="branch"),
        pytest.param(("A", "B", "C"), (("A", "C", 0.8), ("B", "C", 0.2)), id="merge"),
        pytest.param(("A", "B"), (("A", "B", 1.0), ("B", "A", 1.0)), id="cycle"),
        pytest.param(("A", "B", "C"), (("A", "B", 1.0),), id="omitted-node"),
        pytest.param(("A", "B", "C", "D"), (("A", "B", 1.0), ("C", "D", 1.0)), id="disconnected-chains"),
        pytest.param(
            ("A", "B", "C", "D"),
            (("A", "B", 1.0), ("C", "D", 1.0), ("D", "C", 1.0)),
            id="disconnected-cycle-with-one-root",
        ),
        pytest.param(("A", "B"), (("Unknown", "B", 1.0),), id="unknown-source"),
        pytest.param(("A", "B"), (("A", "Unknown", 1.0),), id="unknown-target"),
        pytest.param(("A",), (("A", "A", 1.0),), id="self-loop"),
    ],
)
def test_unsupported_mined_topologies_raise_instead_of_silently_falling_back(steps, edges):
    with pytest.raises(ValueError, match="(?i)workflow|edge|topolog|chain|branch|cycl|root"):
        AgentFactory().generate_langgraph_code(
            _process(steps, edges), DeploymentConfig(approval_required=False), "Invalid topology"
        )


@pytest.mark.parametrize("mined", [False, True])
def test_partially_enabled_workflow_retains_manual_prerequisites(runtime, mined):
    steps = ("Read context", "Prepare draft", "Record result")
    edges = ((steps[0], steps[1], 0.2), (steps[1], steps[2], 0.9)) if mined else ()
    kwargs = {"steps": steps, "approval": False, "enabled_steps": ["Prepare draft"], "edges": edges}
    module, generated = runtime.generate(**kwargs)
    assert generated.langgraph_spec["nodes_count"] == 3
    config = _config()
    paused = module.app.invoke(_state(), config)
    first_gate = paused["__interrupt__"][0].value
    assert first_gate["step"] == "Read context"
    assert first_gate["review_kind"] == "manual_step"
    assert first_gate["adapter_execution"] is False
    assert runtime.calls == []

    module = runtime.reload_if_durable(module, **kwargs)
    reviewed = module.app.invoke(Command(resume=APPROVE), config)
    assert runtime.calls == ["Prepare draft"]
    last_gate = reviewed["__interrupt__"][0].value
    assert last_gate["step"] == "Record result"
    assert last_gate["review_kind"] == "manual_step"
    assert last_gate["adapter_execution"] is False
    module = runtime.reload_if_durable(module, **kwargs)
    completed = module.app.invoke(Command(resume=APPROVE), config)
    assert [row["step"] for row in completed["step_history"]] == list(steps)
    assert [row["status"] for row in completed["step_history"]] == ["human_approved", "automated", "human_approved"]
    assert runtime.calls == ["Prepare draft"]
    _assert_completed_without_replay(runtime, module.app, config, completed)


@pytest.mark.parametrize("enabled_steps", [[], ["Read context", "Prepare draft", "Record result"]])
def test_default_and_explicit_all_enabled_steps_execute_each_adapter_once(runtime, enabled_steps):
    steps = ("Read context", "Prepare draft", "Record result")
    module, _ = runtime.generate(steps, approval=False, enabled_steps=enabled_steps)
    completed = module.app.invoke(_state(), _config())
    assert runtime.calls == list(steps)
    assert [row["step"] for row in completed["step_history"]] == list(steps)
    assert [row["status"] for row in completed["step_history"]] == ["automated"] * len(steps)
    assert not completed.get("__interrupt__")


def test_all_manual_workflow_records_reviews_without_any_adapter_execution(runtime):
    steps = ("Confirm intake", "Approval verification", "Confirm completion")
    module, _ = runtime.generate(steps)
    config = _config()
    result = module.app.invoke(_state(), config)
    for index, step in enumerate(steps):
        approval_request = result["__interrupt__"][0].value
        assert approval_request["step"] == step
        assert approval_request["adapter_execution"] is False
        assert runtime.calls == []
        assert len(result["step_history"]) == index
        module = runtime.reload_if_durable(module, steps=steps)
        result = module.app.invoke(Command(resume=APPROVE), config)
    assert not result.get("__interrupt__")
    assert runtime.calls == []
    assert [row["step"] for row in result["step_history"]] == list(steps)
    assert [row["status"] for row in result["step_history"]] == ["human_approved"] * len(steps)
    _assert_completed_without_replay(runtime, module.app, config, result)


def test_unknown_enabled_step_raises_instead_of_dropping_every_step():
    with pytest.raises(ValueError, match="enabled_steps"):
        AgentFactory().generate_langgraph_code(
            _process(("Read context", "Prepare draft")),
            DeploymentConfig(approval_required=False, enabled_steps=["Unknown"]),
            "Invalid enabled steps",
        )


def test_repeated_malformed_direct_resumes_stay_paused_until_explicit_rejection(runtime):
    module, _ = runtime.generate()
    config = _config()
    assert module.app.invoke(_state(), config).get("__interrupt__")
    for decision in (
        {"approved": "false", "actor": "Synthetic reviewer"},
        {"approved": True, "actor": "  "},
    ):
        module = runtime.reload_if_durable(module)
        paused = module.app.invoke(Command(resume=decision), config)
        assert paused["__interrupt__"][0].value["step"] == "Confirm request"
        assert paused["__interrupt__"][0].value["validation_error"]
        assert [row["step"] for row in paused["step_history"]] == ["Read context"]
        assert runtime.calls == ["Read context"]
    module = runtime.reload_if_durable(module)
    rejected = module.app.invoke(Command(resume=REJECT), config)
    assert not rejected.get("__interrupt__")
    assert rejected["step_history"][-1]["status"] == "human_rejected"
    assert runtime.calls == ["Read context"]
    _assert_completed_without_replay(runtime, module.app, config, rejected)


@pytest.mark.parametrize("decision,status", [(APPROVE, "human_approved"), (REJECT, "human_rejected")])
def test_shuffled_mined_activities_gate_the_actual_terminal_step(runtime, decision, status):
    steps = ("Read middle", "Read end", "Read root")
    edges = (("Read middle", "Read end", 0.99), ("Read root", "Read middle", 0.1))
    module, generated = runtime.generate(steps, approval=True, edges=edges)
    assert generated.langgraph_spec["entrypoint_node"] == "node_read_root"
    assert generated.langgraph_spec["hitl_nodes"] == ["read_end"]
    config = _config()
    paused = module.app.invoke(_state(), config)
    assert runtime.calls == ["Read root", "Read middle"]
    assert [row["step"] for row in paused["step_history"]] == ["Read root", "Read middle"]
    assert paused["__interrupt__"][0].value["step"] == "Read end"
    assert module.app.get_state(config).next == ("gate_read_end",)

    module = runtime.reload_if_durable(module, steps=steps, approval=True, edges=edges)
    completed = module.app.invoke(Command(resume=decision), config)
    assert not completed.get("__interrupt__")
    assert runtime.calls == ["Read root", "Read middle"]
    assert [row["step"] for row in completed["step_history"]] == ["Read root", "Read middle", "Read end"]
    assert completed["step_history"][-1]["status"] == status
    assert completed["last_decision"] == decision
    _assert_completed_without_replay(runtime, module.app, config, completed)


@pytest.mark.parametrize(
    "source,target",
    [
        pytest.param("Read-root", "Read end", id="source-punctuation-alias"),
        pytest.param("read root", "Read end", id="source-case-alias"),
        pytest.param("Read root", "Read-end", id="target-punctuation-alias"),
        pytest.param("Read root", "read end", id="target-case-alias"),
    ],
)
def test_mined_edge_endpoints_must_match_declared_names_before_slug_mapping(source, target):
    with pytest.raises(ValueError, match="exact workflow step names"):
        AgentFactory().generate_langgraph_code(
            _process(("Read root", "Read end"), ((source, target, 1.0),)),
            DeploymentConfig(approval_required=True),
            "Invalid endpoint alias",
        )
