from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.organisation import User
from app.services.fee_audit import FeeAuditEngine
from app.schemas.rate_card import FeeAuditResponse

router = APIRouter(prefix="/fee-audit", tags=["Fee Audit"])


@router.get("", response_model=FeeAuditResponse)
def get_fee_audit_report(
    gateway: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Runs mathematical MDR & 18% GST Fee Audit across tenant transactions.
    Calculates exact paisa variances and groups discrepancies by dispute category.
    """
    report = FeeAuditEngine.audit_transactions(
        db=db,
        org_id=current_user.org_id,
        gateway=gateway,
        start_date=start_date,
        end_date=end_date,
    )
    return report.to_dict()


@router.get("/export")
def export_fee_dispute_claim(
    gateway: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Exports all flagged overcharges as a pre-formatted CSV dispute sheet
    ready to submit to Gateway Merchant Support (Razorpay / Stripe).
    """
    report = FeeAuditEngine.audit_transactions(
        db=db,
        org_id=current_user.org_id,
        gateway=gateway,
        start_date=start_date,
        end_date=end_date,
    )
    csv_content = FeeAuditEngine.generate_dispute_claim_csv(report)

    filename = f"rekon_fee_dispute_claim_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )
