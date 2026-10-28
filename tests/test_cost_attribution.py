"""Token-cost attribution rollups: price table, aggregation, snapshot, export."""

import json
import pathlib
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from backend.observability import cost  # noqa: E402
from backend.observability.cost import (  # noqa: E402
    DEFAULT_PRICING,
    CostAttributor,
    UsageRecord,
    default_attributor,
    estimate_cost,
    load_pricing,
    record_usage,
)


class TestPricing(unittest.TestCase):
    def test_defaults_are_used_without_override(self):
        pricing = load_pricing("")
        self.assertEqual(pricing["gpt-4o"], DEFAULT_PRICING["gpt-4o"])
        self.assertIsNot(pricing, DEFAULT_PRICING)  # copies, not aliases

    def test_env_override_merges_new_models(self):
        pricing = load_pricing('{"custom-model": {"input": 1.0, "output": 2.0}}')
        self.assertEqual(pricing["custom-model"], {"input": 1.0, "output": 2.0})
        self.assertIn("gpt-4o", pricing)  # defaults survive

    def test_env_override_can_replace_prices(self):
        pricing = load_pricing('{"gpt-4o": {"input": 0, "output": 0}}')
        self.assertEqual(pricing["gpt-4o"], {"input": 0.0, "output": 0.0})

    def test_missing_rate_keys_default_to_zero(self):
        pricing = load_pricing('{"half-priced": {"input": 1.0}}')
        self.assertEqual(pricing["half-priced"], {"input": 1.0, "output": 0.0})

    def test_invalid_json_falls_back_to_defaults(self):
        self.assertEqual(load_pricing("{not-json"), load_pricing(""))

    def test_non_dict_payload_falls_back_to_defaults(self):
        self.assertEqual(load_pricing("[1, 2, 3]"), load_pricing(""))

    def test_non_dict_entries_are_skipped(self):
        pricing = load_pricing('{"bad": "shape", "worse": 5}')
        self.assertNotIn("bad", pricing)
        self.assertNotIn("worse", pricing)

    def test_non_numeric_rates_are_skipped(self):
        pricing = load_pricing('{"broken": {"input": "nope", "output": 1}}')
        self.assertNotIn("broken", pricing)

    def test_environment_variable_is_read_when_raw_is_none(self):
        with mock.patch.dict(
            cost.os.environ, {cost.PRICING_ENV: '{"env-model": {"input": 1, "output": 1}}'}
        ):
            pricing = load_pricing(None)
        self.assertIn("env-model", pricing)


class TestEstimateCost(unittest.TestCase):
    def test_known_model_cost(self):
        # 1M input at $2.50 + 1M output at $10.00
        self.assertEqual(estimate_cost("gpt-4o", 1_000_000, 1_000_000), 12.5)

    def test_small_usage_rounds_to_six_places(self):
        self.assertEqual(estimate_cost("gpt-4o", 1, 1), round(12.5 / 1_000_000, 6))

    def test_unknown_model_costs_zero(self):
        self.assertEqual(estimate_cost("mystery-model", 500, 500), 0.0)

    def test_negative_tokens_clamp_to_zero(self):
        self.assertEqual(estimate_cost("gpt-4o", -100, -100), 0.0)

    def test_explicit_pricing_table_is_honoured(self):
        pricing = {"flat": {"input": 1.0, "output": 1.0}}
        self.assertEqual(estimate_cost("flat", 500_000, 500_000, pricing), 1.0)


