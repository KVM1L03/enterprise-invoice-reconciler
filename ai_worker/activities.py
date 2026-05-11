"""Temporal Activities for the invoice reconciliation pipeline."""

import asyncio
import logging
import shutil
from datetime import timedelta
from pathlib import Path

from langfuse import get_client
from temporalio import activity
from temporalio.common import RetryPolicy

from ai_worker.agent_graph import GLOBAL_TENANT, reconciliation_app
from shared.paths import MOCK_DATA_DIR as _MOCK_DATA_DIR
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
async def process_invoice_activity(file_path: str, session_id: str = GLOBAL_TENANT) -> dict:
    """Load a PDF invoice, extract its text, and run the reconciliation graph.

    ``session_id`` is forwarded into the LangGraph state so the MCP call
    can scope its ERP lookup to a single tenant (demo isolation).
    """
    logger.info(
        "Starting invoice reconciliation activity for %s (session=%s)",
        file_path,
        session_id,
    )

    try:
        with _langfuse.start_as_current_observation(
            as_type="span",
            name="invoice_reconciliation",
            input={"file_path": file_path, "session_id": session_id},
        ) as trace:
            try:
                extracted_text = await extract_text_from_pdf(file_path)

                final_state = await reconciliation_app.ainvoke(
                    {"raw_text": extracted_text, "session_id": session_id}
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
async def route_invoice_file_activity(
    file_path: str,
    status: str,
    session_id: str = GLOBAL_TENANT,
) -> str:
    """Move a processed invoice to approved/ or discrepancy/ based on status.

    Routing layout:
      global session → mock_data/{approved,discrepancy}/
      demo session  → mock_data/{approved,discrepancy}/{session_id}/

    Keeping per-session subfolders prevents recruiter PDFs from polluting
    the shared dirs and lets the cleanup job rmtree a whole session at once.
    """
    source = Path(file_path)
    if not source.is_file():
        logger.error("Cannot route missing file: %s", file_path)
        raise FileNotFoundError(f"Source file not found: {file_path}")

    bucket = "approved" if status in APPROVED_STATUSES else "discrepancy"
    target_dir = _MOCK_DATA_DIR / bucket
    if session_id != GLOBAL_TENANT:
        target_dir = target_dir / session_id

    await asyncio.to_thread(target_dir.mkdir, parents=True, exist_ok=True)

    target_path = target_dir / source.name
    moved = await asyncio.to_thread(shutil.move, str(source), str(target_path))

    logger.info(
        "Routed %s → %s (status=%s, session=%s)",
        source.name,
        target_dir,
        status,
        session_id,
    )
    return str(moved)
