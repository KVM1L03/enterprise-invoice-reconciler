"""Tests for the verify_purchase_order MCP tool."""

import sqlite3
from pathlib import Path

import pytest

from mcp_bridge.server import verify_purchase_order

DB_PATH = Path(__file__).resolve().parent / "erp_mock.db"


def _get_first_po() -> tuple[str, float]:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, expected_amount FROM purchase_orders LIMIT 1",
        ).fetchone()
    assert row is not None, "erp_mock.db has no rows — run seed_data.py or init_db"
    return str(row[0]), float(row[1])


@pytest.mark.asyncio
async def test_valid_match() -> None:
    """Correct ERP amount for an existing PO should return 'match'."""
    inv_id, expected = _get_first_po()
    result = await verify_purchase_order(inv_id, expected)
    assert result["status"] == "match"
    assert result["diff"] == 0.0


@pytest.mark.asyncio
async def test_discrepancy() -> None:
    """Invoice total above ERP expected should return 'discrepancy'."""
    inv_id, expected = _get_first_po()
    stated = round(expected + 150.0, 2)
    result = await verify_purchase_order(inv_id, stated)
    assert result["status"] == "discrepancy"
    assert result["expected"] == expected
    assert result["diff"] == round(expected - stated, 2)


@pytest.mark.asyncio
async def test_sql_injection_returns_not_found() -> None:
    """A malicious invoice_id must be treated as a literal string, not SQL."""
    malicious_id = "INV-2026-001' OR '1'='1"
    result = await verify_purchase_order(malicious_id, 0.0)
    assert result["status"] == "not_found"
