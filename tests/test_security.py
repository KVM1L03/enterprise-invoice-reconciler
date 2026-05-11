"""Unit tests for the PII scrubber used in the telemetry pipeline."""

from __future__ import annotations

import pytest

from ai_worker.security import PIIScrubber


@pytest.fixture
def scrubber() -> PIIScrubber:
    return PIIScrubber()


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        # IBAN — Polish, German, French, spaced
        ("Account: PL61109010140000071219812874", "IBAN"),
        ("DE89 3704 0044 0532 0130 00", "IBAN"),
        ("Send to FR1420041010050500013M02606 please", "IBAN"),
        # SSN
        ("SSN 123-45-6789", "SSN"),
        ("SSN: 123 45 6789", "SSN"),
        # EIN
        ("EIN 12-3456789", "EIN"),
        # NIP (Polish tax ID)
        ("NIP: 123-456-78-90", "NIP"),
        # Credit card
        ("Card: 4111 1111 1111 1111", "CARD"),
        ("4111-1111-1111-1111 charged", "CARD"),
    ],
)
def test_scrub_redacts_known_pii(scrubber: PIIScrubber, text: str, kind: str) -> None:
    out = scrubber.scrub(text)
    assert f"[REDACTED:{kind}]" in out, f"expected {kind} placeholder in {out!r}"
    # Round-trip: re-scrubbing the output is a no-op (placeholders are clean).
    assert scrubber.scrub(out) == out


def test_scrub_preserves_non_pii(scrubber: PIIScrubber) -> None:
    text = "Invoice INV-2026-001 from Acme Corp for $1,234.56 due 2026-05-15."
    assert scrubber.scrub(text) == text


def test_scrub_handles_empty_and_non_string(scrubber: PIIScrubber) -> None:
    assert scrubber.scrub("") == ""
    # Non-string inputs (OTel attribute values can be int, float, list...)
    # must round-trip unchanged.
    assert scrubber.scrub(None) is None  # type: ignore[arg-type]
    assert scrubber.scrub(42) == 42  # type: ignore[arg-type]


def test_scrub_chains_multiple_matches(scrubber: PIIScrubber) -> None:
    text = (
        "Vendor: Acme Corp\n"
        "IBAN: PL61109010140000071219812874\n"
        "Tax ID (EIN): 12-3456789\n"
        "Owner SSN 555-12-3456"
    )
    out = scrubber.scrub(text)
    assert "[REDACTED:IBAN]" in out
    assert "[REDACTED:EIN]" in out
    assert "[REDACTED:SSN]" in out
    # No raw identifiers leak through
    assert "PL61109010140000071219812874" not in out
    assert "12-3456789" not in out
    assert "555-12-3456" not in out


def test_has_pii_flags_dirty_text(scrubber: PIIScrubber) -> None:
    assert scrubber.has_pii("My IBAN is DE89370400440532013000") is True
    assert scrubber.has_pii("Plain invoice with no identifiers") is False
    assert scrubber.has_pii("") is False


def test_invoice_id_not_misclassified_as_pii(scrubber: PIIScrubber) -> None:
    """INV-2026-001 must not match the SSN/EIN patterns."""
    text = "Invoice number INV-2026-001 totals $5,425.00"
    assert "[REDACTED" not in scrubber.scrub(text)
