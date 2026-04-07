"""Temporal Activities for the invoice reconciliation pipeline."""

import logging
from datetime import timedelta

from temporalio import activity
from temporalio.common import RetryPolicy

from ai_worker.agent_graph import reconciliation_app

logger = logging.getLogger(__name__)

RECONCILIATION_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=3,
    non_retryable_error_types=["ValueError", "TypeError"],
)


@activity.defn
async def process_invoice_activity(raw_text: str) -> dict:
    """Execute the full reconciliation graph for a single invoice.

    This activity wraps the LangGraph pipeline (DSPy extraction -> MCP
    verification -> decision routing) and returns a serialisable dict
    suitable for Temporal's gRPC payload format.
    """
    logger.info("Starting invoice reconciliation activity")

    final_state = await reconciliation_app.ainvoke(
        {"raw_text": raw_text}
    )

    decision = final_state["final_decision"]
    if decision is None:
        msg = "Reconciliation graph completed without producing a decision"
        raise RuntimeError(msg)

    result: dict = decision.model_dump()
    logger.info("Activity complete — decision: %s", result["status"])
    return result
