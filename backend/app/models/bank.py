from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.invoice import ReconciliationStatusEnum


class BankCredit(Base, TimestampMixin):
    """
    Bank Statement Credits (HDFC, ICICI, Axis, Kotak, etc.)
    Represents actual cash received in the company's bank account.
    """
    __tablename__ = "bank_credits"

    org_id = Column(String(36), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False, index=True)
    upload_job_id = Column(String(36), ForeignKey("upload_jobs.id", ondelete="SET NULL"), nullable=True, index=True)

    transaction_date = Column(DateTime, nullable=False, index=True)
    value_date = Column(DateTime, nullable=True)

    narration = Column(String(500), nullable=False)
    credit_amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    debit_amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    running_balance = Column(Numeric(14, 2), nullable=True)

    reference_no = Column(String(100), nullable=True, index=True)  # UTR, Cheque No, Ref ID
    bank_name = Column(String(100), nullable=True)

    reconciliation_status = Column(
        Enum(ReconciliationStatusEnum), default=ReconciliationStatusEnum.UNMATCHED, nullable=False, index=True
    )

    # Relationship
    organisation = relationship("Organisation", back_populates="bank_credits")

    __table_args__ = (
        Index("ix_bank_credits_org_credit_date", "org_id", "credit_amount", "transaction_date"),
    )
