import enum
from sqlalchemy import Column, String, Numeric, DateTime, Date, ForeignKey, Enum, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.gateway import GatewayEnum
from app.models.invoice import ReconciliationStatusEnum


class SettlementLineTypeEnum(str, enum.Enum):
    PAYMENT = "payment"
    REFUND = "refund"
    CHARGEBACK = "chargeback"
    ADJUSTMENT = "adjustment"


class SettlementBatch(Base, TimestampMixin):
    """
    Gateway Settlement Batches (Razorpay, Stripe payouts).
    Represents the aggregate payout the gateway claims to have sent to the bank.
    """
    __tablename__ = "settlement_batches"

    org_id = Column(String(36), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False, index=True)
    upload_job_id = Column(String(36), ForeignKey("upload_jobs.id", ondelete="SET NULL"), nullable=True, index=True)

    batch_id = Column(String(100), nullable=False)
    gateway = Column(Enum(GatewayEnum), nullable=False, index=True)
    settlement_date = Column(DateTime, nullable=False, index=True)

    # Batch Aggregates
    gross_amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    total_fees = Column(Numeric(12, 2), default=0.00, nullable=False)
    total_gst = Column(Numeric(12, 2), default=0.00, nullable=False)
    total_refunds = Column(Numeric(12, 2), default=0.00, nullable=False)
    total_adjustments = Column(Numeric(12, 2), default=0.00, nullable=False)
    net_amount = Column(Numeric(12, 2), nullable=False)  # Net cash expected to land in bank
    currency = Column(String(3), default="INR", nullable=False)

    utr_number = Column(String(100), nullable=True, index=True)
    bank_account_ref = Column(String(50), nullable=True)

    reconciliation_status = Column(
        Enum(ReconciliationStatusEnum), default=ReconciliationStatusEnum.UNMATCHED, nullable=False, index=True
    )

    # Relationships
    organisation = relationship("Organisation", back_populates="settlement_batches")
    lines = relationship("SettlementLine", back_populates="batch", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("org_id", "batch_id", name="uq_org_batch_id"),
        Index("ix_settlement_batches_org_net_date", "org_id", "net_amount", "settlement_date"),
    )


class SettlementLine(Base, TimestampMixin):
    """
    Itemized lines within a settlement batch linking individual gateway transactions to payouts.
    """
    __tablename__ = "settlement_lines"

    org_id = Column(String(36), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id = Column(String(36), ForeignKey("settlement_batches.id", ondelete="CASCADE"), nullable=False, index=True)

    txn_ref = Column(String(100), nullable=False, index=True)
    line_type = Column(Enum(SettlementLineTypeEnum), default=SettlementLineTypeEnum.PAYMENT, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    fee = Column(Numeric(12, 2), default=0.00, nullable=False)
    tax = Column(Numeric(12, 2), default=0.00, nullable=False)
    description = Column(String(255), nullable=True)

    # Relationship
    batch = relationship("SettlementBatch", back_populates="lines")

