"""Training-data exporter: workspace evidence -> instruction-tuning JSONL.

Every discovery run produces exactly the triples a supervised fine-tune eats:
a raw human message (input), the structured workflow extraction an expert
system derived from it (output), and the domain context that made the
extraction correct (system prompt). This module serializes them.

Formats:

- ``openai``  chat-format rows: ``{"messages": [{role, content}, ...]}``,
              ready for OpenAI / Together / Anyscale fine-tuning APIs.
- ``alpaca``  classic instruction rows: ``{"instruction", "input", "output"}``.

The export is deterministic for a given workspace and contains no channel
credentials -- only message text, extracted activities, actors, categories
and scores. Point the resulting file at your provider of choice, or train a
LoRA adapter locally; docs/FINE-TUNING.md walks both paths.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..models.schema import APScore, Message, Process

SYSTEM_PROMPT = (
    "You are a forward-deployed process analyst. Given raw operational "
    "messages, extract the business workflow they describe as ordered steps "
    "with actors, department category, and confidence. Respond only with JSON."
)

_MAX_INPUT_CHARS = 4000


def build_rows(
    processes: list[Process],
    scores: dict[str, APScore],
    messages: list[Message],
) -> list[dict[str, Any]]:
    """One training row per discovered activity, keyed to its source messages."""
    by_id = {m.id: m for m in messages}
    rows: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()

    for process in processes:
        score = scores.get(process.id)
        for activity in process.activities:
            sources = [by_id[mid] for mid in activity.source_messages if mid in by_id]
            if not sources:
                continue
            user_text = "\n".join(
                f"{m.sender}: {m.content}"[:_MAX_INPUT_CHARS] for m in sources
            ).strip()
            if not user_text:  # pragma: no cover - defensive; sender prefix keeps text non-empty
                continue
            key = (process.name, user_text)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            extraction = {
                "process": process.name,
                "category": process.category or "general",
                "step": activity.name,
                "actors": sorted(set(activity.actors)),
                "case_id": activity.case_id,
                "confidence": round(activity.confidence, 2),
            }
            if score:
                extraction["recommended_mode"] = score.recommended_mode.value
            rows.append({
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_text},
                    {"role": "assistant", "content": json.dumps(extraction, sort_keys=True)},
                ],
            })
    return rows


def to_alpaca(row: dict[str, Any]) -> dict[str, str]:
    system, user, assistant = (m["content"] for m in row["messages"])
    return {
        "instruction": system,
        "input": user,
        "output": assistant,
    }


def write_jsonl(rows: list[dict[str, Any]], path: str | Path) -> Path:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return target


def default_output_path() -> Path:
    override = os.getenv("AUTOPILOT_TRAINING_OUT", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.cwd() / "runs" / "training" / "autopilot-training.jsonl"
