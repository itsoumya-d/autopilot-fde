# Research Log

Every loop iteration starts with cited research. Entries are dated, link
their sources, and name the implementation each finding fed.

## 2026-08-24 — The FDE operating model is now the enterprise AI motion

**Sources**

- CIO, *Forward-deployed engineering in the age of agentic AI* (2026-07-28) —
  https://www.cio.com/article/4202404/
- Forrester, *Forward-Deployed Engineers Are The Training Wheels For AI
  Reinvention* (2026-07-30) — https://www.forrester.com/blogs/forward-deployed-engineers-are-the-training-wheels-for-ai-reinvention/
- Perspective AI, *State of Forward Deployed Engineering 2026* (survey of
  1,500 FDEs, 2026-05-18) — https://getperspective.ai/blog/state-of-forward-deployed-engineering-2026-survey-report-1500-fdes
- Closelook, *Forward-Deployed Engineers — The Human Layer of Agentic AI*
  (2026-07-09) — https://closelook.net/reports/forward-deployed-engineers/
- Mindra, *The Agentic Integration Stack: How Enterprises Are Wiring AI
  Agents Into Core Business Systems in 2026*

**Findings → implementation mapping**

| Finding | Feeds |
|---|---|
| $9B+ committed to FDE orgs in May–Jul 2026 (OpenAI Deployment Company $4B, Anthropic/Ode $1.5B, AWS $1B, Microsoft Frontier Co $2.5B; IBM commits 8,000 FDEs); 78% of FDE teams expect 2× headcount in 2027 | Category validation for ROADMAP positioning; "Where FDE is going" README section |
| FDE tooling stack: 96% agentic coding, 78% observability/eval (LangSmith/Braintrust/W&B), 41% AI-moderated continuous discovery (+32pts YoY); discovery loops going "always-on" by 2027 (64%) | v0.5 observability layer; chat-stream mining framed as the always-on discovery loop |
| Enterprise governance = five layers (intent/data/tool/decision/runtime); EU AI Act posture needs explainability logs retrievable within 72h and tamper-evident records | v0.5 hash-chained audit export; v0.6 tool-governance allowlist + decision gates (already structural) |
| OpenTelemetry `gen_ai.*` semantic conventions stable mid-2026 (`gen_ai.system`, `request.model`, `usage.input/output_tokens`, `agent.id`, `tool.name`) — baseline for agent observability and cost attribution | v0.5 `observability/tracing.py` span emission |
| Agent API Gateway pattern: per-workload identity (SPIFFE/RFC 8693 token exchange), per-agent rate limits, idempotent tool execution, dead-letter queues with human review, mTLS at the boundary | v0.6 agent identity tokens, quotas, idempotency keys, DLQ + review endpoint |
| Hybrid deterministic/LLM routing is non-negotiable for regulated workflows (deterministic control flow, LLM judgment only) | Already core: risk-tier classifier gates generated agents; documented explicitly |
| Native connector expectations: SAP/Salesforce/Workday/ServiceNow reachable under policy | v0.7 connector profiles on the governed webhook adapter |

## 2026-08-23 — MCP distribution & LangGraph/HF surfaces (v0.4.0 inputs)

- Official MCP Registry publish flow (mcp-publisher CLI, GitHub OIDC;
  PulseMCP/Smithery ingest downstream) — https://github.com/modelcontextprotocol/registry
- Camunda 8.9/8.10: Processes-as-MCP-tools, A2A connectors, centralized audit
  log; Celonis Orchestration Engine MCP tools (2025-11-04 launch, 2026 release notes)
- LangGraph persistence/interrupt docs: `interrupt()` recommended API,
  SqliteSaver durability, resume via `Command(resume=...)`, dedicated approval
  nodes avoid double-execution; LangGraph ships no notifications/audit/timeouts
  — the gap AutoPilot FDE's dashboard fills.
- Hugging Face Spaces-as-MCP-servers (Docker SDK, MCP badge, HF OAuth scopes);
  Inference Providers as OpenAI-compatible `LLM_BASE_URL`;
  datasets `push_to_hub` for training corpora.
