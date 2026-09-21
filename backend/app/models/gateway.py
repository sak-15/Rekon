import enum
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Enum, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.invoice import ReconciliationStatusEnum


class GatewayEnum(str, enum.Enum):
    RAZORPAY = "razorpay"
    STRIPE = "stripe"
    CASHFREE = "cashfree"
    PAYU = "payu"


class PaymentMethodEnum(str, enum.Enum):
    UPI = "upi"
    CARD = "card"
    ENACH = "enach"
    NETBANKING = "netbanking"
    WALLET = "wallet"
    OTHER = "other"


class TxnStatusEnum(str, enum.Enum):
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    DISPUTED = "disputed"


class SettlementStatusEnum(str, enum.Enum):
    UNSETTLED = "unsettled"
    SETTLED = "settled"


class GatewayTransaction(Base, TimestampMixin):
    """
    Payment Gateway Transactions (Razorpay, Stripe, etc.)
    Represents actual charges attempted, fees deducted, and net amounts.
    """
    __tablename__ = "gateway_txns"

    org_id = Column(String(36), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False, index=True)
    upload_job_id = Column(String(36), ForeignKey("upload_jobs.id", ondelete="SET NULL"), nullable=True, index=True)

    txn_id = Column(String(100), nullable=False)
    gateway = Column(Enum(GatewayEnum), nullable=False, index=True)
    payment_method = Column(Enum(PaymentMethodEnum), default=PaymentMethodEnum.OTHER, nullable=False)

    invoice_ref = Column(String(100), nullable=True, index=True)
    customer_email = Column(String(255), nullable=True)
    customer_contact = Column(String(50), nullable=True)

    # Monetary Breakdown
    amount = Column(Numeric(12, 2), nullable=False)            # Gross charged amount
    currency = Column(String(3), default="INR", nullable=False)
    status = Column(Enum(TxnStatusEnum), default=TxnStatusEnum.CAPTURED, nullable=False)

    gateway_fee = Column(Numeric(12, 2), default=0.00, nullable=False)     # MDR fee
    gateway_fee_gst = Column(Numeric(12, 2), default=0.00, nullable=False) # 18% GST on MDR
    net_amount = Column(Numeric(12, 2), nullable=False)                    # amount - fee - gst

    captured_at = Column(DateTime, nullable=False, index=True)

    # Reconciliation & Settlement tracking
    settlement_status = Column(Enum(SettlementStatusEnum), default=SettlementStatusEnum.UNSETTLED, nullable=False)
    reconciliation_status = Column(
        Enum(ReconciliationStatusEnum), default=ReconciliationStatusEnum.UNMATCHED, nullable=False, index=True
    )

    # Relationships
    organisation = relationship("Organisation", back_populates="gateway_txns")

    # Scoped uniqueness
    __table_args__ = (
        UniqueConstraint("org_id", "txn_id", name="uq_org_txn_id"),
        Index("ix_gateway_txns_org_amount_date", "org_id", "amount", "captured_at"),
    )
