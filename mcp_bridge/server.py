"""FastMCP server exposing ERP purchase-order verification as an MCP tool."""

import logging

import aiosqlite
from fastmcp import FastMCP

from shared.paths import ERP_DB_PATH as DB_PATH

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

GLOBAL_TENANT = "global"

mcp = FastMCP("ERP-Bridge")


@mcp.tool()
async def verify_purchase_order(
    invoice_id: str,
    amount: float,
    session_id: str = GLOBAL_TENANT,
) -> dict[str, object]:
    """Check an invoice total against the ERP purchase-order record.

    ``session_id`` scopes the lookup to a single tenant. The dev/local
    tenant is ``"global"``; demo sessions pass their own ``demo_<uuid>``
    so recruiters never see each other's seeded data.

    Returns a dict with 'status' ("match", "discrepancy", "not_found", or
    "error") plus relevant detail fields.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT expected_amount FROM purchase_orders "
                "WHERE id = ? AND session_id = ?",
                (invoice_id, session_id),
            )
            row = await cursor.fetchone()
    except aiosqlite.Error:
        logger.exception("Database error while verifying %s", invoice_id)
        return {"status": "error", "message": "Database error"}

    if row is None:
        return {"status": "not_found", "message": f"No PO found for {invoice_id}"}

    expected: float = row[0]
    diff: float = expected - amount

    if abs(diff) < 0.01:
        return {"status": "match", "expected": expected, "diff": 0.0}

    return {"status": "discrepancy", "expected": expected, "diff": round(diff, 2)}


if __name__ == "__main__":
    mcp.run()
