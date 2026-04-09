"""Temporal Activities for the invoice reconciliation pipeline."""

import logging
from datetime import timedelta

from temporalio import activity
from temporalio.common import RetryPolicy

from ai_worker.agent_graph import reconciliation_app
from shared.pdf_utils import extract_text_from_pdf

logger = logging.getLogger(__name__)

RECONCILIATION_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=3,
    non_retryable_error_types=["ValueError", "TypeError", "FileNotFoundError"],
)


@activity.defn
async def process_invoice_activity(file_path: str) -> dict:
    """Load a PDF invoice, extract its text, and run the reconciliation graph.

    The activity reads and parses the PDF (I/O + CPU-bound work is
    offloaded via ``asyncio.to_thread`` inside ``extract_text_from_pdf``),
    then feeds the text into the LangGraph pipeline (DSPy extraction ->
    MCP verification -> decision routing) and returns a serialisable dict
    suitable for Temporal's gRPC payload format.
    """
    logger.info("Starting invoice reconciliation activity for %s", file_path)

    extracted_text = await extract_text_from_pdf(file_path)

    final_state = await reconciliation_app.ainvoke(
        {"raw_text": extracted_text}
    )

    decision = final_state["final_decision"]
    if decision is None:
        msg = "Reconciliation graph completed without producing a decision"
        raise RuntimeError(msg)

    result: dict = decision.model_dump()
    logger.info("Activity complete — decision: %s", result["status"])
    return result
