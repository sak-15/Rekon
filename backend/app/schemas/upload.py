from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, ConfigDict
from app.models.upload import FileTypeEnum, UploadStatusEnum


class UploadJobResponse(BaseModel):
    """
    Public representation of an Ingestion Upload Job and its row-level audit metrics.
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    file_type: FileTypeEnum
    filename: str
    status: UploadStatusEnum
    total_rows: int
    valid_rows: int
    error_rows: int
    error_details: Optional[List[Dict[str, Any]]] = None
    created_at: datetime


class UploadListResponse(BaseModel):
    """
    Paginated list of upload jobs.
    """
    items: List[UploadJobResponse]
    total: int


class UploadSuccessResponse(BaseModel):
    """
    Immediate response returned after uploading and processing a CSV file.
    """
    message: str
    upload_job: UploadJobResponse

