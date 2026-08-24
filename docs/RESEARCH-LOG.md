# Research Log

Every loop iteration starts with cited research. Entries are dated, link
their sources, and name the implementation each finding fed.

## 2026-08-24 (evening) — Object-centric discovery (v0.9.0 inputs)

**Sources**

- OCEL 2.0 Specification (2023-10-16; JSON/XML/SQLite schemas) —
  https://ocel-standard.org/2.0/ocel20_specification.pdf
- OCEL 2.0 JSON format reference — https://ocel-standard.org/specification/formats/json/
- Carried context: 2026 process-intelligence landscape survey (earlier entry)
  marking OCPM support as a *hard requirement* for order-to-cash /
  procure-to-pay classes of processes.

**Findings → implementation mapping**

| Finding | Feeds |
|---|---|
| OCEL 2.0 JSON = four top-level arrays (`eventTypes`, `events`, `objectTypes`, `objects`); events carry `relationships: [{objectId, qualifier}]` (E2O); objects may carry relationships too (O2O) | v0.9 `discovery/object_centric.py`: chat-derived activities re-expressed as an OCEL-shaped log with typed object extraction (case, actor, ticket, vendor, amount, email-domain), qualified E2O links, deduplicated co-observed O2O pairs |
| Single-case (XES-style) mining collapses multi-object processes (invoice + PO + shipment) into linear traces, hiding intersection failures | Per-object traces + per-type summaries expose where objects intersect — the failure points OCPM exists to find |
| Deterministic, auditable extraction matters more than model cleverness for regulated workflows | Pure-regex extractors with pinned patterns and tests; no LLM in the log-building path |

## 2026-08-24 (later) — Operable identity & telemetry (v0.8.0 inputs)

**Sources**

- OpenTelemetry, *OTLP Exporter Configuration* (updated 2026-07-13) —
  https://opentelemetry.io/docs/languages/sdk-configuration/otlp-exporter/
- OpenTelemetry Python, *Exporters* / `OTLPSpanExporter` reference —
  https://opentelemetry.io/docs/languages/python/exporters/
- Grafana, *Instrument a Python application* (post-fork provider setup) —
  https://grafana.com/docs/opentelemetry/instrument/python/
- Carried context: SPIFFE/SPIRE workload attestation and RFC 8693 token
  exchange from the agentic-integration-stack survey (2026-08-24 entry).

**Findings → implementation mapping**

| Finding | Feeds |
|---|---|
| Standard OTel wiring is programmatic: `TracerProvider(Resource(service.name))` + `BatchSpanProcessor(OTLPSpanExporter(endpoint))`; OTLP/HTTP appends `/v1/traces` to the base endpoint | v0.8 `observability/export.py`: env-driven wiring (`AUTOPILOT_OTEL_OTLP_ENDPOINT`, falls back to `OTEL_EXPORTER_OTLP_ENDPOINT`) called from app lifespan; dependency-injected so tests exercise the path without the exporter installed |
| Enterprise agent identity direction is short-lived, scoped, attested credentials (SPIFFE SVIDs rotate ~1–4h; RFC 8693 derives narrow tokens from user sessions) rather than long-lived static secrets | v0.8 **agent identity leases**: HMAC-signed, expiring capability tokens (`v1.<payload>.<sig>`, default 15-min TTL) issued per branch at `POST /api/agents/{id}/lease`; `verify_agent_token` transparently accepts lease or legacy static token, keeping DLQ review and future mutating surfaces unchanged |

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
