"""LangGraph agent that orchestrates invoice extraction and ERP verification."""

import asyncio
import json
import logging
import sys
from typing import TypedDict

from langfuse import get_client
from langgraph.graph import END, StateGraph
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from ai_worker.dspy_engine import create_invoice_processor
from shared.schemas import InvoiceData, ReconciliationDecision

_langfuse = get_client()

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State container for the reconciliation agent graph."""

    raw_text: str
    extracted_invoice: InvoiceData | None
    mcp_result: dict[str, object] | None
    final_decision: ReconciliationDecision | None


async def extract_data(state: AgentState) -> dict[str, InvoiceData]:
    """Node A: Extract structured invoice data from raw text using DSPy.

    Offloads the synchronous DSPy call to a thread to avoid blocking the
    event loop.
    """
    with _langfuse.start_as_current_observation(
        as_type="span",
        name="extract_data",
        input={"raw_text_length": len(state["raw_text"])},
    ) as span:
        processor = create_invoice_processor()
        try:
            prediction = await asyncio.to_thread(
                processor.forward, invoice_text=state["raw_text"]
            )
        except (ConnectionError, TimeoutError) as exc:
            logger.error("LLM provider error during extraction: %s", exc)
            span.update(output={"error": str(exc)}, level="ERROR")
            raise RuntimeError(f"Invoice extraction failed: {exc}") from exc

        invoice: InvoiceData = prediction.structured_invoice
        logger.info(
            "Extracted invoice %s — amount %.2f",
            invoice.invoice_id,
            invoice.total_amount,
        )
        span.update(output=invoice.model_dump())
        return {"extracted_invoice": invoice}


async def verify_with_erp(state: AgentState) -> dict[str, dict[str, object]]:
    """Node B: Verify extracted invoice against ERP via MCP bridge.

    Spins up the MCP bridge server as a subprocess and communicates over
    stdio using the official MCP client SDK.
    """
    invoice = state["extracted_invoice"]
    if invoice is None:
        msg = "Cannot verify: no extracted invoice in state"
        raise ValueError(msg)

    with _langfuse.start_as_current_observation(
        as_type="span",
        name="verify_with_erp",
        input={
            "invoice_id": invoice.invoice_id,
            "amount": invoice.total_amount,
            "vendor_name": invoice.vendor_name,
        },
    ) as span:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_bridge.server"],
        )

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(
                    "verify_purchase_order",
                    arguments={
                        "invoice_id": invoice.invoice_id,
                        "amount": invoice.total_amount,
                    },
                )

        if result.isError:
            logger.error("MCP tool returned error for %s", invoice.invoice_id)
            mcp_result: dict[str, object] = {
                "status": "error",
                "message": "MCP tool error",
            }
            span.update(output=mcp_result, level="ERROR")
            return {"mcp_result": mcp_result}

        raw_text: str = result.content[0].text  # type: ignore[union-attr]
        mcp_result = json.loads(raw_text)
        logger.info(
            "ERP verification for %s: %s", invoice.invoice_id, mcp_result["status"]
        )
        span.update(output=mcp_result)
        return {"mcp_result": mcp_result}


async def make_decision(state: AgentState) -> dict[str, ReconciliationDecision]:
    """Node C: Produce a ReconciliationDecision based on MCP result."""
    mcp_result = state["mcp_result"]
    invoice = state["extracted_invoice"]

    if mcp_result is None or invoice is None:
        msg = "Cannot decide: missing mcp_result or extracted_invoice"
        raise ValueError(msg)

    with _langfuse.start_as_current_observation(
        as_type="span",
        name="make_decision",
        input={
            "invoice_id": invoice.invoice_id,
            "mcp_status": str(mcp_result["status"]),
        },
    ) as span:
        status_str: str = str(mcp_result["status"])

        if status_str == "match":
            decision = ReconciliationDecision(
                status="APPROVED",
                reason=f"Invoice {invoice.invoice_id} matches ERP record.",
                erp_expected_amount=float(mcp_result.get("expected", 0.0)),  # type: ignore[arg-type]
            )
        elif status_str == "discrepancy":
            expected = float(mcp_result.get("expected", 0.0))  # type: ignore[arg-type]
            diff = float(mcp_result.get("diff", 0.0))  # type: ignore[arg-type]
            decision = ReconciliationDecision(
                status="DISCREPANCY",
                reason=(
                    f"Amount mismatch for {invoice.invoice_id}: "
                    f"expected {expected}, diff {diff}."
                ),
                erp_expected_amount=expected,
            )
        else:
            decision = ReconciliationDecision(
                status="HUMAN_REVIEW_NEEDED",
                reason=f"ERP returned '{status_str}' for {invoice.invoice_id}.",
                erp_expected_amount=None,
            )

        logger.info("Decision for %s: %s", invoice.invoice_id, decision.status)
        span.update(
            output=decision.model_dump(),
            metadata={"decision_status": decision.status},
        )
        return {"final_decision": decision}


# — Graph assembly —
_graph = StateGraph(AgentState)
_graph.add_node("extract_data", extract_data)
_graph.add_node("verify_with_erp", verify_with_erp)
_graph.add_node("make_decision", make_decision)

_graph.set_entry_point("extract_data")
_graph.add_edge("extract_data", "verify_with_erp")
_graph.add_edge("verify_with_erp", "make_decision")
_graph.add_edge("make_decision", END)

reconciliation_app = _graph.compile()
