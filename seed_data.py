"""Generate randomized invoice PDFs and seed erp_mock.db (3 MATCH + 2 DISCREPANCY)."""

from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

ROOT = Path(__file__).resolve().parent
MOCK_DATA_DIR = ROOT / "mock_data"
INVOICES_DIR = MOCK_DATA_DIR / "invoices"
DB_PATH = ROOT / "mcp_bridge" / "erp_mock.db"

VENDOR_POOL = [
    "Acme Corp",
    "Global Tech",
    "DataSystems",
    "CloudNet",
    "CyberDyne",
    "Initech",
]

LINE_DESC_POOL = [
    "API Gateway Tier",
    "Storage Allocation",
    "Professional Services",
    "Support Retainer",
    "Data Egress Bundle",
    "Compute Hours",
    "License Renewal",
]


@dataclass
class InvoiceBuild:
    invoice_id: str
    vendor: str
    line_items: list[tuple[str, int, float, float]]
    subtotal: float
    tax: float
    db_total: float
    pdf_total: float
    is_match: bool


def _unique_invoice_id(existing: set[str]) -> str:
    while True:
        inv_id = f"INV-{random.randint(10000, 99999)}"
        if inv_id not in existing:
            existing.add(inv_id)
            return inv_id


def _build_line_items(n_lines: int) -> list[tuple[str, int, float, float]]:
    lines: list[tuple[str, int, float, float]] = []
    for _ in range(n_lines):
        desc = random.choice(LINE_DESC_POOL)
        qty = random.randint(1, 8)
        unit = round(random.uniform(100.00, 5000.00) / max(qty, 1), 2)
        line_total = round(qty * unit, 2)
        lines.append((desc, qty, unit, line_total))
    return lines


def _compute_totals(
    lines: list[tuple[str, int, float, float]],
) -> tuple[float, float, float]:
    subtotal = round(sum(lt for *_, lt in lines), 2)
    tax = round(subtotal * 0.085, 2)
    total = round(subtotal + tax, 2)
    return subtotal, tax, total


def _distort_total(correct: float) -> float:
    mode = random.choice(["add_5k", "mul_10", "sub_small"])
    if mode == "add_5k":
        return round(correct + 5000.0, 2)
    if mode == "mul_10":
        return round(correct * 10.0, 2)
    return max(0.01, round(correct - random.uniform(50.0, 500.0), 2))


def build_invoice(is_match: bool, existing_ids: set[str]) -> InvoiceBuild:
    invoice_id = _unique_invoice_id(existing_ids)
    vendor = random.choice(VENDOR_POOL)
    n_lines = random.randint(2, 5)
    line_items = _build_line_items(n_lines)
    subtotal, tax, db_total = _compute_totals(line_items)
    pdf_total = db_total if is_match else _distort_total(db_total)
    return InvoiceBuild(
        invoice_id=invoice_id,
        vendor=vendor,
        line_items=line_items,
        subtotal=subtotal,
        tax=tax,
        db_total=db_total,
        pdf_total=pdf_total,
        is_match=is_match,
    )


