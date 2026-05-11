"""Temporal Workflow for batch invoice reconciliation."""

import asyncio
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ai_worker.activities import (
        RECONCILIATION_RETRY_POLICY,
        process_invoice_activity,
        route_invoice_file_activity,
    )

GLOBAL_TENANT = "global"


@workflow.defn
class BatchReconciliationWorkflow:
    """Orchestrates concurrent reconciliation + file routing of a batch of invoices."""

    @workflow.run
    async def run(
        self,
        file_paths: list[str],
        session_id: str = GLOBAL_TENANT,
    ) -> dict:
        """Phase 1: reconcile invoices. Phase 2: move files to approved/discrepancy.

        ``session_id`` propagates through every activity so the MCP lookup
        and the routing target dir stay scoped to a single tenant.
        """

        # --- Phase 1: Reconciliation (parallel) ---
        tasks: list = []
        for file_path in file_paths:
            tasks.append(
                workflow.execute_activity(
                    process_invoice_activity,
                    args=[file_path, session_id],
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RECONCILIATION_RETRY_POLICY,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # --- Phase 2: File routing (parallel, only successful reconciliations) ---
        routing_tasks: list = []
        routing_indices: list[int] = []

        for idx, (file_path, result) in enumerate(zip(file_paths, results)):
            if isinstance(result, BaseException):
                workflow.logger.warning(
                    "Skipping routing for invoice %d (reconciliation failed)", idx
                )
                continue
            if not isinstance(result, dict) or "status" not in result:
                workflow.logger.warning(
                    "Skipping routing for invoice %d (malformed result)", idx
                )
                continue

            routing_tasks.append(
                workflow.execute_activity(
                    route_invoice_file_activity,
                    args=[file_path, result["status"], session_id],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RECONCILIATION_RETRY_POLICY,
                )
            )
            routing_indices.append(idx)

        routing_results = await asyncio.gather(
            *routing_tasks, return_exceptions=True
        )

        # --- Build final summary ---
        summary: dict[str, dict] = {}
        for idx, result in enumerate(results):
            key = f"invoice_{idx}"
            if isinstance(result, BaseException):
                workflow.logger.error("Invoice %d failed: %s", idx, result)
                summary[key] = {"status": "SYSTEM_ERROR", "error": str(result)}
            else:
                summary[key] = dict(result)

        for position, idx in enumerate(routing_indices):
            key = f"invoice_{idx}"
            routing_result = routing_results[position]
            if isinstance(routing_result, BaseException):
                workflow.logger.error(
                    "Routing failed for invoice %d: %s", idx, routing_result
                )
                summary[key]["routing_error"] = str(routing_result)
            else:
                summary[key]["routed_to"] = routing_result

        return summary
