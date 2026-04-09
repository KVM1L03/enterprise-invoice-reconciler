"""Asynchronous PDF text extraction via PyMuPDF (fitz)."""

import asyncio
import logging
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def _extract_sync(file_path: str) -> str:
    """Blocking PDF text extraction — CALL ONLY via asyncio.to_thread."""
    text_parts: list[str] = []
    with fitz.open(file_path) as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts)


async def extract_text_from_pdf(file_path: str) -> str:
    """Extract plain text from a PDF file without blocking the event loop.

    Offloads fitz's synchronous, CPU-bound work via ``asyncio.to_thread``
    so the calling async context (Temporal Activity, FastAPI route)
    remains responsive.

    Raises:
        FileNotFoundError: When ``file_path`` does not exist on disk.
    """
    if not Path(file_path).is_file():
        logger.error("PDF not found: %s", file_path)
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    logger.info("Extracting text from %s", file_path)
    text = await asyncio.to_thread(_extract_sync, file_path)
    logger.info("Extracted %d chars from %s", len(text), file_path)
    return text
