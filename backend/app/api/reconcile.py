"""
Reconciliation API Router for Rekon.
Provides endpoints to trigger reconciliation pipelines, list historical runs,
fetch executive telemetry reports, and query granular audit matches across all three layers.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.organisation import User
from app.models.reconciliation import (
    ReconciliationRun,
    ReconciliationMatch,
    ReconciliationLayerEnum,
    MatchStatusEnum,
)
from app.schemas.reconciliation import (
    TriggerReconciliationRequest,
    ReconciliationRunResponse,
    ReconciliationRunListResponse,
    ReconciliationMatchResponse,
    ReconciliationMatchListResponse,
)
from app.services.matching.orchestrator import ReconciliationOrchestrator

router = APIRouter(prefix="/reconcile", tags=["Reconciliation Engine"])


@router.post(
    "",
    response_model=ReconciliationRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger a Three-Layer Reconciliation Run",
    description="Initiates an end-to-end reconciliation run evaluating Invoices, Gateway Txns, Settlements, and Bank Statement Credits.",
)
def trigger_reconciliation(
    payload: Optional[TriggerReconciliationRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReconciliationRunResponse:
    """
    Triggers the reconciliation pipeline for the authenticated organisation.
    """
    rule_config = payload.rule_config if payload else None
    orchestrator = ReconciliationOrchestrator(db, config=rule_config)
    run = orchestrator.run(org_id=current_user.org_id, user_id=current_user.id)
    return ReconciliationRunResponse.model_validate(run)


@router.get(
    "",
    response_model=ReconciliationRunListResponse,
    summary="List Past Reconciliation Runs",
    description="Returns a paginated list of historical reconciliation runs for the authenticated organisation.",
)
def list_reconciliation_runs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReconciliationRunListResponse:
    """
    Lists past reconciliation runs scoped to current organisation.
    """
    query = (
        db.query(ReconciliationRun)
        .filter(ReconciliationRun.org_id == current_user.org_id)
        .order_by(ReconciliationRun.created_at.desc())
    )
    total = query.count()
    items = query.offset(offset).limit(limit).all()

    return ReconciliationRunListResponse(
        items=[ReconciliationRunResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get(
    "/{run_id}",
    response_model=ReconciliationRunResponse,
    summary="Get Specific Reconciliation Run Details",
    description="Retrieves executive telemetry, match counts, and financial summaries for a specific run.",
)
def get_reconciliation_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReconciliationRunResponse:
    """
    Retrieves run details by ID, enforcing tenant isolation.
    """
    run = (
        db.query(ReconciliationRun)
        .filter(
            ReconciliationRun.id == run_id,
            ReconciliationRun.org_id == current_user.org_id,
        )
        .first()
    )
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reconciliation run '{run_id}' not found.",
        )
    return ReconciliationRunResponse.model_validate(run)


@router.get(
    "/{run_id}/matches",
    response_model=ReconciliationMatchListResponse,
    summary="Query Itemized Reconciliation Matches",
    description="Returns paginated audit links across Layer 1, 2, or 3 with optional filtering by layer and match status.",
)
def get_reconciliation_matches(
    run_id: str,
    layer: Optional[ReconciliationLayerEnum] = Query(
        None, description="Filter by reconciliation layer (layer_1, layer_2, layer_3)"
    ),
    match_status: Optional[MatchStatusEnum] = Query(
        None, alias="status", description="Filter by match outcome (matched, partial, discrepancy)"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReconciliationMatchListResponse:
    """
    Queries matches belonging to a specific reconciliation run.
    """
    # Verify run ownership
    run = (
        db.query(ReconciliationRun)
        .filter(
            ReconciliationRun.id == run_id,
            ReconciliationRun.org_id == current_user.org_id,
        )
        .first()
    )
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reconciliation run '{run_id}' not found.",
        )

    query = (
        db.query(ReconciliationMatch)
        .filter(
            ReconciliationMatch.run_id == run_id,
            ReconciliationMatch.org_id == current_user.org_id,
        )
    )

    if layer is not None:
        query = query.filter(ReconciliationMatch.layer == layer)
    if match_status is not None:
        query = query.filter(ReconciliationMatch.status == match_status)

    total = query.count()
    items = (
        query.order_by(ReconciliationMatch.created_at.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return ReconciliationMatchListResponse(
        items=[ReconciliationMatchResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )

