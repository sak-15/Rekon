"""
Pydantic Schemas for Reconciliation Configuration and Results.
Provides type validation, documented parameters for matching rules,
and structured representations of matching telemetry.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

from app.models.reconciliation import (
    ReconciliationRunStatusEnum,
    ReconciliationLayerEnum,
    MatchTypeEnum,
    MatchStatusEnum,
)


class ReconciliationRuleConfig(BaseModel):
    """
    Configurable parameters for matching rules.
    Allows clients or runs to tune tolerances based on their rails and business logic.
    """
    model_config = ConfigDict(from_attributes=True)

    amount_tolerance: Decimal = Field(
        default=Decimal("1.00"),
        description="Maximum absolute difference between invoice and transaction amounts to treat as matched (e.g. ₹1.00 for paisa rounding).",
        ge=Decimal("0.00"),
    )

    layer_1_date_window_days: int = Field(
        default=2,
        description="Allowed date proximity window (± days) between invoice date and transaction captured date for fuzzy matching.",
        ge=0,
    )

    layer_3_bank_window_days: int = Field(
        default=4,
        description="Allowed date clearing window (± days) between settlement payout and bank credit deposit.",
        ge=0,
    )

    enable_fuzzy_matching: bool = Field(
        default=True,
        description="Whether to attempt heuristic customer + amount + date matching when gateway transaction lacks an invoice reference.",
    )

    min_fuzzy_confidence: Decimal = Field(
        default=Decimal("80.00"),
        description="Minimum confidence score threshold (0.00 to 100.00) required to accept a heuristic match.",
        ge=Decimal("0.00"),
        le=Decimal("100.00"),
    )


class Layer1MatchSummary(BaseModel):
    """
    Summary metrics produced by the Layer 1 Matching Engine (Invoices ↔ Gateway Transactions).
    """
    model_config = ConfigDict(from_attributes=True)

    total_invoices_evaluated: int = 0
    matched_invoices: int = 0
    unmatched_invoices: int = 0
    discrepancy_invoices: int = 0

    total_txns_evaluated: int = 0
    matched_txns: int = 0
    unmatched_txns: int = 0

    total_matched_amount: Decimal = Decimal("0.00")
    total_discrepancy_amount: Decimal = Decimal("0.00")

    exact_matches_count: int = 0
    fuzzy_matches_count: int = 0


class Layer2MatchSummary(BaseModel):
    """
    Summary metrics produced by the Layer 2 Matching Engine (Gateway Transactions ↔ Settlement Lines).
    """
    model_config = ConfigDict(from_attributes=True)

    total_txns_evaluated: int = 0
    settled_txns: int = 0
    unsettled_txns: int = 0
    fee_discrepancy_txns: int = 0

    total_settlement_lines_evaluated: int = 0
    matched_lines: int = 0
    unmatched_lines: int = 0

    total_settled_gross_amount: Decimal = Decimal("0.00")
    total_settled_net_amount: Decimal = Decimal("0.00")
    total_fees_deducted: Decimal = Decimal("0.00")
    total_gst_deducted: Decimal = Decimal("0.00")
    total_fee_discrepancy_amount: Decimal = Decimal("0.00")


class Layer3MatchSummary(BaseModel):
    """
    Summary metrics produced by the Layer 3 Matching Engine (Settlement Batches ↔ Bank Credits).
    """
    model_config = ConfigDict(from_attributes=True)

    total_batches_evaluated: int = 0
    matched_batches: int = 0
    unmatched_batches: int = 0
    discrepancy_batches: int = 0

    total_bank_credits_evaluated: int = 0
    matched_bank_credits: int = 0
    unmatched_bank_credits: int = 0

    total_settled_amount: Decimal = Decimal("0.00")
    total_bank_credited_amount: Decimal = Decimal("0.00")
    total_discrepancy_amount: Decimal = Decimal("0.00")

    utr_matches_count: int = 0
    fuzzy_matches_count: int = 0


# =============================================================================
# API Request & Response Schemas
# =============================================================================

class TriggerReconciliationRequest(BaseModel):
    """
    Request body for initiating a new reconciliation run.
    """
    rule_config: Optional[ReconciliationRuleConfig] = None


class ReconciliationRunResponse(BaseModel):
    """
    Full public representation of a Reconciliation Run and its telemetry.
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    status: ReconciliationRunStatusEnum
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    rule_config: Optional[Dict[str, Any]] = None

    # Telemetry Counters
    total_invoices: int
    matched_invoices: int
    unmatched_invoices: int

    total_txns: int
    matched_txns: int
    unmatched_txns: int

    total_settlements: int
    matched_settlements: int
    unmatched_settlements: int

    total_bank_credits: int
    matched_bank_credits: int
    unmatched_bank_credits: int

    # Financial Totals
    invoiced_amount: Decimal
    collected_amount: Decimal
    settled_amount: Decimal
    bank_credited_amount: Decimal
    discrepancy_amount: Decimal

    created_at: datetime


class ReconciliationRunListResponse(BaseModel):
    """
    List of historical reconciliation runs for an organisation.
    """
    items: List[ReconciliationRunResponse]
    total: int


class ReconciliationMatchResponse(BaseModel):
    """
    Detailed audit representation of an individual reconciliation match.
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    org_id: str
    layer: ReconciliationLayerEnum

    invoice_id: Optional[str] = None
    gateway_txn_id: Optional[str] = None
    settlement_line_id: Optional[str] = None
    settlement_batch_id: Optional[str] = None
    bank_credit_id: Optional[str] = None

    match_type: MatchTypeEnum
    confidence_score: Decimal
    status: MatchStatusEnum
    amount_difference: Decimal
    match_details: Optional[Dict[str, Any]] = None
    created_at: datetime


class ReconciliationMatchListResponse(BaseModel):
    """
    Paginated list of reconciliation matches.
    """
    items: List[ReconciliationMatchResponse]
    total: int
    limit: int
    offset: int
