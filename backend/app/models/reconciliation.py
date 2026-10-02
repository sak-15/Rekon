"""
SQLAlchemy Models for Reconciliation Runs & Matches.
Tracks reconciliation execution lifecycle, aggregated metrics, and fine-grained
audit links between financial records across all three layers.
"""

import enum
from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    DateTime,
    ForeignKey,
    Enum,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class ReconciliationRunStatusEnum(str, enum.Enum):
    """Execution status of a reconciliation run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReconciliationLayerEnum(str, enum.Enum):
    """Three architectural layers of the reconciliation engine."""
    LAYER_1 = "layer_1"  # Invoices ↔ Gateway Transactions
    LAYER_2 = "layer_2"  # Gateway Transactions ↔ Settlement Lines
    LAYER_3 = "layer_3"  # Settlement Batches ↔ Bank Credits


class MatchTypeEnum(str, enum.Enum):
    """Heuristic or rule used to identify a match."""
    EXACT = "exact"      # 100% deterministic reference match (e.g. invoice_no == invoice_ref)
    FUZZY = "fuzzy"      # Heuristic match (customer + amount + date window)
    MANUAL = "manual"    # Manually linked by finance analyst


class MatchStatusEnum(str, enum.Enum):
    """Outcome status of a matched pair."""
    MATCHED = "matched"          # Both sides match within tolerance
    PARTIAL = "partial"          # Amount mismatch or partial payment
    DISCREPANCY = "discrepancy"  # Flagged difference requiring review


class ReconciliationRun(Base, TimestampMixin):
    """
    Tracks a single execution of the reconciliation process for an organisation.
    Stores aggregate telemetry, financial summaries, and rule configuration.
    """
    __tablename__ = "reconciliation_runs"

    # Multi-tenant scoping
    org_id = Column(
        String(36),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    initiated_by = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Lifecycle state
    status = Column(
        Enum(ReconciliationRunStatusEnum),
        default=ReconciliationRunStatusEnum.PENDING,
        nullable=False,
        index=True,
    )
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(String(1000), nullable=True)

    # Configurable rule thresholds (e.g. date_window_days, amount_tolerance)
    rule_config = Column(JSON, nullable=True)

    # Record Counts: Layer 1 (Invoices ↔ Gateway Txns)
    total_invoices = Column(Integer, default=0, nullable=False)
    matched_invoices = Column(Integer, default=0, nullable=False)
    unmatched_invoices = Column(Integer, default=0, nullable=False)

    total_txns = Column(Integer, default=0, nullable=False)
    matched_txns = Column(Integer, default=0, nullable=False)
    unmatched_txns = Column(Integer, default=0, nullable=False)

    # Record Counts: Layer 2 & 3 (Settlements ↔ Bank)
    total_settlements = Column(Integer, default=0, nullable=False)
    matched_settlements = Column(Integer, default=0, nullable=False)
    unmatched_settlements = Column(Integer, default=0, nullable=False)

    total_bank_credits = Column(Integer, default=0, nullable=False)
    matched_bank_credits = Column(Integer, default=0, nullable=False)
    unmatched_bank_credits = Column(Integer, default=0, nullable=False)

    # Financial Reconciliation Totals (in base currency, e.g., INR)
    invoiced_amount = Column(Numeric(14, 2), default=0.00, nullable=False)
    collected_amount = Column(Numeric(14, 2), default=0.00, nullable=False)
    settled_amount = Column(Numeric(14, 2), default=0.00, nullable=False)
    bank_credited_amount = Column(Numeric(14, 2), default=0.00, nullable=False)
    discrepancy_amount = Column(Numeric(14, 2), default=0.00, nullable=False)

    # Relationships
    organisation = relationship("Organisation", back_populates="reconciliation_runs")
    user = relationship("User")
    matches = relationship(
        "ReconciliationMatch",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    exceptions = relationship(
        "ReconciliationException",
        back_populates="run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_reconciliation_runs_org_status", "org_id", "status"),
        Index("ix_reconciliation_runs_org_created", "org_id", "created_at"),
    )


class ReconciliationMatch(Base, TimestampMixin):
    """
    Individual matched link between financial entities across the three layers.
    Serves as an immutable audit record of reconciliation decisions.
    """
    __tablename__ = "reconciliation_matches"

    # Multi-tenant scoping and run linkage
    org_id = Column(
        String(36),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id = Column(
        String(36),
        ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Layer designation
    layer = Column(Enum(ReconciliationLayerEnum), nullable=False, index=True)

    # Entity Foreign Keys (Layer-specific, nullable)
    # Layer 1: Invoice ↔ Gateway Txn
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

    # Layer 2: Gateway Txn ↔ Settlement Line
    settlement_line_id = Column(
        String(36),
        ForeignKey("settlement_lines.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Layer 3: Settlement Batch ↔ Bank Credit
    settlement_batch_id = Column(
        String(36),
        ForeignKey("settlement_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    bank_credit_id = Column(
        String(36),
        ForeignKey("bank_credits.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Matching Details & Metrics
    match_type = Column(Enum(MatchTypeEnum), nullable=False)
    confidence_score = Column(Numeric(5, 2), default=100.00, nullable=False)  # 0.00% - 100.00%
    status = Column(
        Enum(MatchStatusEnum),
        default=MatchStatusEnum.MATCHED,
        nullable=False,
    )
    amount_difference = Column(Numeric(12, 2), default=0.00, nullable=False)

    # Additional audit information / reasons for match or discrepancy
    match_details = Column(JSON, nullable=True)

    # Relationships
    run = relationship("ReconciliationRun", back_populates="matches")
    invoice = relationship("Invoice")
    gateway_txn = relationship("GatewayTransaction")
    settlement_line = relationship("SettlementLine")
    settlement_batch = relationship("SettlementBatch")
    bank_credit = relationship("BankCredit")

    __table_args__ = (
        Index("ix_reconciliation_matches_org_layer", "org_id", "layer"),
        Index("ix_reconciliation_matches_run_layer", "run_id", "layer"),
    )

