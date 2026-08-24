# AutoPilot FDE — Research ⇄ Implement Loop Roadmap

The operating model for this repository is a **continuous loop**: every
iteration starts with cited research (see
[docs/RESEARCH-LOG.md](docs/RESEARCH-LOG.md)), ships a fully verified
increment (100% coverage gate, all suites green, live smoke), and lands as a
tagged release. This file is the loop's durable state — a new session resumes
exactly where the last one stopped.

```mermaid
gantt
  title AutoPilot FDE improvement loop (research -> implement -> verify -> tag)
  dateFormat YYYY-MM-DD
  axisFormat %b %d

  section shipped
  v0.3.0 Coverage + MCP distribution kit   :done, v03, 2026-08-24, 1d
  v0.4.0 LangGraph-native + HuggingFace    :done, v04, 2026-08-24, 1d

  section v0.5.0 Observable and Compliant
  OTel gen_ai.* spans (optional extra)      :active, a1, 2026-08-24, 1d
  Hash-chained tamper-evident audit export  :a2, after a1, 1d
  Token-cost attribution rollups            :a3, after a2, 1d

  section v0.6.0 Governed Autonomy
  Per-agent workload identity tokens        :b1, after a3, 1d
  Per-agent quotas + idempotency keys       :b2, after b1, 1d
  Dead-letter queue with human review       :b3, after b2, 1d
  Tool-governance allowlist policy          :b4, after b3, 1d

  section v0.7.0 Connected
  Connector profiles (SN/SF/Jira)           :c1, after b4, 1d
  A2A agent-card export                     :c2, after c1, 1d
  Slack interactive approvals               :c3, after c2, 1d
  IMAP email ingestion                      :c4, after c3, 1d
```

## System architecture (current)

```mermaid
graph TD
    subgraph Ingestion
        SL[Slack sync] --> DB[(SQLite WAL store)]
        WA[WhatsApp webhook] --> DB
        EM[IMAP email - v0.7] -.-> DB
    end

    subgraph Discovery
        DB --> EXT[Bayesian activity extractor]
        EXT --> MINER[Process miner + entropy]
        MINER --> APS[APS scoring engine]
        APS --> SIM[Monte Carlo simulator]
    end

    subgraph Governance
        G1[Risk-tier classifiers]
        G2[Audit trail -> hash chain]
        G3[Agent identity tokens - v0.6]
        G4[Tool policy allowlist - v0.6]
    end

    subgraph Deployment
        APS --> FACTORY[LangGraph codegen v2]
        FACTORY --> LG[native interrupt gates<br/>checkpointer / langgraph.json]
        LG --> ADAPTERS[Safe tool adapters]
        ADAPTERS --> WEBHOOK[Internal webhooks]
        ADAPTERS --> DLQ[Dead-letter queue - v0.6]
    end

    subgraph Surfaces
        API[FastAPI dashboard API] --- UI[Next.js console]
        API --> STDIO[MCP stdio server]
        API --> HTTPMCP[POST /mcp streamable HTTP]
        STDIO & HTTPMCP --> CLAUDE[Claude Desktop/Code]
        STDIO & HTTPMCP --> CODEX[Codex CLI]
        STDIO & HTTPMCP --> CURSOR[Cursor/Windsurf]
        API --> HF[HF Spaces hosted demo]
        API --> REG[MCP Registry listing]
    end

    SIM --> API
    G2 -.-> API
```

## Integration map (where FDE tooling plugs in)

```mermaid
graph LR
    AP[AutoPilot FDE] -->|MCP stdio+HTTP| ASSISTANTS[AI coding assistants]
    AP -->|langchain-mcp-adapters| LANGGRAPH[LangGraph/LangChain agents]
    AP -->|agent bundles zip| STUDIO[LangGraph Studio / dev server]
    AP -->|datasets push| HFHUB[Hugging Face Hub]
    AP -->|fine-tuned model via OpenAI-compatible API| ENRICH[Discovery enhancer]
    AP -.->|v0.7 A2A agent card| OTHERAGENTS[Third-party agents]
    AP -.->|v0.7 connector profiles| SNOW[ServiceNow]
    AP -.->|v0.7 connector profiles| SFDC[Salesforce]
    AP -.->|v0.7 connector profiles| JIRA[Jira]
    AP -->|hash-chained audit| SIEM[SIEM / compliance archive]
    AP -.->|OTel gen_ai.* spans| OTEL[Observability backends]
```

## Iteration log

| Tag | Theme | Status | Key deliverables |
|---|---|---|---|
| v0.3.0 | Observable distribution | shipped | MCP stdio+HTTP, registry kit, 100% cov gate |
| v0.4.0 | Native agents | shipped | interrupt() codegen, bundles, HF track |
| v0.5.0 | Observable & Compliant | **shipped** | gen_ai.* spans, tamper-evident audit chain, cost attribution |
| v0.6.0 | Governed Autonomy | queued | agent identity, quotas/idempotency, DLQ, tool policy |
| v0.7.0 | Connected | queued | connector profiles, A2A cards, Slack approvals, email |

## Verification contract (every iteration)

`pytest --cov-fail-under=100` · `ruff check` · frontend vitest/tsc/build ·
`install.sh --check` · live boot with stdio **and** HTTP `/mcp` handshakes ·
feature-specific smoke (chain tamper detection, token auth rejection, DLQ
review flow).
