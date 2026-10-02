"""
Pydantic Schemas for Reconciliation Exceptions and Resolution Queue.
"""

from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.models.reconciliation_exception import (
    ExceptionTypeEnum,
    ExceptionSeverityEnum,
    ResolutionStatusEnum,
    ResolutionActionEnum,
)


class ReconciliationExceptionResponse(BaseModel):
    id: str
    org_id: str
    run_id: Optional[str] = None

    exception_type: ExceptionTypeEnum
    severity: ExceptionSeverityEnum
    status: ResolutionStatusEnum

    # Entity Pointers
    invoice_id: Optional[str] = None
    gateway_txn_id: Optional[str] = None
    settlement_batch_id: Optional[str] = None
    settlement_line_id: Optional[str] = None
    bank_credit_id: Optional[str] = None

    # Human-friendly entity summaries for clean UI
    entity_reference: Optional[str] = None
    customer_info: Optional[str] = None

    # Monetary values
    expected_amount: float
    actual_amount: float
    discrepancy_amount: float

    # Diagnosis
    title: str
    root_cause_explanation: str
    suggested_action: Optional[str] = None

    # Resolution Audit
    resolution_action: Optional[ResolutionActionEnum] = None
    resolution_notes: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExceptionListResponse(BaseModel):
    items: List[ReconciliationExceptionResponse]
    total: int
    limit: int
    offset: int


class ExceptionSummaryResponse(BaseModel):
    total_exceptions: int
    open_count: int
    investigating_count: int
    resolved_count: int
    written_off_count: int
    total_unresolved_exposure: float
    severity_breakdown: Dict[str, int]
    type_breakdown: Dict[str, Dict[str, Any]]


class ManualMatchRequest(BaseModel):
    target_entity_type: str = Field(..., description="'gateway_txn', 'invoice', or 'bank_credit'")
    target_entity_id: str = Field(..., description="UUID of the target record to link")
    notes: Optional[str] = Field(default=None, description="Audit justification note")


class WriteOffRequest(BaseModel):
    notes: Optional[str] = Field(default=None, description="Reason for write-off to Rounding Expense")
    max_allowed: Optional[Decimal] = Field(default=Decimal("50.00"), description="Safety limit")


class BatchWriteOffRequest(BaseModel):
    max_threshold: Decimal = Field(default=Decimal("5.00"), description="Threshold under which to write off all open deltas")


class UpdateStatusRequest(BaseModel):
    status: ResolutionStatusEnum
    notes: Optional[str] = None

