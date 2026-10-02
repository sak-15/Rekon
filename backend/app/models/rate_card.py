import enum
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional
from sqlalchemy import (
    Column,
    String,
    Numeric,
    DateTime,
    Boolean,
    ForeignKey,
    Enum,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.gateway import GatewayEnum, PaymentMethodEnum


class RateTypeEnum(str, enum.Enum):
    """
    Fee structure type:
    - percentage: standard MDR (e.g. 2.0% of transaction volume)
    - flat: fixed fee per transaction (e.g. ₹5.00 for eNACH mandate debit)
    - hybrid: percentage + fixed fee (e.g. 2.9% + ₹3.00 for international cards)
    """
    PERCENTAGE = "percentage"
    FLAT = "flat"
    HYBRID = "hybrid"


class GatewayRateCard(Base, TimestampMixin):
    """
    Contracted Commercial Rate Card per Tenant.
    Stores the exact negotiated gateway pricing for each payment method and rail.
    Used by the Fee Audit Engine to verify MDR deductions and 18% GST down to the paisa.
    """
    __tablename__ = "gateway_rate_cards"

    org_id = Column(
        String(36),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    gateway = Column(Enum(GatewayEnum), nullable=False, index=True)
    payment_method = Column(
        Enum(PaymentMethodEnum),
        default=PaymentMethodEnum.OTHER,
        nullable=False,
        index=True,
    )
    card_network = Column(String(50), default="all", nullable=False)  # 'all', 'debit', 'credit', 'amex', 'visa'
    is_international = Column(Boolean, default=False, nullable=False)

    rate_type = Column(
        Enum(RateTypeEnum),
        default=RateTypeEnum.PERCENTAGE,
        nullable=False,
    )
    percentage_rate = Column(Numeric(6, 4), default=0.0000, nullable=False)  # e.g. 0.0200 = 2.00%
    flat_fee = Column(Numeric(10, 2), default=0.00, nullable=False)          # e.g. 5.00 = ₹5.00
    gst_rate = Column(Numeric(5, 4), default=0.1800, nullable=False)         # 18% GST (0.1800)

    cap_min_fee = Column(Numeric(10, 2), nullable=True)  # Floor fee minimum
    cap_max_fee = Column(Numeric(10, 2), nullable=True)  # Ceiling fee cap (e.g. ₹20 for debit cards)

    is_active = Column(Boolean, default=True, nullable=False, index=True)
    effective_from = Column(DateTime, nullable=True)
    effective_to = Column(DateTime, nullable=True)
    notes = Column(String(255), nullable=True)

    # Scoped uniqueness ensuring no conflicting overlapping active rules for the same rail
    __table_args__ = (
        UniqueConstraint(
            "org_id",
            "gateway",
            "payment_method",
            "card_network",
            "is_international",
            "is_active",
            name="uq_org_rate_card_rule",
        ),
        Index("ix_rate_cards_lookup", "org_id", "gateway", "payment_method", "is_active"),
    )

    # Relationship
    organisation = relationship("Organisation", back_populates="rate_cards")

    def calculate_expected_charges(self, gross_amount: Decimal) -> Dict[str, Decimal]:
        """
        Calculates expected MDR fee, 18% GST, and net settlement for a given gross amount.
        Applies min/max fee caps and standard half-up paisa rounding.
        """
        amount = Decimal(str(gross_amount))
        pct_rate = Decimal(str(self.percentage_rate))
        flat = Decimal(str(self.flat_fee))
        gst = Decimal(str(self.gst_rate))

        # 1. Base MDR calculation based on rate type
        if self.rate_type == RateTypeEnum.PERCENTAGE:
            calc_fee = amount * pct_rate
        elif self.rate_type == RateTypeEnum.FLAT:
            calc_fee = flat
        else:  # HYBRID
            calc_fee = (amount * pct_rate) + flat

        # 2. Apply regulatory / contracted floor & ceiling caps
        if self.cap_min_fee is not None:
            min_cap = Decimal(str(self.cap_min_fee))
            calc_fee = max(calc_fee, min_cap)

        if self.cap_max_fee is not None:
            max_cap = Decimal(str(self.cap_max_fee))
            calc_fee = min(calc_fee, max_cap)

        # Round MDR fee to nearest paisa (2 decimal places)
        expected_fee = calc_fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # 3. Compute 18% GST on the fee
        calc_gst = expected_fee * gst
        expected_gst = calc_gst.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # 4. Expected Net settlement amount
        expected_net = amount - expected_fee - expected_gst

        return {
            "gross_amount": amount,
            "expected_fee": expected_fee,
            "expected_gst": expected_gst,
            "expected_total_deduction": expected_fee + expected_gst,
            "expected_net_amount": expected_net,
        }

