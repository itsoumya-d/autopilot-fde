#!/usr/bin/env python3
"""Export a deployed agent's audit trail as a tamper-evident hash chain.

    PYTHONPATH=. python scripts/export_audit_chain.py <agent_id> \
        [--out runs/audit/<agent_id>.json] [--verify]

The export embeds per-event SHA-256 links (canonical JSON); --verify
recomputes the chain and exits non-zero on any inconsistency. Suited to
EU AI Act Article 12-style explainability archives: store the JSON, verify
on demand, retain per your retention policy.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import database  # noqa: E402
from backend.export.audit_chain import export_agent_chain, verify_chain  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("agent_id")
    parser.add_argument("--out", default="")
    parser.add_argument("--verify", action="store_true",
                        help="Verify the chain after export; non-zero exit on tamper.")
    args = parser.parse_args()

    if override := os.getenv("AUTOPILOT_DB_PATH", "").strip():
        database.DB_PATH = Path(override).expanduser()

    async def load():
        await database.init_db()
        try:
            return await database.get_agent(args.agent_id)
        finally:
            await database.close_db()

    agent = asyncio.run(load())
    if not agent:
        print(f"Agent not found: {args.agent_id}", file=sys.stderr)
        return 1
    events = agent.metrics.get("audit") or []
    if not isinstance(events, list):
        events = []

    envelope = export_agent_chain(agent.id, events)

    if args.verify:
        ok, reason = verify_chain(envelope["events"])
        print(f"chain verification: {'OK' if ok else f'FAILED — {reason}'}")
        if not ok:
            return 2

    rendered = json.dumps(envelope, indent=2, default=str)
    target = (Path(args.out).expanduser() if args.out
              else Path.cwd() / "runs" / "audit" / f"{args.agent_id}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered + "\n", encoding="utf-8")
    print(f"Wrote audit chain ({envelope['event_count']} events, "
          f"head {envelope['head_hash'][:12]}…) -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
