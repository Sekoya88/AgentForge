"""PII masking service using regex-based detection.

Detects and replaces common PII patterns with [REDACTED:<TYPE>] placeholders.
No external dependencies — uses the standard library `re` module only.
"""

from __future__ import annotations

import copy
import re

# Ordered list of (pattern, replacement_label) tuples.
# Order matters: more specific patterns (SSN, CC) come before generic digits.
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Credit card — 16 digits optionally separated by spaces or hyphens
    (
        re.compile(
            r"\b(?:\d[ -]?){15}\d\b",
        ),
        "CC",
    ),
    # SSN — NNN-NN-NNNN
    (
        re.compile(
            r"\b\d{3}-\d{2}-\d{4}\b",
        ),
        "SSN",
    ),
    # Email
    (
        re.compile(
            r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
        ),
        "EMAIL",
    ),
    # Phone — US and international formats
    # Matches: +1-800-555-1234, (800) 555-1234, 800.555.1234, 8005551234, +44 20 7946 0958
    (
        re.compile(
            r"(?<!\d)"
            r"(?:\+?\d{1,3}[\s.\-]?)?"
            r"(?:\(?\d{2,4}\)?[\s.\-]?)"
            r"\d{3,4}[\s.\-]?\d{4}"
            r"(?!\d)",
        ),
        "PHONE",
    ),
]


class PiiMasker:
    """Stateless PII masker.  Instantiate once and reuse freely."""

    def mask(self, text: str) -> tuple[str, int]:
        """Replace PII patterns in *text* with ``[REDACTED:<TYPE>]`` placeholders.

        Returns
        -------
        tuple[str, int]
            ``(masked_text, hit_count)`` where *hit_count* is the total number
            of replacements made across all pattern types.
        """
        hits = 0
        for pattern, label in _PATTERNS:
            replacement = f"[REDACTED:{label}]"
            text, n = pattern.subn(replacement, text)
            hits += n
        return text, hits

    def mask_messages(self, messages: list[dict]) -> list[dict]:
        """Mask PII in a list of ``{role, content}`` message dicts.

        The original list is not mutated — a deep copy is returned.
        Non-string *content* values are left untouched.
        """
        result: list[dict] = []
        for msg in messages:
            msg_copy = copy.deepcopy(msg)
            content = msg_copy.get("content")
            if isinstance(content, str):
                masked, _ = self.mask(content)
                msg_copy["content"] = masked
            result.append(msg_copy)
        return result
