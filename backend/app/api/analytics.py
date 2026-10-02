from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.organisation import User
from app.services.analytics import ExecutiveAnalyticsService
from app.schemas.analytics import (
    ExecutiveDashboardResponse,
    ExecutiveKPISummary,
    CashflowWaterfallStep,
    GatewayPerformanceItem,
)

router = APIRouter(prefix="/analytics", tags=["Executive Analytics & Dashboard"])


@router.get("/dashboard", response_model=ExecutiveDashboardResponse)
def get_executive_dashboard(
    start_date: Optional[datetime] = Query(None, description="Filter from start date"),
    end_date: Optional[datetime] = Query(None, description="Filter to end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns complete founder & CFO executive dashboard metrics:
    Gross revenue, net bank cash, blended take-rate %, cashflow waterfall,
    gateway cost comparisons, financial health score, and actionable priority alerts.
    Strictly tenant-scoped with optional date window / month filtering.
    """
    return ExecutiveAnalyticsService.get_dashboard(
        db=db,
        org_id=current_user.org_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/summary", response_model=ExecutiveKPISummary)
def get_executive_summary_kpis(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the top-level 5 KPI metric cards for lightweight header displays.
    """
    dashboard = ExecutiveAnalyticsService.get_dashboard(db=db, org_id=current_user.org_id)
    return dashboard.summary


@router.get("/waterfall", response_model=List[CashflowWaterfallStep])
def get_cashflow_waterfall(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the 5-step revenue-to-bank-cash realization waterfall pipeline.
    """
    dashboard = ExecutiveAnalyticsService.get_dashboard(db=db, org_id=current_user.org_id)
    return dashboard.waterfall


@router.get("/gateways", response_model=List[GatewayPerformanceItem])
def get_gateway_comparisons(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns side-by-side volume, take-rate %, and overcharge discrepancy comparison per gateway.
    """
    dashboard = ExecutiveAnalyticsService.get_dashboard(db=db, org_id=current_user.org_id)
    return dashboard.gateway_comparison

