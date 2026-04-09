"""Integration test — proves DSPy extracts valid Pydantic InvoiceData from PDF."""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()

from ai_worker.dspy_engine import create_invoice_processor
from shared.pdf_utils import extract_text_from_pdf
from shared.schemas import InvoiceData

INVOICE_PATH = (
    Path(__file__).resolve().parent.parent
    / "mock_data"
    / "invoices"
    / "INV-2026-001.pdf"
)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"),
    reason="No LLM API keys — skipping integration test",
)
async def test_invoice_extraction_returns_valid_pydantic() -> None:
    """Feed PDF-extracted invoice text through the full LLM pipeline."""
    processor = create_invoice_processor()
    invoice_text = await extract_text_from_pdf(str(INVOICE_PATH))

    result = processor.forward(invoice_text=invoice_text)

    assert isinstance(result.structured_invoice, InvoiceData)
    assert isinstance(result.structured_invoice.total_amount, float)
    assert isinstance(result.structured_invoice.invoice_id, str)
    assert len(result.structured_invoice.invoice_id) > 0
