#!/usr/bin/env bash
# AutoPilot FDE one-step installer.
#
#   bash install.sh              # install everything, print next steps
#   bash install.sh --run       # ... and start backend + dashboard
#   bash install.sh --check     # verify an existing installation only
#
# Idempotent: safe to re-run. Nothing here needs API keys; the server seeds
# its own demo workspace on first boot.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

RUN=false
CHECK=false
for arg in "$@"; do
  case "$arg" in
    --run) RUN=true ;;
    --check) CHECK=true ;;
    *) echo "Unknown flag: $arg (use --run or --check)"; exit 2 ;;
  esac
done

PYTHON_BIN="${PYTHON_BIN:-python3}"
NODE_BIN="${NODE_BIN:-node}"

say()  { printf '\033[1;36m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m !\033[0m  %s\n' "$1"; }

command -v "$PYTHON_BIN" >/dev/null || { warn "python3 not found on PATH"; exit 1; }

# ── Backend ──────────────────────────────────────────────────────────────────
say "Backend: virtualenv + dependencies"
if [ ! -x .venv/bin/python ]; then
  "$PYTHON_BIN" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --quiet --upgrade pip
pip install --quiet -r backend/requirements.txt

say "Backend: test suite (63+ assertions)"
if PYTHONPATH=. python -m pytest tests/ -q -p no:cacheprovider >/tmp/autopilot_install_tests.log 2>&1; then
  tail -1 /tmp/autopilot_install_tests.log
else
  warn "tests failed — see /tmp/autopilot_install_tests.log"; exit 1
fi

# ── Frontend ─────────────────────────────────────────────────────────────────
FRONTEND_OK=true
if command -v "$NODE_BIN" >/dev/null; then
  say "Frontend: npm dependencies + production build"
  ( cd frontend \
    && { npm ci --silent 2>/dev/null || npm install --silent; } \
    && npm run build )
else
  FRONTEND_OK=false
  warn "node not found — skipping dashboard build (API + MCP still work)"
fi

if $CHECK; then
  say "Check complete."
  exit 0
fi

# ── MCP wiring snippets ─────────────────────────────────────────────────────
ABS_ROOT="$ROOT"
cat <<EOF

┌──────────────────────────────────────────────────────────────────────────┐
│ Installation complete. Wire your coding agent (pick any):                │
├──────────────────────────────────────────────────────────────────────────┤

Claude Desktop / Claude Code → claude_desktop_config.json:
  {"mcpServers": {"autopilot-fde": {
    "command": "$ABS_ROOT/.venv/bin/python",
    "args": ["-m", "backend.mcp_server"],
    "cwd": "$ABS_ROOT",
    "env": {"AUTOPILOT_DB_PATH": "$ABS_ROOT/backend/autopilot.db"}}}}

Codex CLI → ~/.codex/config.toml:
  [mcp_servers.autopilot-fde]
  command = "$ABS_ROOT/.venv/bin/python"
  args = ["-m", "backend.mcp_server"]
  cwd = "$ABS_ROOT"
  [mcp_servers.autopilot-fde.env]
  AUTOPILOT_DB_PATH = "$ABS_ROOT/backend/autopilot.db"

Claude Code plugin marketplace (from this repo root):
  /plugin marketplace add <this-repo>
  /plugin install autopilot-fde@hostshift-fde

Mutating MCP tools stay disabled until you add:
  "AUTOPILOT_MCP_ALLOW_MUTATIONS": "1"   (server env)

└──────────────────────────────────────────────────────────────────────────┘

Run it:
  source .venv/bin/activate
  uvicorn backend.main:app --port 8000          # API  → http://127.0.0.1:8000
$( if $FRONTEND_OK; then echo '  ( cd frontend && npm run dev )               # UI   → http://localhost:3000'; else echo '  # install node/npm for the dashboard UI'; fi )

Or: bash install.sh --run
EOF

if $RUN; then
  say "Starting backend on :8000 and frontend on :3000 (Ctrl-C to stop)"
  trap 'kill 0' EXIT INT TERM
  uvicorn backend.main:app --port 8000 &
  if $FRONTEND_OK; then
    ( cd frontend && npm run dev ) &
  fi
  wait
fi
