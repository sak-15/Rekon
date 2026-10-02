from decimal import Decimal
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class CashflowWaterfallStep(BaseModel):
    step_key: str
    label: str
    amount: Decimal
    percentage_of_gross: float
    step_type: str  # "starting", "deduction", "net_realized"
    description: str


class GatewayPerformanceItem(BaseModel):
    gateway: str
    transaction_count: int
    gross_volume: Decimal
    total_fee: Decimal
    total_gst: Decimal
    total_deductions: Decimal
    effective_take_rate_pct: float
    discrepancy_count: int
    overcharge_amount: Decimal
    volume_share_pct: float


class ExecutiveAlertItem(BaseModel):
    id: str
    severity: str  # "critical", "warning", "info", "success"
    title: str
    description: str
    action_label: Optional[str] = None
    action_target: Optional[str] = None  # tab navigation or action


class ExecutiveKPISummary(BaseModel):
    # Core Revenue & Cash
    gross_billed_amount: Decimal
    invoice_count: int
    gross_gateway_volume: Decimal
    gateway_txn_count: int
    net_settled_cash: Decimal
    bank_credit_count: int

    # Deductions & Take-Rate
    total_gateway_fees: Decimal
    total_gateway_gst: Decimal
    total_gateway_deductions: Decimal
    blended_take_rate_pct: float

    # Audit & Exposure
    fee_leakage_detected: Decimal
    overcharged_txns_count: int
    unresolved_exposure: Decimal
    open_exceptions_count: int

    # Financial Health Index
    health_score: float  # 0 to 100
    health_status: str   # "EXCELLENT", "GOOD", "NEEDS_ATTENTION", "CRITICAL"
    matched_invoices_pct: float
    settled_batches_pct: float


class ExecutiveDashboardResponse(BaseModel):
    summary: ExecutiveKPISummary
    waterfall: List[CashflowWaterfallStep]
    gateway_comparison: List[GatewayPerformanceItem]
    actionable_alerts: List[ExecutiveAlertItem]
    last_updated: str

