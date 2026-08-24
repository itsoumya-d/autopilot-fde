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


def push_to_hub(path: Path, repo_id: str) -> None:
    """Upload the exported JSONL as a Hugging Face dataset repo.

    Requires the optional hub extra and a logged-in token:
        pip install "huggingface_hub[cli]" && hf auth login
    """
    try:
        from huggingface_hub import HfApi
    except ImportError as error:  # pragma: no cover - optional dependency
        raise SystemExit(
            "huggingface_hub is not installed; run "
            '`pip install "huggingface_hub[cli]"` and `hf auth login` first.'
        ) from error
    api = HfApi()
    api.create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True)
    api.upload_file(
        path_or_fileobj=str(path),
        path_in_repo="train.jsonl",
        repo_id=repo_id,
        repo_type="dataset",
    )
    print(f"Pushed {path} -> https://huggingface.co/datasets/{repo_id} (train.jsonl)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=str, default="")
    parser.add_argument("--format", choices=("openai", "alpaca"), default="openai")
    parser.add_argument(
        "--push-to-hub", metavar="REPO_ID", default="",
        help="Upload the export to a Hugging Face dataset repo (org/name).")
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
    if args.push_to_hub:
        push_to_hub(target, args.push_to_hub)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
