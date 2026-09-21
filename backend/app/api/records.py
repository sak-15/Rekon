"""
Records Query API Router for Rekon.

Provides paginated views of canonical financial records scoped strictly
to the authenticated user's organisation.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from decimal import Decimal
from datetime import datetime, date

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.organisation import User
from app.models.invoice import Invoice, InvoiceStatusEnum, ReconciliationStatusEnum
from app.models.gateway import GatewayTransaction, GatewayEnum, PaymentMethodEnum, TxnStatusEnum
from app.models.settlement import SettlementBatch, SettlementLine
from app.models.bank import BankCredit

router = APIRouter(prefix="/records", tags=["Records Explorer"])


# --- Schemas ---

class InvoiceRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    invoice_no: str
    customer_id: str
    customer_name: Optional[str] = None
    plan_name: Optional[str] = None
    amount: Decimal
    tax_amount: Decimal
    currency: str
    status: InvoiceStatusEnum
    invoice_date: datetime
    reconciliation_status: ReconciliationStatusEnum


class GatewayTxnRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    txn_id: str
    gateway: GatewayEnum
    payment_method: PaymentMethodEnum
    invoice_ref: Optional[str] = None
    customer_email: Optional[str] = None
    amount: Decimal
    gateway_fee: Decimal
    gateway_fee_gst: Decimal
    net_amount: Decimal
    currency: str
    status: TxnStatusEnum
    captured_at: datetime
    reconciliation_status: ReconciliationStatusEnum


class SettlementBatchRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    batch_id: str
    gateway: GatewayEnum
    settlement_date: datetime
    gross_amount: Decimal
    total_fees: Decimal
    total_gst: Decimal
    total_refunds: Decimal
    net_amount: Decimal
    utr_number: Optional[str] = None
    reconciliation_status: ReconciliationStatusEnum


class BankCreditRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    transaction_date: datetime
    narration: str
    credit_amount: Decimal
    debit_amount: Decimal
    reference_no: Optional[str] = None
    bank_name: Optional[str] = None
    reconciliation_status: ReconciliationStatusEnum


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


# --- Endpoints ---

@router.get("/invoices", response_model=PaginatedResponse, summary="List ingested invoices")
def get_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Invoice).filter(Invoice.org_id == current_user.org_id)
    total = query.count()
    items = (
        query.order_by(Invoice.invoice_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedResponse(
        items=[InvoiceRecord.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/gateway-txns", response_model=PaginatedResponse, summary="List gateway transactions")
def get_gateway_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(GatewayTransaction).filter(GatewayTransaction.org_id == current_user.org_id)
    total = query.count()
    items = (
        query.order_by(GatewayTransaction.captured_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedResponse(
        items=[GatewayTxnRecord.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/settlements", response_model=PaginatedResponse, summary="List settlement batches")
def get_settlements(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(SettlementBatch).filter(SettlementBatch.org_id == current_user.org_id)
    total = query.count()
    items = (
        query.order_by(SettlementBatch.settlement_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedResponse(
        items=[SettlementBatchRecord.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/bank-credits", response_model=PaginatedResponse, summary="List bank credits")
def get_bank_credits(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(BankCredit).filter(BankCredit.org_id == current_user.org_id)
    total = query.count()
    items = (
        query.order_by(BankCredit.transaction_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedResponse(
        items=[BankCreditRecord.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )
