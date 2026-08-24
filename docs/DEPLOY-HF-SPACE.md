# Deploy AutoPilot FDE as a Hugging Face Space (free hosted MCP)

The Space gives you a **public HTTPS MCP endpoint** — `https://<org>-<space>.hf.space/mcp`
— with the Hub's grey **MCP badge** in the Spaces directory, so anyone can add
AutoPilot FDE's tools to Claude Desktop, Claude Code, Codex CLI, or Cursor
with one click. No server, no domain, no TLS.

## 1. Create the Space

```bash
pip install -U "huggingface_hub[cli]"
hf auth login

hf repo create <your-org>/autopilot-fde --repo-type space --space_sdk docker
```

## 2. Push the three files

From this repository's root:

```bash
hf upload <your-org>/autopilot-fde spaces/Dockerfile   Dockerfile  --repo-type space
hf upload <your-org>/autopilot-fde spaces/README.md    README.md   --repo-type space
hf upload <your-org>/autopilot-fde backend             backend     --repo-type space
```

The Space builds (`spaces/Dockerfile`) and boots uvicorn on the port the
platform injects.

## 3. Verify

```bash
curl -s "https://<your-org>-autopilot-fde.hf.space/health"
curl -s -X POST "https://<your-org>-autopilot-fde.hf.space/mcp" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}'
curl -s "https://<your-org>-autopilot-fde.hf.space/.well-known/mcp" | jq .serverInfo
```

## 4. Point your coding agent at it

**Codex CLI** (`~/.codex/config.toml`):

```toml
[mcp_servers.autopilot-fde]
url = "https://<your-org>-autopilot-fde.hf.space/mcp"
```

**Claude Code**: `claude mcp add autopilot-fde --transport http https://<your-org>-autopilot-fde.hf.space/mcp`

**Claude Desktop / Cursor**: same URL in their MCP config (remote server).

## 5. Gating mutations on a public deployment

Read-only tools are safe to expose. For mutations, the consent gate applies:

```bash
hf spaces secrets set <your-org>/autopilot-fde AUTOPILOT_MCP_ALLOW_MUTATIONS=1
```

Leave the secret unset for a pure read-only demo (recommended for public
Spaces). The demo workspace self-seeds; every restart resets to that seed
unless you attach a persistent Space volume.

## Notes

- HF OAuth is declared in the Space frontmatter so authenticated tool calls
  can be attributed later; scopes are minimal (`inference-api`).
- The registry publish workflow (`publish-mcp.yml`) lists the stdio variant;
  once the Space is live, add its URL under `transports.streamable-http` in
  `server.json` and re-tag.
