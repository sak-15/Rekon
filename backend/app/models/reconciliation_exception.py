"""
SQLAlchemy Model for Reconciliation Exceptions & Resolution Queue.
Stores forensic root-cause diagnoses for transactions that fail automatic reconciliation,
tracking manual matches, write-offs, dispute tickets, and audit trails.
"""

import enum
from sqlalchemy import (
    Column,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    Enum,
    Text,
    Index,
)
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class ExceptionTypeEnum(str, enum.Enum):
    """Forensic root-cause classifications for reconciliation failures."""
    TIMING_DIFFERENCE = "timing_difference"                  # T+2 clearing lag / in-transit money
    AMOUNT_MISMATCH = "amount_mismatch"                      # Reference matches, amount short/excess
    MISSING_BANK_CREDIT = "missing_bank_credit"              # Gateway claims UTR sent, not found in bank
    UNBILLED_CHARGE = "unbilled_charge"                      # Payment captured without billing invoice
    UNIDENTIFIED_BANK_DEPOSIT = "unidentified_bank_deposit"  # Direct bank credit without gateway batch
    PAISA_ROUNDING_DELTA = "paisa_rounding_delta"            # Minor fractional tax/paisa rounding (<= ₹5)
    GATEWAY_FEE_DISCREPANCY = "gateway_fee_discrepancy"      # MDR or GST markup discrepancy


class ExceptionSeverityEnum(str, enum.Enum):
    """Priority level for financial exposure."""
    LOW = "low"          # Minor rounding, timing difference
    MEDIUM = "medium"    # Partial payment, fee delta
    HIGH = "high"        # Missing bank credit > ₹10k, unbilled charge
    CRITICAL = "critical"# Missing bank deposit > ₹1 Lakh


class ResolutionStatusEnum(str, enum.Enum):
    """Current state of exception in the finance queue."""
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    WRITTEN_OFF = "written_off"
    DISPUTED = "disputed"


class ResolutionActionEnum(str, enum.Enum):
    """Action taken to clear the exception."""
    MANUAL_MATCH = "manual_match"
    WRITE_OFF = "write_off"
    DISPUTE_TICKET = "dispute_ticket"
    CREATE_ADJUSTMENT = "create_adjustment"
    SYSTEM_AUTO_RESOLVED = "system_auto_resolved"


class ReconciliationException(Base, TimestampMixin):
    """
    Actionable financial exception record created by the Classifier Engine.
    Enables finance operators to investigate, manually link, or write-off variances.
    """
    __tablename__ = "reconciliation_exceptions"

    # Multi-tenant scoping
    org_id = Column(
        String(36),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Associated reconciliation execution
    run_id = Column(
        String(36),
        ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Classification & Priority
    exception_type = Column(
        Enum(ExceptionTypeEnum),
        nullable=False,
        index=True,
    )
    severity = Column(
        Enum(ExceptionSeverityEnum),
        default=ExceptionSeverityEnum.LOW,
        nullable=False,
        index=True,
    )
    status = Column(
        Enum(ResolutionStatusEnum),
        default=ResolutionStatusEnum.OPEN,
        nullable=False,
        index=True,
    )

    # Entity Pointers (Nullable based on layer)
    invoice_id = Column(
        String(36),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    gateway_txn_id = Column(
        String(36),
        ForeignKey("gateway_txns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    settlement_batch_id = Column(
        String(36),
        ForeignKey("settlement_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    settlement_line_id = Column(
        String(36),
        ForeignKey("settlement_lines.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    bank_credit_id = Column(
        String(36),
        ForeignKey("bank_credits.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Financial Exposure Amounts
    expected_amount = Column(Numeric(14, 2), default=0.00, nullable=False)
    actual_amount = Column(Numeric(14, 2), default=0.00, nullable=False)
    discrepancy_amount = Column(Numeric(14, 2), default=0.00, nullable=False)

    # Forensic Diagnosis & Guidance
    title = Column(String(255), nullable=False)
    root_cause_explanation = Column(Text, nullable=False)
    suggested_action = Column(String(255), nullable=True)

    # Resolution Audit Trail
    resolution_action = Column(Enum(ResolutionActionEnum), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    resolved_by = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at = Column(DateTime, nullable=True)

    # Relationships
    organisation = relationship("Organisation", back_populates="exceptions")
    run = relationship("ReconciliationRun", back_populates="exceptions")
    resolver = relationship("User", foreign_keys=[resolved_by])

    invoice = relationship("Invoice")
    gateway_txn = relationship("GatewayTransaction")
    settlement_batch = relationship("SettlementBatch")
    settlement_line = relationship("SettlementLine")
    bank_credit = relationship("BankCredit")

    __table_args__ = (
        Index("ix_exceptions_org_status", "org_id", "status"),
        Index("ix_exceptions_org_type", "org_id", "exception_type"),
        Index("ix_exceptions_org_severity", "org_id", "severity"),
    )

