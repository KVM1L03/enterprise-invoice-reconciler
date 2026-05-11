"""Demo-workspace endpoints: session-scoped seeding and periodic cleanup.

Architecture:
- ``POST /demo/init`` mints a session_id, clones the canonical purchase
  orders into SQLite with that session_id, generates 5 PDFs into
  ``mock_data/invoices/{session_id}/``, sets an httpOnly cookie, and
  returns the session_id + summary to the caller.
- An APScheduler ``AsyncIOScheduler`` runs every 15 min (configured in
  ``main.py`` lifespan) and prunes sessions older than 2 hours: their
  SQLite rows, their per-session PDF dirs, and any approved/discrepancy
  subdirs that were created during reconciliation.

The Postgres ``Batch`` table (frontend / Prisma) is cleaned by a separate
SQL snippet (``scripts/cleanup_demo.sql``) since FastAPI has no Prisma
client; running it as a cron is out of scope for this process.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from pydantic import BaseModel, ConfigDict, Field

from api_gateway.deps import (
    DEMO_SESSION_PREFIX,
    GLOBAL_TENANT,
    get_tenant_id,
    is_demo_mode,
)
from shared.paths import (
    ERP_DB_PATH as _DB_PATH,
    INVOICES_DIR as _INVOICES_DIR,
    MOCK_DATA_DIR as _MOCK_DATA_DIR,
)

logger = logging.getLogger(__name__)

DEMO_SESSION_TTL_SECONDS = 2 * 60 * 60  # 2 hours
DEMO_CLEANUP_INTERVAL_SECONDS = 15 * 60

router = APIRouter(prefix="/demo", tags=["demo"])


# --- Canonical seed set (totals MUST match mcp_bridge/init_db.py SEED_DATA) ---
# 4 fields per record: id, vendor, line_items, pdf_total (post-tax).
# 003/004 are intentional discrepancies — PDF total != ERP expected so the
# reconciliation pipeline routes them to DISCREPANCY.
_CANONICAL_INVOICES: tuple[tuple[str, str, list[tuple[str, int, float, float]], float], ...] = (
    (
        "INV-2026-001",
        "CloudFront Hosting LLC",
        [("API Gateway Tier", 5, 1000.0, 5000.0)],
        5425.00,
    ),
    (
        "INV-2026-002",
        "DataPipe Analytics",
        [("Data Egress Bundle", 9, 4500.0, 40500.0)],
        43942.50,
    ),
    (
        "INV-2026-003",
        "CyberShield Enterprise",
        [("Security Retainer", 3, 5500.0, 16500.0)],
        17902.50,
    ),
    (
        "INV-2026-004",  # DISCREPANCY: ERP expects 16817.50, PDF claims 16867.50
        "SyncCloud Solutions",
        [("Cloud Sync Service", 2, 7500.0, 15000.0), ("Setup Fee", 1, 500.0, 500.0)],
        16867.50,
    ),
    (
        "INV-2026-005",  # DISCREPANCY: ERP expects 7540.75, PDF claims 7000.00
        "Stripe Inc",
        [("Payment Processing", 1, 6451.61, 6451.61)],
        7000.00,
    ),
)


class DemoInvoiceSummary(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)
    invoice_id: str
    vendor: str
    pdf_total: float
    expected_total: float
    expected_status: str = Field(
        ..., description="MATCH or DISCREPANCY (deterministic for the canonical set)"
    )


class DemoInitResponse(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)
    session_id: str
    ttl_seconds: int
    invoices: list[DemoInvoiceSummary]


# --- PDF generation (deterministic; mirrors seed_data.write_invoice_pdf) -----


def _write_invoice_pdf(
    path: Path,
    invoice_id: str,
    vendor: str,
    line_items: list[tuple[str, int, float, float]],
    pdf_total: float,
) -> None:
    subtotal = round(sum(lt for *_, lt in line_items), 2)
    tax = round(pdf_total - subtotal, 2)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "INVOICE", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Invoice Number: {invoice_id}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, "Invoice Date: 2026-04-15", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, f"From: {vendor}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(90, 8, "Description", border=0)
    pdf.cell(25, 8, "Qty", border=0)
    pdf.cell(35, 8, "Unit Price", border=0)
    pdf.cell(35, 8, "Amount", border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    for desc, qty, unit, line_total in line_items:
        pdf.cell(90, 7, desc[:40], border=0)
        pdf.cell(25, 7, str(qty), border=0)
        pdf.cell(35, 7, f"${unit:,.2f}", border=0)
        pdf.cell(35, 7, f"${line_total:,.2f}", border=0,
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(4)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Subtotal: ${subtotal:,.2f}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, f"Tax: ${tax:,.2f}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, f"Total Amount Due: ${pdf_total:,.2f}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))


# --- SQLite seeding (clones canonical purchase_orders under a new session) ---


def _seed_session_rows_sync(session_id: str) -> None:
    """Synchronous SQLite work — called via ``asyncio.to_thread``."""
    with sqlite3.connect(_DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO demo_sessions (session_id, created_at) VALUES (?, ?)",
            (session_id, time.time()),
        )
        cur.execute(
            "INSERT OR REPLACE INTO purchase_orders "
            "(id, session_id, vendor_name, expected_amount) "
            "SELECT id, ?, vendor_name, expected_amount FROM purchase_orders "
            "WHERE session_id = ?",
            (session_id, GLOBAL_TENANT),
        )
        conn.commit()


def _expected_status(pdf_total: float, expected_total: float) -> str:
    return "MATCH" if abs(pdf_total - expected_total) < 0.01 else "DISCREPANCY"


# --- Endpoints ---------------------------------------------------------------


@router.post("/init", response_model=DemoInitResponse, status_code=status.HTTP_201_CREATED)
async def init_demo_session(response: Response) -> DemoInitResponse:
    """Mint a new demo session, seed its 5 invoices, and set a session cookie.

    Refuses to run unless ``DEMO_MODE=true`` — protects local dev from
    accidentally polluting the global tenant with session_id rows.
    """
    if not is_demo_mode():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo workspace is disabled. Set DEMO_MODE=true to enable.",
        )

    session_id = f"{DEMO_SESSION_PREFIX}{uuid.uuid4().hex}"

    # Lookup canonical ERP totals so the response payload can label each
    # invoice as MATCH or DISCREPANCY without rerunning the pipeline.
    expected_by_id: dict[str, float] = {}
    for inv_id, _vendor, _lines, _pdf_total in _CANONICAL_INVOICES:
        expected_by_id[inv_id] = 0.0
    expected_rows = await asyncio.to_thread(_fetch_global_totals, list(expected_by_id))
    for inv_id, exp in expected_rows.items():
        expected_by_id[inv_id] = exp

    # 1. Seed SQLite rows under the new session_id
    await asyncio.to_thread(_seed_session_rows_sync, session_id)

    # 2. Generate PDFs into the per-session directory
    session_dir = _INVOICES_DIR / session_id
    summaries: list[DemoInvoiceSummary] = []
    for inv_id, vendor, lines, pdf_total in _CANONICAL_INVOICES:
        target = session_dir / f"{inv_id}.pdf"
        await asyncio.to_thread(_write_invoice_pdf, target, inv_id, vendor, lines, pdf_total)
        exp = expected_by_id.get(inv_id, pdf_total)
        summaries.append(
            DemoInvoiceSummary(
                invoice_id=inv_id,
                vendor=vendor,
                pdf_total=pdf_total,
                expected_total=exp,
                expected_status=_expected_status(pdf_total, exp),
            )
        )

    logger.info(
        "Initialised demo session %s with %d invoices", session_id, len(summaries)
    )

    # 3. Cookie: httpOnly so the browser sends it back to server actions
    # in Next.js. SameSite=Lax because the recruiter UI is same-site.
    response.set_cookie(
        key="demo_session",
        value=session_id,
        max_age=DEMO_SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=os.environ.get("DEMO_COOKIE_SECURE", "false").lower() == "true",
    )

    return DemoInitResponse(
        session_id=session_id,
        ttl_seconds=DEMO_SESSION_TTL_SECONDS,
        invoices=summaries,
    )


@router.get("/session", response_model=DemoInitResponse | None)
async def get_demo_session(
    tenant_id: Annotated[str, Depends(get_tenant_id)],
) -> DemoInitResponse | None:
    """Return the current session metadata if a valid demo cookie is set."""
    expected_rows = await asyncio.to_thread(
        _fetch_global_totals, [inv[0] for inv in _CANONICAL_INVOICES]
    )
    summaries = [
        DemoInvoiceSummary(
            invoice_id=inv_id,
            vendor=vendor,
            pdf_total=pdf_total,
            expected_total=expected_rows.get(inv_id, pdf_total),
            expected_status=_expected_status(pdf_total, expected_rows.get(inv_id, pdf_total)),
        )
        for inv_id, vendor, _lines, pdf_total in _CANONICAL_INVOICES
    ]
    return DemoInitResponse(
        session_id=tenant_id,
        ttl_seconds=DEMO_SESSION_TTL_SECONDS,
        invoices=summaries,
    )


def _fetch_global_totals(invoice_ids: list[str]) -> dict[str, float]:
    """One-shot read of the canonical ERP totals for the demo response payload."""
    if not invoice_ids:
        return {}
    placeholders = ",".join("?" * len(invoice_ids))
    out: dict[str, float] = {}
    with sqlite3.connect(_DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, expected_amount FROM purchase_orders "
            f"WHERE session_id = ? AND id IN ({placeholders})",
            [GLOBAL_TENANT, *invoice_ids],
        )
        for row in cur.fetchall():
            out[row[0]] = float(row[1])
    return out


# --- Cleanup -----------------------------------------------------------------


def _cleanup_expired_sessions_sync(ttl_seconds: float) -> int:
    """Delete demo sessions whose ``created_at`` is older than ``ttl_seconds``.

    Returns the number of sessions removed. Also rmtrees the per-session
    subdirs under ``mock_data/invoices/``, ``mock_data/approved/``, and
    ``mock_data/discrepancy/``.
    """
    cutoff = time.time() - ttl_seconds
    removed = 0
    with sqlite3.connect(_DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT session_id FROM demo_sessions WHERE created_at < ?", (cutoff,)
        )
        expired = [row[0] for row in cur.fetchall()]

        if not expired:
            return 0

        placeholders = ",".join("?" * len(expired))
        cur.execute(
            f"DELETE FROM purchase_orders WHERE session_id IN ({placeholders})",
            expired,
        )
        cur.execute(
            f"DELETE FROM demo_sessions WHERE session_id IN ({placeholders})",
            expired,
        )
        conn.commit()
        removed = len(expired)

    for session_id in expired:
        for bucket in ("invoices", "approved", "discrepancy"):
            target = _MOCK_DATA_DIR / bucket / session_id
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)

    logger.info("Cleanup removed %d expired demo session(s)", removed)
    return removed


async def cleanup_expired_sessions() -> int:
    """Async wrapper for the scheduler — runs the sync SQLite work off-loop."""
    return await asyncio.to_thread(
        _cleanup_expired_sessions_sync, DEMO_SESSION_TTL_SECONDS
    )