class TestCostAttributor(unittest.TestCase):
    def test_record_returns_cost_and_aggregates(self):
        attributor = CostAttributor()
        first = attributor.record(UsageRecord("gpt-4o", 1_000_000, 0, "agent-a", "read"))
        second = attributor.record(UsageRecord("gpt-4o", 0, 1_000_000, "agent-a", "read"))
        self.assertEqual(first, 2.5)
        self.assertEqual(second, 10.0)
        snapshot = attributor.snapshot()
        self.assertEqual(snapshot["total_usd"], 12.5)
        self.assertEqual(snapshot["total_input_tokens"], 1_000_000)
        self.assertEqual(snapshot["total_output_tokens"], 1_000_000)
        self.assertEqual(len(snapshot["rollups"]), 1)
        rollup = snapshot["rollups"][0]
        self.assertEqual(rollup["calls"], 2)
        self.assertEqual(rollup["usd"], 12.5)

    def test_attribution_is_split_by_agent_and_tool(self):
        attributor = CostAttributor()
        attributor.record(UsageRecord("gpt-4o", 100, 100, "agent-a", "read"))
        attributor.record(UsageRecord("gpt-4o", 100, 100, "agent-b", "write"))
        attributor.record(UsageRecord("claude-sonnet-4", 100, 100, "agent-a", "read"))
        snapshot = attributor.snapshot()
        keys = {(r["model"], r["agent_id"], r["tool_name"]) for r in snapshot["rollups"]}
        self.assertEqual(
            keys,
            {
                ("gpt-4o", "agent-a", "read"),
                ("gpt-4o", "agent-b", "write"),
                ("claude-sonnet-4", "agent-a", "read"),
            },
        )

    def test_unknown_models_are_flagged_not_priced(self):
        attributor = CostAttributor()
        self.assertEqual(attributor.record(UsageRecord("mystery", 10, 10)), 0.0)
        snapshot = attributor.snapshot()
        self.assertEqual(snapshot["unpriced_models"], ["mystery"])
        self.assertEqual(snapshot["total_usd"], 0.0)

    def test_negative_tokens_are_clamped_in_rollups(self):
        attributor = CostAttributor()
        attributor.record(UsageRecord("gpt-4o", -50, -50, "agent-a", "read"))
        snapshot = attributor.snapshot()
        self.assertEqual(snapshot["total_input_tokens"], 0)
        self.assertEqual(snapshot["total_output_tokens"], 0)

    def test_reset_clears_everything(self):
        attributor = CostAttributor()
        attributor.record(UsageRecord("gpt-4o", 100, 100))
        attributor.reset()
        snapshot = attributor.snapshot()
        self.assertEqual(snapshot["total_usd"], 0.0)
        self.assertEqual(snapshot["rollups"], [])
        self.assertEqual(snapshot["unpriced_models"], [])

    def test_snapshot_rollups_are_sorted_and_detached(self):
        attributor = CostAttributor()
        attributor.record(UsageRecord("gpt-4o", 1, 1, "b"))
        attributor.record(UsageRecord("claude-sonnet-4", 1, 1, "a"))
        rollups = attributor.snapshot()["rollups"]
        self.assertEqual([r["model"] for r in rollups], ["claude-sonnet-4", "gpt-4o"])
        rollups.clear()  # snapshot is a copy; internal state is untouched
        self.assertEqual(len(attributor.snapshot()["rollups"]), 2)

    def test_dump_writes_json_and_creates_parent_directories(self):
        attributor = CostAttributor()
        attributor.record(UsageRecord("gpt-4o", 10, 20, "agent-a", "read"))
        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "nested" / "cost.json"
            written = attributor.dump(target)
            self.assertEqual(written, target)
            payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(payload["total_usd"], attributor.snapshot()["total_usd"])
        self.assertEqual(payload["rollups"][0]["agent_id"], "agent-a")

    def test_concurrent_records_sum_exactly(self):
        attributor = CostAttributor()
        records = 100
        threads = 8

        def worker():
            for _ in range(records):
                attributor.record(UsageRecord("gpt-4o", 1000, 1000))

        workers = [threading.Thread(target=worker) for _ in range(threads)]
        for w in workers:
            w.start()
        for w in workers:
            w.join()

        snapshot = attributor.snapshot()
        self.assertEqual(snapshot["rollups"][0]["calls"], records * threads)
        self.assertEqual(snapshot["rollups"][0]["input_tokens"], 1000 * records * threads)


class TestDefaultAttributor(unittest.TestCase):
    def setUp(self):
        cost._DEFAULT = None

    def tearDown(self):
        cost._DEFAULT = None

    def test_default_attributor_is_a_singleton(self):
        self.assertIs(default_attributor(), default_attributor())

    def test_record_usage_targets_the_default(self):
        first = record_usage(UsageRecord("gpt-4o", 1000, 1000))
        second = record_usage(UsageRecord("gpt-4o", 1000, 1000))
        self.assertEqual(first, second)
        self.assertEqual(default_attributor().snapshot()["rollups"][0]["calls"], 2)


if __name__ == "__main__":
    unittest.main()
