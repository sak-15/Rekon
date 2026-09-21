import enum
from sqlalchemy import Column, String, Numeric, DateTime, Date, ForeignKey, Enum, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class InvoiceStatusEnum(str, enum.Enum):
    PAID = "paid"
    PENDING = "pending"
    VOID = "void"
    FAILED = "failed"


class ReconciliationStatusEnum(str, enum.Enum):
    UNMATCHED = "unmatched"
    MATCHED = "matched"
    EXCEPTION = "exception"


class Invoice(Base, TimestampMixin):
    """
    Subscription Billing Invoices (Chargebee, Zoho Subscriptions, etc.)
    Represents what SHOULD have been billed and collected.
    """
    __tablename__ = "invoices"

    org_id = Column(String(36), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False, index=True)
    upload_job_id = Column(String(36), ForeignKey("upload_jobs.id", ondelete="SET NULL"), nullable=True, index=True)

    invoice_no = Column(String(100), nullable=False)
    customer_id = Column(String(100), nullable=False, index=True)
    customer_name = Column(String(255), nullable=True)
    customer_email = Column(String(255), nullable=True)
    plan_name = Column(String(100), nullable=True)

    amount = Column(Numeric(12, 2), nullable=False)
    tax_amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    currency = Column(String(3), default="INR", nullable=False)
    status = Column(Enum(InvoiceStatusEnum), default=InvoiceStatusEnum.PAID, nullable=False)

    invoice_date = Column(DateTime, nullable=False)
    due_date = Column(DateTime, nullable=True)
    billing_period_start = Column(Date, nullable=True)
    billing_period_end = Column(Date, nullable=True)
    source_system = Column(String(50), default="chargebee", nullable=False)

    # Reconciliation tracking
    reconciliation_status = Column(
        Enum(ReconciliationStatusEnum), default=ReconciliationStatusEnum.UNMATCHED, nullable=False, index=True
    )

    # Relationships
    organisation = relationship("Organisation", back_populates="invoices")

    # Scoped uniqueness: Invoice number is unique per organisation
    __table_args__ = (
        UniqueConstraint("org_id", "invoice_no", name="uq_org_invoice_no"),
        Index("ix_invoices_org_customer_amount", "org_id", "customer_id", "amount"),
    )
