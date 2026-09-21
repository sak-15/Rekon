import enum
from sqlalchemy import Column, String, Integer, Text, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class FileTypeEnum(str, enum.Enum):
    INVOICE = "invoice"
    GATEWAY_TXN = "gateway_txn"
    SETTLEMENT = "settlement"
    BANK_STATEMENT = "bank_statement"


class UploadStatusEnum(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class UploadJob(Base, TimestampMixin):
    """
    Tracks each CSV batch ingestion job for auditability and error reporting.
    """
    __tablename__ = "upload_jobs"

    org_id = Column(String(36), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False, index=True)
    file_type = Column(Enum(FileTypeEnum), nullable=False)
    filename = Column(String(255), nullable=False)
    status = Column(Enum(UploadStatusEnum), default=UploadStatusEnum.PENDING, nullable=False)

    total_rows = Column(Integer, default=0, nullable=False)
    valid_rows = Column(Integer, default=0, nullable=False)
    error_rows = Column(Integer, default=0, nullable=False)
    error_details = Column(JSON, nullable=True)  # Detailed list of row errors: [{"row": 5, "error": "invalid amount"}]

    # Relationship
    organisation = relationship("Organisation", back_populates="upload_jobs")

