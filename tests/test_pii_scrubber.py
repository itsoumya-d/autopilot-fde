"""Focused regression tests for recursive dictionary-value redaction."""

from copy import deepcopy
import unittest

from backend.distillation.pii_scrubber import PIIScrubber


class TestPIIScrubber(unittest.TestCase):
    def test_scrubs_strings_in_nested_lists(self):
        payload = {"items": [["alice@example.com", ["bob@example.com"]]]}

        scrubbed, count = PIIScrubber.scrub_dict(payload)

        self.assertEqual(scrubbed, {"items": [["[REDACTED_EMAIL]", ["[REDACTED_EMAIL]"]]]})
        self.assertEqual(count, 2)

    def test_scrubs_mixed_dictionary_and_list_nesting(self):
        payload = {
            "owner": "owner@example.com",
            "groups": [
                "first@example.com",
                {"contacts": [[{"email": "second@example.com"}, "third@example.com"]]},
                [[{"details": {"emails": ["fourth@example.com"]}}]],
            ],
            "metadata": {"reviewer": "reviewer@example.com"},
        }

        scrubbed, count = PIIScrubber.scrub_dict(payload)

        self.assertEqual(scrubbed, {
            "owner": "[REDACTED_EMAIL]",
            "groups": [
                "[REDACTED_EMAIL]",
                {"contacts": [[{"email": "[REDACTED_EMAIL]"}, "[REDACTED_EMAIL]"]]},
                [[{"details": {"emails": ["[REDACTED_EMAIL]"]}}]],
            ],
            "metadata": {"reviewer": "[REDACTED_EMAIL]"},
        })
        self.assertEqual(count, 6)

    def test_counts_every_occurrence_once_across_depths(self):
        payload = {
            "message": "alice@example.com and alice@example.com",
            "items": [
                "alice@example.com",
                ["bob@example.com and carol@example.com", {"reply": "dave@example.com"}],
                {"nested": [["erin@example.com", "plain text"]]},
            ],
        }

        scrubbed, count = PIIScrubber.scrub_dict(payload)

        self.assertEqual(scrubbed, {
            "message": "[REDACTED_EMAIL] and [REDACTED_EMAIL]",
            "items": [
                "[REDACTED_EMAIL]",
                ["[REDACTED_EMAIL] and [REDACTED_EMAIL]", {"reply": "[REDACTED_EMAIL]"}],
                {"nested": [["[REDACTED_EMAIL]", "plain text"]]},
            ],
        })
        self.assertEqual(count, 7)

    def test_preserves_empty_containers_and_scalar_values(self):
        cases = [
            {},
            {"list": [], "dict": {}},
            {"nested": [[], {}, [[], {"empty": []}]]},
            {"values": [None, True, False, 0, 42, 3.5, "", "plain text"]},
            {"nested": [[None, True, 42, 3.5, "plain text"]], "value": None},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                scrubbed, count = PIIScrubber.scrub_dict(payload)
                self.assertEqual(scrubbed, payload)
                self.assertEqual(count, 0)

    def test_preserves_dictionary_keys_and_other_value_types(self):
        marker = object()
        unchanged_tuple = ("tuple@example.com",)
        unchanged_bytes = b"bytes@example.com"
        payload = {
            "key@example.com": "plain text",
            "marker": marker,
            "values": [[unchanged_tuple, unchanged_bytes, marker]],
        }

        scrubbed, count = PIIScrubber.scrub_dict(payload)

        self.assertEqual(scrubbed, payload)
        self.assertIs(scrubbed["marker"], marker)
        self.assertIs(scrubbed["values"][0][0], unchanged_tuple)
        self.assertIs(scrubbed["values"][0][1], unchanged_bytes)
        self.assertIs(scrubbed["values"][0][2], marker)
        self.assertEqual(count, 0)

    def test_does_not_mutate_input(self):
        payload = {"items": [["alice@example.com", {"emails": [["bob@example.com"]]}]]}
        original = deepcopy(payload)

        PIIScrubber.scrub_dict(payload)

        self.assertEqual(payload, original)

    def test_returns_independent_dictionary_and_list_containers(self):
        payload = {"items": [["plain text", {"values": [[]]}]]}
        original = deepcopy(payload)

        scrubbed, count = PIIScrubber.scrub_dict(payload)
        scrubbed["items"][0].append("added")
        scrubbed["items"][0][1]["values"][0].append("added")
        scrubbed["items"][0][1]["new"] = "added"

        self.assertEqual(payload, original)
        self.assertEqual(count, 0)

    def test_is_idempotent_and_reports_no_second_pass_redactions(self):
        payload = {
            "email": "alice@example.com",
            "items": [["bob@example.com", {"email": "carol@example.com"}]],
        }

        first, first_count = PIIScrubber.scrub_dict(payload)
        second, second_count = PIIScrubber.scrub_dict(first)

        self.assertEqual(first, {
            "email": "[REDACTED_EMAIL]",
            "items": [["[REDACTED_EMAIL]", {"email": "[REDACTED_EMAIL]"}]],
        })
        self.assertEqual(first_count, 3)
        self.assertEqual(second, first)
        self.assertEqual(second_count, 0)


if __name__ == "__main__":
    unittest.main()
