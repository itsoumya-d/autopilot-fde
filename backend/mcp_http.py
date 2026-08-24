"""Streamable-HTTP MCP transport served by the FastAPI app.

The stdio server (``python -m backend.mcp_server``) serves local coding
agents; this router exposes the *same* tool surface over HTTP at ``/mcp``
in the spec's stateless Streamable-HTTP JSON mode, so remote clients --
Codex CLI (`url = ...`), Cursor, ChatGPT connectors, HF Spaces -- can point
at one URL without spawning a process.

Same policy as stdio, unchanged: read-only tools are open, mutating tools
stay refused until ``AUTOPILOT_MCP_ALLOW_MUTATIONS=1`` is set in the
server's environment. The discovery card lives at ``/.well-known/mcp``.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .mcp_server import (
    PARSE_ERROR,
    SERVER_NAME,
    SERVER_VERSION,
    handle_message,
)

logger = logging.getLogger("autopilot.mcp-http")

router = APIRouter()


@router.post("/mcp", tags=["MCP"])
async def mcp_endpoint(request: Request) -> JSONResponse:
    """One JSON-RPC message in, one response out (stateless JSON mode)."""
    raw = await request.body()
    try:
        message = json.loads(raw or b"")
    except json.JSONDecodeError:
        return JSONResponse({
            "jsonrpc": "2.0", "id": None,
            "error": {"code": PARSE_ERROR, "message": "Parse error"},
        })
    if not isinstance(message, dict):
        return JSONResponse({
            "jsonrpc": "2.0", "id": None,
            "error": {"code": PARSE_ERROR, "message": "Parse error"},
        })
    response = await handle_message(message)
    if response is None:  # notifications get 202-style empty acknowledgement
        return JSONResponse({"jsonrpc": "2.0", "result": {}}, status_code=202)
    status = 500 if "error" in response and response["error"].get("code") == -32603 else 200
    return JSONResponse(response, status_code=status)


@router.get("/.well-known/mcp", tags=["MCP"])
async def mcp_discovery() -> dict:
    """Static server card so agents can discover capabilities at a fixed path."""
    from .mcp_server import MUTATIONS_ENV, mutations_allowed, tools_listing

    return {
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        "protocolVersion": "2024-11-05",
        "transports": {"streamableHttp": "/mcp"},
        "authentication": {
            "required": False,
            "note": (
                "Mutating tools additionally require "
                f"{MUTATIONS_ENV}=1 in the server environment."
            ),
        },
        "mutationsEnabled": mutations_allowed(),
        "tools": [
            {"name": t["name"], "description": t["description"]}
            for t in tools_listing()
        ],
    }
