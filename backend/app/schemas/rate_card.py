from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from app.models.gateway import GatewayEnum, PaymentMethodEnum
from app.models.rate_card import RateTypeEnum


class GatewayRateCardBase(BaseModel):
    gateway: GatewayEnum
    payment_method: PaymentMethodEnum
    card_network: str = Field(default="all", description="Card network: 'all', 'debit', 'credit', 'visa', 'mastercard', 'amex'")
    is_international: bool = Field(default=False, description="Whether this rate applies to international cards")
    rate_type: RateTypeEnum = Field(default=RateTypeEnum.PERCENTAGE, description="percentage, flat, or hybrid")
    percentage_rate: Decimal = Field(default=Decimal("0.0000"), ge=0, le=1, description="MDR rate as decimal (e.g. 0.0200 = 2.0%)")
    flat_fee: Decimal = Field(default=Decimal("0.00"), ge=0, description="Flat fee per transaction (e.g. 5.00 = ₹5.00)")
    gst_rate: Decimal = Field(default=Decimal("0.1800"), ge=0, le=1, description="Mandatory GST rate (default 0.1800 = 18%)")
    cap_min_fee: Optional[Decimal] = Field(default=None, ge=0, description="Optional minimum fee floor")
    cap_max_fee: Optional[Decimal] = Field(default=None, ge=0, description="Optional maximum fee ceiling (e.g. ₹20 for debit cards)")
    is_active: bool = Field(default=True)
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=255)


class GatewayRateCardCreate(GatewayRateCardBase):
    pass


class GatewayRateCardUpdate(BaseModel):
    rate_type: Optional[RateTypeEnum] = None
    percentage_rate: Optional[Decimal] = Field(default=None, ge=0, le=1)
    flat_fee: Optional[Decimal] = Field(default=None, ge=0)
    gst_rate: Optional[Decimal] = Field(default=None, ge=0, le=1)
    cap_min_fee: Optional[Decimal] = None
    cap_max_fee: Optional[Decimal] = None
    is_active: Optional[bool] = None
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    notes: Optional[str] = None


class GatewayRateCardResponse(GatewayRateCardBase):
    id: str
    org_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GatewayRateCardListResponse(BaseModel):
    items: List[GatewayRateCardResponse]
    total: int


class CalculateFeeRequest(BaseModel):
    gross_amount: Decimal = Field(gt=0, description="Gross charge amount to calculate expected MDR & GST for")
    rate_card_id: Optional[str] = None


class CalculateFeeResponse(BaseModel):
    gross_amount: Decimal
    expected_fee: Decimal
    expected_gst: Decimal
    expected_total_deduction: Decimal
    expected_net_amount: Decimal
    effective_take_rate_pct: Decimal


class AuditedTransactionResponse(BaseModel):
    txn_id: str
    gateway: str
    payment_method: str
    card_network: str
    is_international: bool
    captured_at: Optional[datetime]
    gross_amount: float
    actual_fee: float
    actual_gst: float
    actual_total_deduction: float
    expected_fee: float
    expected_gst: float
    expected_total_deduction: float
    fee_variance: float
    gst_variance: float
    total_overcharge: float
    audit_status: str
    dispute_category: str
    explanation: str
    rate_card_applied: Optional[str] = None


class CategoryBreakdownItem(BaseModel):
    count: int
    amount: float


class FeeAuditResponse(BaseModel):
    total_audited: int
    total_gross_volume: float
    total_actual_fees: float
    total_expected_fees: float
    total_actual_gst: float
    total_expected_gst: float
    total_overcharged_amount: float
    total_undercharged_amount: float
    net_variance: float
    verified_count: int
    overcharged_count: int
    undercharged_count: int
    discrepancies_by_category: dict
    items: List[AuditedTransactionResponse]
