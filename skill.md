---
name: autopilot-fde
description: Operate AutoPilot FDE — discover automatable workflows from chat streams, read APS scores, simulate ROI, deploy human-gated LangGraph agents, and wire MCP into coding agents. Use when the user asks about process discovery, automation candidates, agent deployment, or FDE tooling.
license: FSL-1.1-Apache-2.0
compatibility: Python 3.12+, FastAPI backend; optional langgraph extra for executing generated agents
metadata:
  repo: https://github.com/itsoumya-d/autopilot-fde
  mcp: python -m backend.mcp_server (stdio) or POST /mcp (streamable HTTP)
---

# AutoPilot FDE skill

Autonomous Forward Deployed Engineer: Slack/WhatsApp streams → discovered
workflows → APS scores → Monte Carlo ROI forecasts → human-gated LangGraph
agents.

## Setup

```bash
cd autopilot-fde && bash install.sh          # venv + deps + tests + build
bash install.sh --run                        # boots API :8000 + dashboard :3000
```

First boot seeds a demo workspace; no keys required.

## Talk to the workspace

MCP tools (preferred): `dashboard_summary`, `list_processes`, `get_process`,
`get_scores`, `recommendations`, `simulate_process`, `list_channels`,
`list_agents`; mutating (`run_discovery`, `deploy_agent`, `approve_agent`,
`pause_agent`, `resume_agent`, `stop_agent`) require
`AUTOPILOT_MCP_ALLOW_MUTATIONS=1` in the server env.

REST fallback:

```bash
curl -s localhost:8000/api/dashboard/
curl -s localhost:8000/api/scores/recommendations
curl -s "localhost:8000/api/scores/simulate/<process_id>?runs=1000"
```

## Deploy an agent

1. `GET /api/processes/` then `GET /api/scores/{id}` for eligible steps.
2. `POST /api/agents/deploy` with draft/assisted mode (AUTONOMOUS is refused
   by design). Branch starts `pending_approval`.
3. A human approves via `POST /api/agents/{id}/approve`. Every action is
   audited; illegal transitions return 409.
4. Generated code ships in `generated_code.python_code`; run it with the
   optional agents extra (`pip install -r requirements-agents.txt`) and open
   in LangGraph Studio via the bundled `langgraph.json`.

## Interpret scores

APS ≥ ~65 = strong candidate. Check `recommended_mode`
(observation_only/draft_only/assisted), `eligible_steps` vs `blocked_steps`
(blocked are structurally non-automatable), and simulation
`straight_through_rate` + `net_monthly_savings_dollars`.

## Train your own model

```bash
PYTHONPATH=. python scripts/export_training_data.py --format openai --out runs/training/train.jsonl
PYTHONPATH=. python scripts/export_training_data.py --format openai --out runs/training/train.jsonl --push-to-hub your-org/autopilot-extractor
```

See docs/FINE-TUNING.md (OpenAI API, Together, local LoRA, HF Inference
Providers as the enrichment endpoint).
