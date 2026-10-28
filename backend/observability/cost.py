"""Token-cost attribution rollups for gen_ai.* usage (ROADMAP v0.5.0 a3).

Maps ``gen_ai.usage.input_tokens`` / ``output_tokens`` to USD with an explicit,
auditable price table and aggregates spend by model, agent and tool, so an
operator can answer "which agent cost the most this week?" without a vendor
dashboard.

Pricing is USD per 1,000,000 tokens. Defaults cover the models this repository
routinely targets; extend or override them without code changes:

    AUTOPILOT_COST_TABLE='{"my-model": {"input": 0.5, "output": 1.5}}'

Unknown models are never guessed at: they cost 0.0 and are surfaced in the
snapshot as ``unpriced_models`` so the gap is visible rather than silent.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PRICING_ENV = "AUTOPILOT_COST_TABLE"
TOKENS_PER_UNIT = 1_000_000

DEFAULT_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "claude-opus-4": {"input": 15.00, "output": 75.00},
    "deepseek-chat": {"input": 0.27, "output": 1.10},
    "llama-3.1-70b": {"input": 0.59, "output": 0.79},
}


def load_pricing(raw: str | None = None) -> dict[str, dict[str, float]]:
    """Default price table merged with the JSON override in ``AUTOPILOT_COST_TABLE``.

    Malformed overrides are ignored wholesale (the defaults stay), because a
    broken cost table must never break instrumentation. Invalid individual
    entries are skipped for the same reason.
    """
    pricing = {model: dict(rates) for model, rates in DEFAULT_PRICING.items()}
    override = raw if raw is not None else os.getenv(PRICING_ENV, "")
    if not override.strip():
        return pricing
    try:
        parsed = json.loads(override)
    except json.JSONDecodeError:
        return pricing
    if not isinstance(parsed, dict):
        return pricing
    for model, rates in parsed.items():
        if not isinstance(rates, dict):
            continue
        try:
            pricing[model] = {
                "input": float(rates.get("input", 0.0)),
                "output": float(rates.get("output", 0.0)),
            }
        except (TypeError, ValueError):
            continue
    return pricing


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    pricing: dict[str, dict[str, float]] | None = None,
) -> float:
    """USD for one call. Unknown models cost 0.0; negative counts clamp to zero."""
    table = load_pricing() if pricing is None else pricing
    rates = table.get(model)
    if rates is None:
        return 0.0
    billed_input = max(int(input_tokens), 0)
    billed_output = max(int(output_tokens), 0)
    return round(
        (billed_input * rates["input"] + billed_output * rates["output"])
        / TOKENS_PER_UNIT,
        6,
    )


@dataclass(frozen=True)
class UsageRecord:
    """One measured LLM/tool call, shaped like the gen_ai.* semantic convention."""

    model: str
    input_tokens: int
    output_tokens: int
    agent_id: str = ""
    tool_name: str = ""


class CostAttributor:
    """Thread-safe accumulator keyed by (model, agent_id, tool_name)."""

    def __init__(self, pricing: dict[str, dict[str, float]] | None = None):
        self._pricing = pricing if pricing is not None else load_pricing()
        self._lock = threading.Lock()
        self._rollups: dict[tuple[str, str, str], dict[str, float | int]] = {}
        self._total_usd = 0.0
        self._total_input = 0
        self._total_output = 0
        self._unpriced: set[str] = set()

    def record(self, usage: UsageRecord) -> float:
        """Attribute one call; returns its USD cost."""
        cost = estimate_cost(
            usage.model, usage.input_tokens, usage.output_tokens, self._pricing
        )
        billed_input = max(int(usage.input_tokens), 0)
        billed_output = max(int(usage.output_tokens), 0)
        key = (usage.model, usage.agent_id, usage.tool_name)
        with self._lock:
            bucket = self._rollups.setdefault(
                key,
                {"calls": 0, "input_tokens": 0, "output_tokens": 0, "usd": 0.0},
            )
            bucket["calls"] = int(bucket["calls"]) + 1
            bucket["input_tokens"] = int(bucket["input_tokens"]) + billed_input
            bucket["output_tokens"] = int(bucket["output_tokens"]) + billed_output
            bucket["usd"] = round(float(bucket["usd"]) + cost, 6)
            self._total_usd = round(self._total_usd + cost, 6)
            self._total_input += billed_input
            self._total_output += billed_output
            if usage.model not in self._pricing:
                self._unpriced.add(usage.model)
        return cost

    def snapshot(self) -> dict[str, Any]:
        """Deterministic, JSON-ready view of everything recorded so far."""
        with self._lock:
            rollups = [
                {
                    "model": model,
                    "agent_id": agent_id,
                    "tool_name": tool_name,
                    "calls": bucket["calls"],
                    "input_tokens": bucket["input_tokens"],
                    "output_tokens": bucket["output_tokens"],
                    "usd": bucket["usd"],
                }
                for (model, agent_id, tool_name), bucket in sorted(
                    self._rollups.items()
                )
            ]
            return {
                "total_usd": round(self._total_usd, 6),
                "total_input_tokens": self._total_input,
                "total_output_tokens": self._total_output,
                "unpriced_models": sorted(self._unpriced),
                "rollups": rollups,
            }

    def reset(self) -> None:
        """Clear all counters (useful between reporting windows)."""
        with self._lock:
            self._rollups.clear()
            self._total_usd = 0.0
            self._total_input = 0
            self._total_output = 0
            self._unpriced.clear()

    def dump(self, path: str | Path) -> Path:
        """Write the current snapshot as JSON; returns the written path."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.snapshot(), indent=2), encoding="utf-8")
        return target


_DEFAULT: CostAttributor | None = None
_DEFAULT_LOCK = threading.Lock()


def default_attributor() -> CostAttributor:
    """Process-wide accumulator used by call sites that want zero wiring."""
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is None:
            _DEFAULT = CostAttributor()
        return _DEFAULT


def record_usage(usage: UsageRecord) -> float:
    """Attribute one call to the process-wide accumulator."""
    return default_attributor().record(usage)
