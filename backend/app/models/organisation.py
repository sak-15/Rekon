import enum
from sqlalchemy import Column, String, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    FINANCE_ANALYST = "finance_analyst"
    AUDITOR = "auditor"
    VIEWER = "viewer"


class Organisation(Base, TimestampMixin):
    """
    Tenant entity. Each customer SaaS business using Rekon has their own Organisation.
    All financial data is partitioned by org_id.
    """
    __tablename__ = "organisations"

    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    currency = Column(String(3), default="INR", nullable=False)  # Base currency (INR, USD, EUR)

    # Relationships
    users = relationship("User", back_populates="organisation", cascade="all, delete-orphan")
    upload_jobs = relationship("UploadJob", back_populates="organisation", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="organisation", cascade="all, delete-orphan")
    gateway_txns = relationship("GatewayTransaction", back_populates="organisation", cascade="all, delete-orphan")
    settlement_batches = relationship("SettlementBatch", back_populates="organisation", cascade="all, delete-orphan")
    bank_credits = relationship("BankCredit", back_populates="organisation", cascade="all, delete-orphan")
    reconciliation_runs = relationship("ReconciliationRun", back_populates="organisation", cascade="all, delete-orphan")
    rate_cards = relationship("GatewayRateCard", back_populates="organisation", cascade="all, delete-orphan")
    exceptions = relationship("ReconciliationException", back_populates="organisation", cascade="all, delete-orphan")


class User(Base, TimestampMixin):
    """
    User belonging to an Organisation.
    """
    __tablename__ = "users"

    org_id = Column(String(36), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(Enum(UserRole), default=UserRole.FINANCE_ANALYST, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationship
    organisation = relationship("Organisation", back_populates="users")

