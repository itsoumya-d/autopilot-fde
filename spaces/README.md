---
title: AutoPilot FDE MCP
emoji: 🤖
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: true
hf_oauth: true
hf_oauth_scopes:
  - inference-api
short_description: Forward-deployed engineering copilot — workflow discovery, APS scoring, ROI simulation, human-gated LangGraph agents (MCP server).
---

# AutoPilot FDE — hosted MCP demo

This Space runs the full FastAPI app: dashboard API, and the Streamable-HTTP
MCP endpoint at `/mcp` (server card at `/.well-known/mcp`). Because it is an
MCP-capable Space, the Hub shows the grey **MCP badge** — anyone can add these
tools to Claude/Codex/Cursor with one click from the Space page.

Read-only tools (discovery, scores, simulations) work out of the box against
the seeded demo workspace. Mutating tools stay refused unless the operator
sets `AUTOPILOT_MCP_ALLOW_MUTATIONS=1` as a **Space secret**, mirroring the
local consent gate.

Set secrets via: `hf spaces secrets set <org>/<space> AUTOPILOT_MCP_ALLOW_MUTATIONS=1`
