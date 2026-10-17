"""Pattern-based redaction helpers for selected identifiers and secrets.

Regex matching is incomplete and does not establish anonymization or compliance.
Review generated datasets for remaining sensitive information before use.
"""

from __future__ import annotations

import re
from typing import Any


class PIIScrubber:
    """Regex and pattern-based sanitizer for operational text."""

    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
    SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
    API_KEY_PATTERN = re.compile(r"\b(?:sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|xoxb-[A-Za-z0-9-]{20,})\b")
    IP_PATTERN = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")

    @classmethod
    def scrub_text(cls, text: str) -> tuple[str, int]:
        """Scrubs PII from input text and returns sanitized text plus count of redactions."""
        redactions = 0

        def email_repl(_: re.Match) -> str:
            nonlocal redactions
            redactions += 1
            return "[REDACTED_EMAIL]"

        def phone_repl(_: re.Match) -> str:
            nonlocal redactions
            redactions += 1
            return "[REDACTED_PHONE]"

        def ssn_repl(_: re.Match) -> str:
            nonlocal redactions
            redactions += 1
            return "[REDACTED_SSN]"

        def cc_repl(_: re.Match) -> str:
            nonlocal redactions
            redactions += 1
            return "[REDACTED_CC]"

        def api_key_repl(_: re.Match) -> str:
            nonlocal redactions
            redactions += 1
            return "[REDACTED_SECRET]"

        def ip_repl(_: re.Match) -> str:
            nonlocal redactions
            redactions += 1
            return "[REDACTED_IP]"

        cleaned = cls.API_KEY_PATTERN.sub(api_key_repl, text)
        cleaned = cls.CREDIT_CARD_PATTERN.sub(cc_repl, cleaned)
        cleaned = cls.SSN_PATTERN.sub(ssn_repl, cleaned)
        cleaned = cls.EMAIL_PATTERN.sub(email_repl, cleaned)
        cleaned = cls.PHONE_PATTERN.sub(phone_repl, cleaned)
        cleaned = cls.IP_PATTERN.sub(ip_repl, cleaned)

        return cleaned, redactions

    @classmethod
    def scrub_dict(cls, data: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Scrub string values in nested dictionaries/lists without mutating input."""
        total_redactions = 0
        result: dict[str, Any] = {}

        for k, v in data.items():
            result[k], count = cls._scrub_value(v)
            total_redactions += count

        return result, total_redactions

    @classmethod
    def _scrub_value(cls, value: Any) -> tuple[Any, int]:
        if isinstance(value, str):
            return cls.scrub_text(value)
        if isinstance(value, dict):
            return cls.scrub_dict(value)
        if isinstance(value, list):
            scrubbed_list = []
            total_redactions = 0
            for item in value:
                scrubbed_item, count = cls._scrub_value(item)
                scrubbed_list.append(scrubbed_item)
                total_redactions += count
            return scrubbed_list, total_redactions
        return value, 0
