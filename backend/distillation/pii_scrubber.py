"""GDPR & EU AI Act compliant automated PII (Personally Identifiable Information) scrubber.

Pre-processes all enterprise operational messages, emails, and ticket data before
distillation or fine-tuning dataset generation to guarantee zero personal data leakage.
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
        """Recursively scrub all string values inside a dictionary."""
        total_redactions = 0
        result: dict[str, Any] = {}

        for k, v in data.items():
            if isinstance(v, str):
                scrubbed_v, count = cls.scrub_text(v)
                result[k] = scrubbed_v
                total_redactions += count
            elif isinstance(v, dict):
                scrubbed_dict, count = cls.scrub_dict(v)
                result[k] = scrubbed_dict
                total_redactions += count
            elif isinstance(v, list):
                scrubbed_list = []
                for item in v:
                    if isinstance(item, str):
                        s_item, count = cls.scrub_text(item)
                        scrubbed_list.append(s_item)
                        total_redactions += count
                    elif isinstance(item, dict):
                        s_item, count = cls.scrub_dict(item)
                        scrubbed_list.append(s_item)
                        total_redactions += count
                    else:
                        scrubbed_list.append(item)
                result[k] = scrubbed_list
            else:
                result[k] = v

        return result, total_redactions
