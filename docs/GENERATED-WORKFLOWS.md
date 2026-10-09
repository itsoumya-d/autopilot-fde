# Generated workflow runtime contract

Generating an agent creates Python source and a pending-approval record. It does
not start a worker. The optional LangGraph runtime must be installed separately;
reference adapters can have effects when executed and configured, so begin with
synthetic data and isolated local test adapters.

## Review and rejection

Generated gates call LangGraph's native `interrupt()`. Resume the same thread
with `Command(resume={"approved": True, "actor": "reviewer-name"})`. `approved` must be an actual
boolean, and `actor` must be a nonempty string. The name is an audit label, not
authenticated identity. Authenticate and authorize the caller in your host.

- Approval records one `human_approved` event and advances to the next node.
- Rejection records one `human_rejected` event, sets `is_escalated`, and ends the
  graph. Dependent nodes do not execute.
- Malformed input produces another interrupt with `validation_error`. It does
  not record approval or run an adapter. Submit a corrected decision to that
  pending interrupt; this also works after a SQLite-backed restart.
- Gates never call a step adapter. They record review only; they do not prove
  that a person completed the named business action outside the graph.

An approval-only node and conditional outgoing edges avoid running a business
adapter before review. Every node returns only its new history event because
LangGraph's `operator.add` reducer appends the delta. This prevents duplicate
history; it is not a distributed exactly-once guarantee for external services.

## Selected automation and topology

`enabled_steps` selects automatic adapter nodes. Other steps remain explicit
`manual_step` review gates, preserving their position and prerequisites. These
disabled adapters are never called. Existing approval-required steps remain
gated even if selected. Unknown step names are rejected.

An empty `enabled_steps` list retains the existing default meaning, not “select
none”: direct generation uses the default step set, while REST/MCP deployment
selects the first eligible step. There is no separate select-none API contract.
A workflow consisting entirely of review-gated steps has no automatic adapter
calls.

With supplied mined edges, only a complete, connected, acyclic linear chain is
supported. Its unique graph root is the entrypoint, regardless of transition
probabilities or input edge order. Branches, convergence, cycles, disconnected
or incomplete edges, unknown endpoints, self-loops and ambiguous node names
are rejected; they are never silently reordered into a different workflow.
REST deployment returns HTTP 422; MCP returns a tool error without storing a
new agent. When no edges are supplied, the explicit activity order is used.

## Persistence and verification

By default, checkpoints are in memory and do not survive process restart. Set
`AUTOPILOT_CHECKPOINT_DB` to a local SQLite file and install the SQLite extra for
restartable pauses. Protect the file and its parent directory appropriately;
this is not a multi-tenant authorization or retention system.

From the repository root in a separate virtual environment:

```bash
python -m pip install -r backend/requirements.txt -r requirements-agents.txt pytest
PYTHONPATH=. AUTOPILOT_REQUIRE_RUNTIME_TESTS=1 LANGCHAIN_TRACING_V2=false LANGSMITH_TRACING=false \
  python -m pytest tests/runtime/ -q
```

The dedicated CI runtime job executes emitted graphs against real LangGraph and
in-memory/SQLite checkpointers, with isolated recording adapters. It covers
approval/rejection, malformed-decision recovery across restart, single-event
history, repeat resume, partial automation and graph-root validation. It does
not contact model providers, run production webhooks or establish browser E2E
coverage. The separate core suite retains its 100% measured coverage gate.
