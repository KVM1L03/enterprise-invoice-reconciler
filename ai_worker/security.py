"""PII redaction for LLM telemetry.

The scope is strictly telemetry: this module is invoked from the OTel
``SpanProcessor`` pipeline (see ``ai_worker.otel_scrubber``) so that raw
invoice text containing IBANs, SSNs, or other identifiers never crosses
the network boundary to Langfuse.

It is NOT used to mutate LLM inputs, extraction results, or database
records — the model still receives the full document for context, and
Prisma/SQLite only persist structured ``InvoiceData`` (invoice_id,
vendor_name, total_amount), none of which are PII.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final


# --- Regex catalogue ---------------------------------------------------------
#
# The patterns deliberately err on the side of false positives. In the
# telemetry path a false positive only redacts a non-PII string; a false
# negative leaks real PII to a third-party server. We take the safer cost.

# IBAN: 2-letter country code + 2 check digits + 11-30 alphanumerics,
# optionally grouped in 4-character blocks separated by spaces. The
# ``\b`` anchors prevent matching mid-word.
_IBAN_RE: Final = re.compile(
    r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}[ ]?[A-Z0-9]{1,4}\b"
)

# US SSN: 3-2-4 digits with optional hyphens or spaces. The leading
# negative lookahead rejects 000/666/9## area numbers (invalid SSNs).
_SSN_RE: Final = re.compile(
    r"\b(?!000|666|9\d{2})\d{3}[- ]?(?!00)\d{2}[- ]?(?!0000)\d{4}\b"
)

# US EIN (employer tax ID): ##-#######
_EIN_RE: Final = re.compile(r"\b\d{2}-\d{7}\b")

# Polish NIP (10 digits, optionally with dashes): ###-###-##-## or 10 raw digits
# Anchored to avoid eating invoice numbers; requires the standard NIP separator
# pattern OR a leading "NIP" token.
_NIP_RE: Final = re.compile(
    r"(?:\bNIP[:\s]*)?(\d{3}-\d{3}-\d{2}-\d{2}|\d{3}-\d{2}-\d{2}-\d{3})\b",
    re.IGNORECASE,
)

# Credit-card-ish: 4 groups of 4 digits with optional separators (-, space).
# Catches Visa/MC/Amex shapes without trying to Luhn-validate (we'd rather
# over-redact a non-card number than miss a real one).
_CARD_RE: Final = re.compile(r"\b(?:\d[ -]?){13,19}\b")


@dataclass(frozen=True, slots=True)
class _Rule:
    kind: str
    pattern: re.Pattern[str]


_RULES: Final[tuple[_Rule, ...]] = (
    _Rule("IBAN", _IBAN_RE),
    _Rule("CARD", _CARD_RE),  # Run before SSN so 16-digit numbers don't get
    _Rule("EIN", _EIN_RE),    # split into SSN+leftover by the SSN matcher.
    _Rule("NIP", _NIP_RE),
    _Rule("SSN", _SSN_RE),
)


class PIIScrubber:
    """Stateless regex-based redactor for high-risk identifiers.

    The class is intentionally not configurable — every caller gets the
    same set of rules so telemetry semantics stay consistent across
    services. Construct once and reuse (it's cheap, but the pre-compiled
    regexes are module-level constants so even per-call construction is
    fine).
    """

    PLACEHOLDER_FMT: Final = "[REDACTED:{kind}]"

    def scrub(self, text: str) -> str:
        """Return ``text`` with every matched identifier replaced.

        Non-string inputs are returned unchanged so callers in the OTel
        pipeline can pass arbitrary attribute values without type-checking
        ahead of time.
        """
        if not isinstance(text, str) or not text:
            return text
        out = text
        for rule in _RULES:
            placeholder = self.PLACEHOLDER_FMT.format(kind=rule.kind)
            out = rule.pattern.sub(placeholder, out)
        return out

    def has_pii(self, text: str) -> bool:
        """Cheap presence check — useful for emitting redaction counters."""
        if not isinstance(text, str) or not text:
            return False
        return any(rule.pattern.search(text) for rule in _RULES)
