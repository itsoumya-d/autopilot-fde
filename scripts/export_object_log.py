#!/usr/bin/env python3
"""Export the object-centric event log (OCEL 2.0-inspired JSON).

    PYTHONPATH=. python scripts/export_object_log.py \
        --out runs/object-log/ocel.json [--limit 500]

The log re-expresses chat-derived activity as events referencing multiple
typed objects (case, actor, ticket, vendor, amount, email-domain) with
qualified relationships — the multi-object view that single-case mining
collapses. Deterministic: same workspace in, byte-identical log out.
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
from backend.discovery.object_centric import build_object_log  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()

    if override := os.getenv("AUTOPILOT_DB_PATH", "").strip():
        database.DB_PATH = Path(override).expanduser()

    async def collect():
        await database.init_db()
        try:
            activities = [
                activity
                for process in await database.get_processes()
                for activity in process.activities
            ][: max(0, args.limit)]
            messages = await database.get_messages()
            return activities, messages
        finally:
            await database.close_db()

    activities, messages = asyncio.run(collect())
    log = build_object_log(activities, messages)

    target = (Path(args.out).expanduser() if args.out
              else Path.cwd() / "runs" / "object-log" / "ocel.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(log, indent=2, default=str) + "\n",
                      encoding="utf-8")
    print(f"Wrote OCEL-shaped log ({log['summaries'] and len(log['events'])} "
          f"events, {len(log['objects'])} objects) -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
