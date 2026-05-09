"""Integration test — proves DSPy extracts valid Pydantic InvoiceData from PDF."""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()

from ai_worker.dspy_engine import create_invoice_processor
from shared.pdf_utils import extract_text_from_pdf
from shared.schemas import InvoiceData

HAS_VERTEX_AI = (
    os.environ.get("LLM_PROVIDER", "vertex_ai") == "vertex_ai"
    and bool(os.environ.get("VERTEXAI_PROJECT"))
)
HAS_LEGACY_LLM_KEY = any(
    os.environ.get(key)
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")
)

INVOICE_PATH = (
    Path(__file__).resolve().parent.parent
    / "mock_data"
    / "invoices"
    / "INV-2026-001.pdf"
)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not (HAS_VERTEX_AI or HAS_LEGACY_LLM_KEY),
    reason="No Vertex AI project or legacy LLM API key — skipping integration test",
)
@pytest.mark.skipif(
    not INVOICE_PATH.is_file(),
    reason="Sample invoice PDF missing — run `make seed` before integration tests",
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
