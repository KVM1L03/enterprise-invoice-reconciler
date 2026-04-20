"""LangGraph agent that orchestrates invoice extraction and ERP verification."""

import asyncio
import hashlib
import json
import logging
import re
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

# Prompt-injection tells that legitimate invoice fields should never contain.
_INJECTION_PATTERNS = re.compile(
    r"(ignore\s+(previous|all|above)|system\s*:|<\|.*?\|>|override\s+instructions)",
    re.IGNORECASE,
)
_MAX_VENDOR_LEN = 200
_MAX_INVOICE_ID_LEN = 100
_MAX_REASONABLE_AMOUNT = 10_000_000.0


def _vendor_hash(name: str) -> str:
    """Stable short fingerprint — lets you correlate without leaking the vendor."""
    return hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]


def _redact_invoice(invoice: InvoiceData) -> dict[str, object]:
    return {
        "invoice_id": invoice.invoice_id,
        "vendor_hash": _vendor_hash(invoice.vendor_name),
        "total_amount": invoice.total_amount,
    }


def _sanity_check_invoice(invoice: InvoiceData) -> list[str]:
    """Flag extractions that look tampered with (prompt injection in the PDF)."""
    warnings: list[str] = []
    if invoice.total_amount <= 0 or invoice.total_amount > _MAX_REASONABLE_AMOUNT:
        warnings.append("amount_out_of_range")
    if "\n" in invoice.invoice_id or len(invoice.invoice_id) > _MAX_INVOICE_ID_LEN:
        warnings.append("invoice_id_malformed")
    if "\n" in invoice.vendor_name or len(invoice.vendor_name) > _MAX_VENDOR_LEN:
        warnings.append("vendor_name_malformed")
    if _INJECTION_PATTERNS.search(invoice.invoice_id):
        warnings.append("invoice_id_injection_pattern")
    if _INJECTION_PATTERNS.search(invoice.vendor_name):
        warnings.append("vendor_name_injection_pattern")
    return warnings


class AgentState(TypedDict):
    """State container for the reconciliation agent graph."""

    raw_text: str
    extracted_invoice: InvoiceData | None
    extraction_warnings: list[str]
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
        warnings = _sanity_check_invoice(invoice)
        logger.info(
            "Extracted invoice %s — amount %.2f",
            invoice.invoice_id,
            invoice.total_amount,
        )
        if warnings:
            logger.warning(
                "Extraction sanity warnings for %s: %s",
                invoice.invoice_id,
                warnings,
            )
        span.update(
            output=_redact_invoice(invoice),
            metadata={"extraction_warnings": warnings} if warnings else None,
            level="WARNING" if warnings else "DEFAULT",
        )
        return {"extracted_invoice": invoice, "extraction_warnings": warnings}


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
            "vendor_hash": _vendor_hash(invoice.vendor_name),
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

    warnings: list[str] = state.get("extraction_warnings", [])

    with _langfuse.start_as_current_observation(
        as_type="span",
        name="make_decision",
        input={
            "invoice_id": invoice.invoice_id,
            "mcp_status": str(mcp_result["status"]),
            "extraction_warnings": warnings,
        },
    ) as span:
        status_str: str = str(mcp_result["status"])

        if warnings:
            # Suspicious extraction — never auto-approve, regardless of ERP match.
            decision = ReconciliationDecision(
                status="HUMAN_REVIEW_NEEDED",
                reason=(
                    f"Extraction flagged {len(warnings)} anomaly signal(s); "
                    "requires human review."
                ),
                erp_expected_amount=None,
            )
        elif status_str == "match":
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
