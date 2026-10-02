from typing import Optional, List, Dict, Any
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.organisation import User
from app.models.reconciliation_exception import (
    ReconciliationException,
    ExceptionTypeEnum,
    ExceptionSeverityEnum,
    ResolutionStatusEnum,
)
from app.services.exceptions.resolver import ExceptionResolverService
from app.schemas.exception import (
    ReconciliationExceptionResponse,
    ExceptionListResponse,
    ExceptionSummaryResponse,
    ManualMatchRequest,
    WriteOffRequest,
    BatchWriteOffRequest,
    UpdateStatusRequest,
)

router = APIRouter(prefix="/exceptions", tags=["Exception Resolution Queue"])


def _serialize_exception(exc: ReconciliationException) -> ReconciliationExceptionResponse:
    """Helper to enrich exception with clean human-readable entity references."""
    ref = None
    cust = None

    if exc.invoice:
        ref = f"Invoice: {exc.invoice.invoice_no}"
        cust = exc.invoice.customer_name or exc.invoice.customer_email
    elif exc.gateway_txn:
        ref = f"Charge: {exc.gateway_txn.txn_id} ({exc.gateway_txn.gateway.value.upper()})"
        cust = exc.gateway_txn.customer_email
    elif exc.settlement_batch:
        utr = exc.settlement_batch.utr_number or exc.settlement_batch.batch_id
        ref = f"Payout: {utr} ({exc.settlement_batch.gateway.value.upper()})"
    elif exc.bank_credit:
        ref = f"Bank Narration: {exc.bank_credit.narration[:40]}..."

    return ReconciliationExceptionResponse(
        id=exc.id,
        org_id=exc.org_id,
        run_id=exc.run_id,
        exception_type=exc.exception_type,
        severity=exc.severity,
        status=exc.status,
        invoice_id=exc.invoice_id,
        gateway_txn_id=exc.gateway_txn_id,
        settlement_batch_id=exc.settlement_batch_id,
        settlement_line_id=exc.settlement_line_id,
        bank_credit_id=exc.bank_credit_id,
        entity_reference=ref,
        customer_info=cust,
        expected_amount=float(exc.expected_amount),
        actual_amount=float(exc.actual_amount),
        discrepancy_amount=float(exc.discrepancy_amount),
        title=exc.title,
        root_cause_explanation=exc.root_cause_explanation,
        suggested_action=exc.suggested_action,
        resolution_action=exc.resolution_action,
        resolution_notes=exc.resolution_notes,
        resolved_by=exc.resolved_by,
        resolved_at=exc.resolved_at,
        created_at=exc.created_at,
        updated_at=exc.updated_at,
    )


@router.get("", response_model=ExceptionListResponse)
def list_exceptions(
    status_filter: Optional[ResolutionStatusEnum] = Query(None, alias="status"),
    exception_type: Optional[ExceptionTypeEnum] = None,
    severity: Optional[ExceptionSeverityEnum] = None,
    run_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List tenant exceptions with flexible filters.
    """
    query = db.query(ReconciliationException).filter(
        ReconciliationException.org_id == current_user.org_id
    )

    if status_filter:
        query = query.filter(ReconciliationException.status == status_filter)
    if exception_type:
        query = query.filter(ReconciliationException.exception_type == exception_type)
    if severity:
        query = query.filter(ReconciliationException.severity == severity)
    if run_id:
        query = query.filter(ReconciliationException.run_id == run_id)

    total = query.count()
    items = (
        query.order_by(ReconciliationException.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return ExceptionListResponse(
        items=[_serialize_exception(e) for e in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/summary", response_model=ExceptionSummaryResponse)
def get_exception_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns executive exception metrics: open count, unresolved exposure, breakdown by severity and type.
    """
    all_exc = (
        db.query(ReconciliationException)
        .filter(ReconciliationException.org_id == current_user.org_id)
        .all()
    )

    open_cnt = 0
    inv_cnt = 0
    res_cnt = 0
    wo_cnt = 0
    exposure = Decimal("0.00")

    sev_breakdown: Dict[str, int] = {
        ExceptionSeverityEnum.LOW.value: 0,
        ExceptionSeverityEnum.MEDIUM.value: 0,
        ExceptionSeverityEnum.HIGH.value: 0,
        ExceptionSeverityEnum.CRITICAL.value: 0,
    }

    type_breakdown: Dict[str, Dict[str, Any]] = {}

    for e in all_exc:
        t_val = e.exception_type.value
        if t_val not in type_breakdown:
            type_breakdown[t_val] = {"count": 0, "amount": 0.0}
        type_breakdown[t_val]["count"] += 1
        type_breakdown[t_val]["amount"] += float(e.discrepancy_amount)

        if e.status == ResolutionStatusEnum.OPEN:
            open_cnt += 1
            exposure += e.discrepancy_amount
            sev_breakdown[e.severity.value] += 1
        elif e.status == ResolutionStatusEnum.INVESTIGATING:
            inv_cnt += 1
            exposure += e.discrepancy_amount
            sev_breakdown[e.severity.value] += 1
        elif e.status == ResolutionStatusEnum.RESOLVED:
            res_cnt += 1
        elif e.status == ResolutionStatusEnum.WRITTEN_OFF:
            wo_cnt += 1

    return ExceptionSummaryResponse(
        total_exceptions=len(all_exc),
        open_count=open_cnt,
        investigating_count=inv_cnt,
        resolved_count=res_cnt,
        written_off_count=wo_cnt,
        total_unresolved_exposure=float(exposure),
        severity_breakdown=sev_breakdown,
        type_breakdown=type_breakdown,
    )


@router.post("/{exception_id}/manual-match", response_model=ReconciliationExceptionResponse)
def manual_match_exception(
    exception_id: str,
    payload: ManualMatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually links an exception to an unmatched target record.
    """
    exc = ExceptionResolverService.resolve_with_manual_match(
        db=db,
        exception_id=exception_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        target_entity_type=payload.target_entity_type,
        target_entity_id=payload.target_entity_id,
        notes=payload.notes,
    )
    return _serialize_exception(exc)


@router.post("/{exception_id}/write-off", response_model=ReconciliationExceptionResponse)
def write_off_exception(
    exception_id: str,
    payload: WriteOffRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Writes off an immaterial discrepancy delta to the Rounding Expense ledger.
    """
    exc = ExceptionResolverService.resolve_with_write_off(
        db=db,
        exception_id=exception_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        notes=payload.notes,
        max_allowed=payload.max_allowed or Decimal("50.00"),
    )
    return _serialize_exception(exc)


@router.post("/batch-write-off", response_model=List[ReconciliationExceptionResponse])
def batch_write_off_exceptions(
    payload: BatchWriteOffRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    1-Click Bulk Action: Writes off all open minor rounding deltas under threshold (default <= ₹5.00).
    """
    exceptions = ExceptionResolverService.resolve_batch_write_off(
        db=db,
        org_id=current_user.org_id,
        user_id=current_user.id,
        max_threshold=payload.max_threshold,
    )
    return [_serialize_exception(e) for e in exceptions]


@router.put("/{exception_id}/status", response_model=ReconciliationExceptionResponse)
def update_exception_status(
    exception_id: str,
    payload: UpdateStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Updates exception queue status (e.g. mark INVESTIGATING or DISPUTED).
    """
    exc = ExceptionResolverService.update_status(
        db=db,
        exception_id=exception_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        new_status=payload.status,
        notes=payload.notes,
    )
    return _serialize_exception(exc)

