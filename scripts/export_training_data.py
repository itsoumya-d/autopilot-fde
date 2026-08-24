#!/usr/bin/env python3
"""Export discovered workspace data as instruction-tuning JSONL.

Usage (from autopilot-fde/, with the venv active):

    PYTHONPATH=. python scripts/export_training_data.py \\
        --out runs/training/autopilot-training.jsonl --format openai

The workspace must contain discovery results first (boot the API once, or run
``PYTHONPATH=. python -c "import asyncio; from backend import database, services;
asyncio.run(database.init_db()); asyncio.run(services.run_discovery())"``).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import database  # noqa: E402
from backend.export.training import build_rows, default_output_path, to_alpaca, write_jsonl  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=str, default="")
    parser.add_argument("--format", choices=("openai", "alpaca"), default="openai")
    args = parser.parse_args()

    if override := os.getenv("AUTOPILOT_DB_PATH", "").strip():
        from pathlib import Path as _Path

        database.DB_PATH = _Path(override).expanduser()

    async def collect():
        await database.init_db()
        try:
            processes = await database.get_processes()
            scores = {s.process_id: s for s in await database.get_scores()}
            messages = await database.get_messages()
            return processes, scores, messages
        finally:
            await database.close_db()

    processes, scores, messages = asyncio.run(collect())
    if not processes:
        print("No discovery results found. Boot the dashboard once or run "
              "run_discovery() before exporting.", file=sys.stderr)
        return 1

    rows = build_rows(processes, scores, messages)
    if not rows:
        print("Processes exist but no activity has source-message evidence; "
              "nothing to export.", file=sys.stderr)
        return 1
    if args.format == "alpaca":
        rows = [to_alpaca(row) for row in rows]

    target = Path(args.out).expanduser() if args.out else default_output_path()
    write_jsonl(rows, target)
    print(f"Wrote {len(rows)} training rows ({args.format} format) -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
