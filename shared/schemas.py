from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Optional

class InvoiceData(BaseModel):
    """
    Strict representation of extracted invoice data.
    Used by DSPy to enforce the LLM output format.
    """
    model_config = ConfigDict(strict=True)

    invoice_id: str = Field(
        ..., 
        description="Unique identifier or number of the invoice (e.g., 'INV-2026-001')."
    )
    vendor_name: str = Field(
        ..., 
        description="Full, official name of the vendor or company issuing the invoice."
    )
    total_amount: float = Field(
        ..., 
        description="Total amount on the invoice. Must be a pure float (e.g., 1500.50). Do NOT include currency symbols like '$'."
    )

class ReconciliationDecision(BaseModel):
    """
    The final output from the LangGraph Agent after checking the ERP database.
    """
    status: Literal["APPROVED", "DISCREPANCY", "HUMAN_REVIEW_NEEDED"] = Field(
        ...,
        description="The final routing status for the invoice."
    )
    reason: str = Field(
        ..., 
        description="A concise explanation of why this decision was made (e.g., 'Matches ERP data perfectly' or 'Expected 1000.0, found 1000.50')."
    )
    erp_expected_amount: Optional[float] = Field(
        default=None,
        description="The amount found in the ERP system, if applicable."
    )