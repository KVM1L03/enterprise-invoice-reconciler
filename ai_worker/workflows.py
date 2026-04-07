"""Temporal Workflow for batch invoice reconciliation."""

import asyncio
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ai_worker.activities import (
        RECONCILIATION_RETRY_POLICY,
        process_invoice_activity,
    )


@workflow.defn
class BatchReconciliationWorkflow:
    """Orchestrates concurrent reconciliation of a batch of invoices."""

    @workflow.run
    async def run(self, invoices: list[str]) -> dict:
        """Process all invoices concurrently via Temporal Activities."""
        tasks: list = []
        for invoice_text in invoices:
            tasks.append(
                workflow.execute_activity(
                    process_invoice_activity,
                    args=[invoice_text],
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RECONCILIATION_RETRY_POLICY,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        summary: dict[str, dict] = {}
        for idx, result in enumerate(results):
            key = f"invoice_{idx}"
            if isinstance(result, BaseException):
                workflow.logger.error(
                    "Invoice %d failed: %s", idx, result
                )
                summary[key] = {"status": "SYSTEM_ERROR", "error": str(result)}
            else:
                summary[key] = result

        return summary
