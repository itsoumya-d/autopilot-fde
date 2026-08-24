"""Training-data exporter tests: row construction, formats, JSONL output."""

import json
import pathlib
import sys
import tempfile
import unittest
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from backend.export.training import (  # noqa: E402
    build_rows,
    to_alpaca,
    write_jsonl,
)
from backend.models.schema import (  # noqa: E402
    Activity,
    APScore,
    Message,
    Process,
    SafetyStatus,
)


def _fixture():
    message = Message(
        id="m-1", channel_id="ch-1", sender="dana",
        content="Customer escalation received for Acme; the API is down for them.",
        timestamp=datetime.now(UTC),
    )
    activity = Activity(
        id="a-1", name="Customer escalation received", category="support",
        case_id="case-1", actors=["dana"], timestamp=message.timestamp,
        source_messages=["m-1"], evidence=message.content, confidence=0.95,
    )
    process = Process(
        id="proc-1", name="Support Escalation", category="support",
        activities=[activity], evidence_case_ids=["case-1"],
    )
    score = APScore(
        process_id="proc-1", score=69.0,
        recommended_mode=SafetyStatus.ASSISTED,
    )
    return [process], {"proc-1": score}, [message]


class TestBuildRows(unittest.TestCase):
    def test_one_row_per_evidenced_activity(self):
        rows = build_rows(*_fixture())
        self.assertEqual(len(rows), 1)
        roles = [m["role"] for m in rows[0]["messages"]]
        self.assertEqual(roles, ["system", "user", "assistant"])

    def test_user_content_is_raw_message_text(self):
        rows = build_rows(*_fixture())
        self.assertIn("Acme", rows[0]["messages"][1]["content"])

    def test_assistant_emits_valid_extraction_json(self):
        rows = build_rows(*_fixture())
        extraction = json.loads(rows[0]["messages"][2]["content"])
        self.assertEqual(extraction["step"], "Customer escalation received")
        self.assertEqual(extraction["category"], "support")
        self.assertEqual(extraction["recommended_mode"], "assisted")
        self.assertIn("confidence", extraction)

    def test_activities_without_source_messages_are_skipped(self):
        processes, scores, messages = _fixture()
        orphan = processes[0].model_copy(deep=True)
        orphan.activities[0] = orphan.activities[0].model_copy(
            update={"id": "a-2", "source_messages": []})
        processes.append(orphan.model_copy(update={"id": "proc-2", "name": "Orphan"}))
        self.assertEqual(len(build_rows(processes, scores, messages)), 1)

    def test_duplicate_pairs_collapse(self):
        processes, scores, messages = _fixture()
        twin = processes[0].model_copy(deep=True)
        twin.activities[0] = twin.activities[0].model_copy(update={"name": "Issue triaged"})
        processes.append(twin)
        rows = build_rows(processes, scores, messages)
        user_texts = {r["messages"][1]["content"] for r in rows}
        self.assertEqual(len(user_texts), 1)  # same evidence text, one row


class TestFormatsAndOutput(unittest.TestCase):
    def test_alpaca_conversion(self):
        row = build_rows(*_fixture())[0]
        alpaca = to_alpaca(row)
        self.assertEqual(set(alpaca), {"instruction", "input", "output"})
        self.assertIn("process analyst", alpaca["instruction"])

    def test_write_jsonl_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "nested" / "out.jsonl"
            rows = build_rows(*_fixture())
            returned = write_jsonl(rows, target)
            self.assertEqual(returned, target)
            lines = target.read_text().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0]), rows[0])

    def test_export_is_credential_free(self):
        # Channels carry credentials excluded from serialization; the exporter
        # only ever touches messages, so no secret can leak into a row.
        rows = build_rows(*_fixture())
        blob = json.dumps(rows)
        self.assertNotIn("credential", blob.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