def write_invoice_pdf(path: Path, inv: InvoiceBuild) -> None:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "INVOICE", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0, 6, f"Invoice Number: {inv.invoice_id}", new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )
    pdf.cell(0, 6, "Invoice Date: 2026-04-15", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, "Due Date: 2026-05-15", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Bill To: Acme Corporation", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, "123 Enterprise Plaza", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(
        0, 6, "San Francisco, CA 94105 USA", new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, f"From: {inv.vendor}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, "789 Vendor Lane", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, "Seattle, WA 98101 USA", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(90, 8, "Description", border=0)
    pdf.cell(25, 8, "Qty", border=0)
    pdf.cell(35, 8, "Unit Price", border=0)
    pdf.cell(
        35, 8, "Amount", border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )
    pdf.set_font("Helvetica", "", 9)
    for desc, qty, unit, line_total in inv.line_items:
        pdf.cell(90, 7, desc[:40], border=0)
        pdf.cell(25, 7, str(qty), border=0)
        pdf.cell(35, 7, f"${unit:,.2f}", border=0)
        pdf.cell(
            35,
            7,
            f"${line_total:,.2f}",
            border=0,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

    pdf.ln(4)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0, 6, f"Subtotal: ${inv.subtotal:,.2f}", new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )
    pdf.cell(
        0, 6, f"Tax (8.5%): ${inv.tax:,.2f}", new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(
        0,
        8,
        f"Total Amount Due: ${inv.pdf_total:,.2f}",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, "Payment Terms: Net 30", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, "Status: Issued", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))


def clear_all_mock_data_pdfs() -> None:
    """Remove every *.pdf under mock_data/ (invoices, approved, discrepancy, etc.)."""
    if MOCK_DATA_DIR.is_dir():
        for p in sorted(MOCK_DATA_DIR.rglob("*.pdf")):
            if p.is_file():
                try:
                    p.unlink()
                except OSError:
                    pass
    remaining = (
        [p for p in MOCK_DATA_DIR.rglob("*.pdf") if p.is_file()]
        if MOCK_DATA_DIR.is_dir()
        else []
    )
    if remaining:
        rel = MOCK_DATA_DIR.relative_to(ROOT)
        bad = "\n".join(f"  {p}" for p in remaining)
        raise RuntimeError(
            "Nie można usunąć niektórych PDF-ów (często właściciel root z kontenera Docker).\n"
            "Napraw właściciela i uruchom ponownie:\n"
            f'  sudo chown -R "$USER:$USER" {rel}\n'
            "Albo usuń z hosta przez kontener (root w kontenerze):\n"
            f'  docker run --rm -v "$PWD:/work" -w /work alpine:latest '
            f'sh -c \'find {rel} -type f -name "*.pdf" -delete\'\n'
            "Potem: uv run python seed_data.py\n"
            "Pozostałe pliki:\n" + bad
        )
    INVOICES_DIR.mkdir(parents=True, exist_ok=True)


def seed_database(rows: list[tuple[str, str, float]]) -> None:
    schema = """
    CREATE TABLE IF NOT EXISTS purchase_orders (
        id              TEXT PRIMARY KEY,
        vendor_name     TEXT NOT NULL,
        expected_amount REAL NOT NULL
    );
    """
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.executescript(schema)
        cur.execute("DELETE FROM purchase_orders")
        cur.executemany(
            "INSERT OR REPLACE INTO purchase_orders (id, vendor_name, expected_amount) "
            "VALUES (?, ?, ?)",
            rows,
        )
        conn.commit()


def main() -> None:
    random.seed()
    clear_all_mock_data_pdfs()

    existing_ids: set[str] = set()
    builds: list[InvoiceBuild] = []

    for i in range(5):
        is_match = i < 3
        inv = build_invoice(is_match, existing_ids)
        builds.append(inv)
        write_invoice_pdf(INVOICES_DIR / f"{inv.invoice_id}.pdf", inv)

    seed_database([(b.invoice_id, b.vendor, b.db_total) for b in builds])

    print()
    print("  SEED SUMMARY (expect in UI after reconcile)")
    print("  " + "=" * 76)
    hdr = f"  {'Generated ID':<14} {'Vendor':<14} {'DB Amount':>12} {'PDF Amount':>12} {'EXPECTED':<12}"
    print(hdr)
    print("  " + "-" * 76)
    for b in builds:
        status = "Match" if b.is_match else "Discrepancy"
        print(
            f"  {b.invoice_id:<14} {b.vendor:<14} {b.db_total:12.2f} {b.pdf_total:12.2f} {status:<12}"
        )
    print("  " + "=" * 76)
    print(f"  PDFs: {INVOICES_DIR}")
    print(f"  DB:   {DB_PATH} (5 rows)")
    print()


if __name__ == "__main__":
    main()
