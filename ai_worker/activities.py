"""Temporal Activities for the invoice reconciliation pipeline."""

import asyncio
import logging
import shutil
from datetime import timedelta
from pathlib import Path

from langfuse import get_client
from temporalio import activity
from temporalio.common import RetryPolicy

from ai_worker.agent_graph import reconciliation_app
from shared.pdf_utils import extract_text_from_pdf

_langfuse = get_client()

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

    try:
        with _langfuse.start_as_current_observation(
            as_type="span",
            name="invoice_reconciliation",
            input={"file_path": file_path},
        ) as trace:
            try:
                extracted_text = await extract_text_from_pdf(file_path)

                final_state = await reconciliation_app.ainvoke(
                    {"raw_text": extracted_text}
                )

                decision = final_state["final_decision"]
                if decision is None:
                    msg = (
                        "Reconciliation graph completed without producing a decision"
                    )
                    raise RuntimeError(msg)

                result: dict = decision.model_dump()
                logger.info("Activity complete — decision: %s", result["status"])
                trace.update(
                    output=result, metadata={"status": result["status"]}
                )
                return result
            except Exception:
                trace.update(level="ERROR")
                raise
    finally:
        _langfuse.flush()


APPROVED_STATUSES: frozenset[str] = frozenset({"APPROVED"})


@activity.defn
async def route_invoice_file_activity(file_path: str, status: str) -> str:
    """Move a processed invoice to approved/ or discrepancy/ based on status.

    APPROVED → mock_data/approved/; every other status → mock_data/discrepancy/.
    All disk ops are offloaded via ``asyncio.to_thread`` to keep the
    activity's event loop responsive.
    """
    source = Path(file_path)
    if not source.is_file():
        logger.error("Cannot route missing file: %s", file_path)
        raise FileNotFoundError(f"Source file not found: {file_path}")

    base_dir = source.parent.parent
    target_dir_name = "approved" if status in APPROVED_STATUSES else "discrepancy"
    target_dir = base_dir / target_dir_name

    await asyncio.to_thread(target_dir.mkdir, parents=True, exist_ok=True)

    target_path = target_dir / source.name
    moved = await asyncio.to_thread(shutil.move, str(source), str(target_path))

    logger.info(
        "Routed %s → %s (status=%s)", source.name, target_dir_name, status
    )
    return str(moved)
