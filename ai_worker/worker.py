"""Temporal Worker — connects to the cluster and processes invoice reconciliation tasks."""

import asyncio
import logging
import os

from dotenv import load_dotenv
from langfuse import get_client
from openinference.instrumentation.dspy import DSPyInstrumentor
from openinference.instrumentation.litellm import LiteLLMInstrumentor
from temporalio.client import Client
from temporalio.worker import Worker

from ai_worker.activities import (
    process_invoice_activity,
    route_invoice_file_activity,
)
from ai_worker.llm_router import get_configured_lm
from ai_worker.workflows import BatchReconciliationWorkflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

TASK_QUEUE = "invoice-reconciliation-queue"
TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")


async def main() -> None:
    """Start the Temporal worker for invoice reconciliation."""
    load_dotenv()

    # Initialise Langfuse (registers the global OTEL TracerProvider)
    # BEFORE instrumenting DSPy/LiteLLM so their spans use our exporter.
    get_client()
    DSPyInstrumentor().instrument()
    LiteLLMInstrumentor().instrument()

    get_configured_lm()

    client = await Client.connect(TEMPORAL_ADDRESS)
    logger.info("Connected to Temporal at %s", TEMPORAL_ADDRESS)

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[BatchReconciliationWorkflow],
        activities=[process_invoice_activity, route_invoice_file_activity],
    )

    logger.info("Worker listening on task queue '%s'", TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
