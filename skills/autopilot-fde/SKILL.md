---
name: autopilot-fde
description: Operate AutoPilot FDE — discover automatable business workflows from chat streams, read Automation Potential (APS) scores, run Monte Carlo ROI simulations, and deploy human-gated LangGraph agents. Use when the user asks about workflow discovery, process mining, automation candidates, agent deployment, or connecting AutoPilot FDE to Claude/Codex/Cursor.
---

# AutoPilot FDE operation guide

AutoPilot FDE mines business workflows from communication streams (Slack,
WhatsApp), scores each with an Automation Potential Score (APS) derived from
graph transition entropy, forecasts straight-through rates with Monte Carlo
simulation, and generates typed LangGraph state machines whose critical steps
stay human-gated.

## Prerequisites

The backend must be installed and have a seeded workspace:

```bash
cd autopilot-fde
source .venv/bin/activate 2>/dev/null || python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
```

First boot of the API seeds a demo workspace automatically:
`uvicorn backend.main:app --port 8000`

## Talking to the workspace from this session

Prefer the MCP server when the host supports it (Claude Desktop/Code, Codex
CLI, Cursor). It exposes: `dashboard_summary`, `list_processes`,
`get_process`, `get_scores`, `recommendations`, `simulate_process`,
`list_channels`, `list_agents` — plus mutating tools (`run_discovery`,
`deploy_agent`, `approve_agent`, `pause_agent`, `resume_agent`,
`stop_agent`) that stay disabled until the operator sets
`AUTOPILOT_MCP_ALLOW_MUTATIONS=1` in the server environment.

Without MCP, use the REST API directly:

```bash
curl -s localhost:8000/api/dashboard/
curl -s localhost:8000/api/scores/recommendations
curl -s "localhost:8000/api/scores/simulate/<process_id>?runs=1000"
```

Mutating HTTP routes require `X-API-Key` when `AUTOPILOT_API_KEY` is set;
illegal lifecycle transitions return 409, never silent success.

## Interpreting results

- **APS score** (0–100): composite of value, feasibility, evidence
  confidence. Above ~65 is a strong candidate; check `recommended_mode`.
- **Safety modes**: `observation_only` → `draft_only` → `assisted`.
  `autonomous` is refused by the API by design.
- **eligible_steps vs blocked_steps**: blocked steps are structurally unable
  to run automatically (payments, sends, production changes).
- **Simulation**: `straight_through_rate` is the % of runs needing no human;
  `simulated_bottleneck_step` is where time goes; `net_monthly_savings_dollars`
  uses the $65/hr + token-cost model in `backend/scoring/simulator.py`.

## Deploying an agent

1. Pick a process: `GET /api/processes/`
2. Check eligible steps in its APS score: `GET /api/scores/{id}`
3. Deploy (creates pending_approval branch):
   ```bash
   curl -s -X POST localhost:8000/api/agents/deploy \
     -H 'Content-Type: application/json' -H "X-API-Key: $AUTOPILOT_API_KEY" \
     -d '{"process_id":"<id>","name":"Support Triage Copilot",
          "config":{"mode":"draft","approval_required":true}}'
   ```
4. A human approves via `POST /api/agents/{id}/approve` — agents can never
   self-approve, and every action lands in the audit trail.
5. Generated LangGraph code ships in `generated_code.python_code`; automated
   nodes dispatch through `backend/deployment/tool_adapters.py`
   (read-only → context summary, draft-only → local artifact,
   internal → operator-configured webhook; external/critical tiers raise).

## Customizing for an organization

- Discovery vocabulary: keyword tables in
  `backend/discovery/activity_extractor.py`
- Economics ($/hr, token price): constants atop `aps_engine.py` / `simulator.py`
- Risk tiers: `APSEngine.STEP_CLASSIFIERS`
- Own chat streams: `SLACK_BOT_TOKEN` + `POST /api/channels/slack/sync`, or
  the WhatsApp webhook

## Fine-tuning on discovered data

`scripts/export_training_data.py` writes instruction-tuning JSONL (openai or
alpaca format) pairing raw messages with expert extractions. See
docs/FINE-TUNING.md.
