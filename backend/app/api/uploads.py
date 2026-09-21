"""
CSV Ingestion API Router for Rekon.

Provides authenticated multi-tenant endpoints to ingest:
1. Subscription Invoices (Chargebee / Zoho)
2. Gateway Transactions (Razorpay / Stripe)
3. Settlement Batches & Lines
4. Bank Statement Credits
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.organisation import User
from app.models.upload import UploadJob, FileTypeEnum, UploadStatusEnum
from app.models.invoice import Invoice
from app.models.gateway import GatewayTransaction, GatewayEnum
from app.models.settlement import SettlementBatch
from app.models.bank import BankCredit
from app.schemas.upload import UploadJobResponse, UploadListResponse, UploadSuccessResponse
from app.services.parsers import (
    InvoiceParser,
    GatewayParser,
    SettlementParser,
    BankStatementParser,
)

router = APIRouter(prefix="/uploads", tags=["CSV Ingestion"])


@router.post(
    "/invoices",
    response_model=UploadSuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Subscription Invoices CSV",
    description="Parses and ingests subscription billing invoices (Chargebee, Zoho) with deduplication and row error tracking.",
)
async def upload_invoices(
    file: UploadFile = File(..., description="CSV file of subscription invoices"),
    source_system: str = Query("chargebee", description="Billing system origin (chargebee, zoho, custom)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content_bytes = await file.read()
    try:
        content_str = content_bytes.decode("utf-8-sig")  # Handles potential Excel BOM
    except UnicodeDecodeError:
        content_str = content_bytes.decode("latin-1")

    # 1. Initialize UploadJob record
    job = UploadJob(
        org_id=current_user.org_id,
        file_type=FileTypeEnum.INVOICE,
        filename=file.filename or "invoices.csv",
        status=UploadStatusEnum.PROCESSING,
    )
    db.add(job)
    db.flush()

    # 2. Parse CSV
    parsed = InvoiceParser.parse(
        csv_content=content_str,
        org_id=current_user.org_id,
        upload_job_id=job.id,
        source_system=source_system,
    )

    # 3. Deduplication against existing invoices in this organisation
    existing_inv_nos = {
        inv_no for (inv_no,) in db.query(Invoice.invoice_no).filter(Invoice.org_id == current_user.org_id).all()
    }

    new_records = []
    skipped_duplicates = 0
    for record in parsed.valid_records:
        if record.invoice_no in existing_inv_nos:
            skipped_duplicates += 1
        else:
            new_records.append(record)
            existing_inv_nos.add(record.invoice_no)

    if new_records:
        db.add_all(new_records)

    # 4. Finalize job status
    error_list = [
        {"row": err.row_number, "field": err.field, "message": err.message}
        for err in parsed.errors
    ]
    if skipped_duplicates > 0:
        error_list.append({"row": 0, "field": "deduplication", "message": f"Skipped {skipped_duplicates} existing duplicate invoices"})

    job.total_rows = parsed.total_rows
    job.valid_rows = len(new_records)
    job.error_rows = parsed.error_count + skipped_duplicates
    job.error_details = error_list

    if parsed.error_count == 0:
        job.status = UploadStatusEnum.COMPLETED
    elif len(new_records) > 0:
        job.status = UploadStatusEnum.PARTIAL_SUCCESS
    else:
        job.status = UploadStatusEnum.FAILED

    db.commit()
    db.refresh(job)

    return UploadSuccessResponse(
        message=f"Successfully ingested {len(new_records)} invoices ({job.error_rows} exceptions/duplicates)",
        upload_job=UploadJobResponse.model_validate(job),
    )


@router.post(
    "/gateway-txns",
    response_model=UploadSuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Gateway Transactions CSV (Razorpay / Stripe)",
    description="Auto-detects gateway and standardizes payment transactions with MDR fees and GST.",
)
async def upload_gateway_transactions(
    file: UploadFile = File(..., description="CSV file of Razorpay or Stripe transactions"),
    gateway: Optional[GatewayEnum] = Query(None, description="Optional override: razorpay or stripe"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content_bytes = await file.read()
    try:
        content_str = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        content_str = content_bytes.decode("latin-1")

    job = UploadJob(
        org_id=current_user.org_id,
        file_type=FileTypeEnum.GATEWAY_TXN,
        filename=file.filename or "gateway_txns.csv",
        status=UploadStatusEnum.PROCESSING,
    )
    db.add(job)
    db.flush()

    parsed = GatewayParser.parse(
        csv_content=content_str,
        org_id=current_user.org_id,
        upload_job_id=job.id,
        force_gateway=gateway,
    )

    # Deduplicate against existing txn_id within this tenant
    existing_txn_ids = {
        t_id for (t_id,) in db.query(GatewayTransaction.txn_id).filter(GatewayTransaction.org_id == current_user.org_id).all()
    }

    new_records = []
    skipped_duplicates = 0
    for record in parsed.valid_records:
        if record.txn_id in existing_txn_ids:
            skipped_duplicates += 1
        else:
            new_records.append(record)
            existing_txn_ids.add(record.txn_id)

    if new_records:
        db.add_all(new_records)

    error_list = [
        {"row": err.row_number, "field": err.field, "message": err.message}
        for err in parsed.errors
    ]
    if skipped_duplicates > 0:
        error_list.append({"row": 0, "field": "deduplication", "message": f"Skipped {skipped_duplicates} duplicate transactions"})

    job.total_rows = parsed.total_rows
    job.valid_rows = len(new_records)
    job.error_rows = parsed.error_count + skipped_duplicates
    job.error_details = error_list

    if parsed.error_count == 0:
        job.status = UploadStatusEnum.COMPLETED
    elif len(new_records) > 0:
        job.status = UploadStatusEnum.PARTIAL_SUCCESS
    else:
        job.status = UploadStatusEnum.FAILED

    db.commit()
    db.refresh(job)

    return UploadSuccessResponse(
        message=f"Successfully ingested {len(new_records)} gateway transactions ({job.error_rows} exceptions/duplicates)",
        upload_job=UploadJobResponse.model_validate(job),
    )


@router.post(
    "/settlements",
    response_model=UploadSuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Gateway Settlements CSV",
    description="Ingests payout batches with gross collections, deductions, and itemized settlement lines.",
)
async def upload_settlements(
    file: UploadFile = File(..., description="CSV file of gateway settlement reports"),
    gateway: GatewayEnum = Query(GatewayEnum.RAZORPAY, description="Originating gateway: razorpay or stripe"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content_bytes = await file.read()
    try:
        content_str = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        content_str = content_bytes.decode("latin-1")

    job = UploadJob(
        org_id=current_user.org_id,
        file_type=FileTypeEnum.SETTLEMENT,
        filename=file.filename or "settlements.csv",
        status=UploadStatusEnum.PROCESSING,
    )
    db.add(job)
    db.flush()

    parsed = SettlementParser.parse(
        csv_content=content_str,
        org_id=current_user.org_id,
        upload_job_id=job.id,
        gateway=gateway,
    )

    # Deduplicate batch_ids
    existing_batches = {
        b_id for (b_id,) in db.query(SettlementBatch.batch_id).filter(SettlementBatch.org_id == current_user.org_id).all()
    }

    new_records = []
    skipped_duplicates = 0
    for record in parsed.valid_records:
        if record.batch_id in existing_batches:
            skipped_duplicates += 1
        else:
            new_records.append(record)
            existing_batches.add(record.batch_id)

    if new_records:
        db.add_all(new_records)

    error_list = [
        {"row": err.row_number, "field": err.field, "message": err.message}
        for err in parsed.errors
    ]
    if skipped_duplicates > 0:
        error_list.append({"row": 0, "field": "deduplication", "message": f"Skipped {skipped_duplicates} duplicate settlement batches"})

    job.total_rows = parsed.total_rows
    job.valid_rows = len(new_records)
    job.error_rows = parsed.error_count + skipped_duplicates
    job.error_details = error_list

    if parsed.error_count == 0:
        job.status = UploadStatusEnum.COMPLETED
    elif len(new_records) > 0:
        job.status = UploadStatusEnum.PARTIAL_SUCCESS
    else:
        job.status = UploadStatusEnum.FAILED

    db.commit()
    db.refresh(job)

    return UploadSuccessResponse(
        message=f"Successfully ingested {len(new_records)} settlement batches",
        upload_job=UploadJobResponse.model_validate(job),
    )


@router.post(
    "/bank-statements",
    response_model=UploadSuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Bank Statement CSV",
    description="Ingests bank credits and UTR reference narrations for matching against settlement deposits.",
)
async def upload_bank_statements(
    file: UploadFile = File(..., description="CSV file of bank statement transactions"),
    bank_name: Optional[str] = Query("HDFC Bank", description="Bank name (HDFC, ICICI, Axis, etc.)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content_bytes = await file.read()
    try:
        content_str = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        content_str = content_bytes.decode("latin-1")

    job = UploadJob(
        org_id=current_user.org_id,
        file_type=FileTypeEnum.BANK_STATEMENT,
        filename=file.filename or "bank_statement.csv",
        status=UploadStatusEnum.PROCESSING,
    )
    db.add(job)
    db.flush()

    parsed = BankStatementParser.parse(
        csv_content=content_str,
        org_id=current_user.org_id,
        upload_job_id=job.id,
        bank_name=bank_name,
    )

    if parsed.valid_records:
        db.add_all(parsed.valid_records)

    error_list = [
        {"row": err.row_number, "field": err.field, "message": err.message}
        for err in parsed.errors
    ]

    job.total_rows = parsed.total_rows
    job.valid_rows = len(parsed.valid_records)
    job.error_rows = parsed.error_count
    job.error_details = error_list

    if parsed.error_count == 0:
        job.status = UploadStatusEnum.COMPLETED
    elif len(parsed.valid_records) > 0:
        job.status = UploadStatusEnum.PARTIAL_SUCCESS
    else:
        job.status = UploadStatusEnum.FAILED

    db.commit()
    db.refresh(job)

    return UploadSuccessResponse(
        message=f"Successfully ingested {len(parsed.valid_records)} bank credit lines",
        upload_job=UploadJobResponse.model_validate(job),
    )


@router.get(
    "",
    response_model=UploadListResponse,
    summary="List Upload Jobs for Organisation",
    description="Returns all previous CSV upload batches scoped to the current tenant.",
)
def list_uploads(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(UploadJob).filter(UploadJob.org_id == current_user.org_id)
    total = query.count()
    jobs = query.order_by(UploadJob.created_at.desc()).offset(skip).limit(limit).all()

    return UploadListResponse(
        items=[UploadJobResponse.model_validate(j) for j in jobs],
        total=total,
    )


@router.get(
    "/{upload_id}",
    response_model=UploadJobResponse,
    summary="Get Upload Job Details",
    description="Fetches audit status and row-level error log for a specific upload job.",
)
def get_upload_job(
    upload_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(UploadJob).filter(
        UploadJob.id == upload_id,
        UploadJob.org_id == current_user.org_id,
    ).first()

    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload job not found")

    return UploadJobResponse.model_validate(job)

