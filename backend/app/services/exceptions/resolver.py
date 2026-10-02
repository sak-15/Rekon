"""
Reconciliation Exception Resolution Service.
Handles manual matching, 1-click write-offs, dispute tickets, and audit trails.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.reconciliation_exception import (
    ReconciliationException,
    ResolutionStatusEnum,
    ResolutionActionEnum,
    ExceptionTypeEnum,
)
from app.models.reconciliation import (
    ReconciliationMatch,
    ReconciliationLayerEnum,
    MatchTypeEnum,
    MatchStatusEnum,
)
from app.models.invoice import Invoice, ReconciliationStatusEnum as InvoiceReconStatus
from app.models.gateway import GatewayTransaction, ReconciliationStatusEnum as GatewayReconStatus
from app.models.bank import BankCredit, ReconciliationStatusEnum as BankReconStatus


class ExceptionResolverService:
    """
    Manages resolution workflows for reconciliation exceptions.
    """

    DEFAULT_MAX_WRITE_OFF = Decimal("50.00")  # ₹50 max per manual write-off without executive override

    @classmethod
    def resolve_with_manual_match(
        cls,
        db: Session,
        exception_id: str,
        org_id: str,
        user_id: str,
        target_entity_type: str,  # 'gateway_txn', 'invoice', 'bank_credit'
        target_entity_id: str,
        notes: Optional[str] = None,
    ) -> ReconciliationException:
        """
        Manually links an exception entity to an unmatched target entity.
        Creates a manual ReconciliationMatch and updates both entities to MATCHED.
        """
        exc = (
            db.query(ReconciliationException)
            .filter(
                ReconciliationException.id == exception_id,
                ReconciliationException.org_id == org_id,
            )
            .first()
        )
        if not exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found")

        now = datetime.now(timezone.utc)
        note_text = notes or "Manually matched by finance operator"

        # Determine link layer
        if exc.invoice_id and target_entity_type == "gateway_txn":
            txn = db.query(GatewayTransaction).filter_by(id=target_entity_id, org_id=org_id).first()
            if not txn:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target transaction not found")

            inv = db.query(Invoice).filter_by(id=exc.invoice_id).first()
            amt_diff = (txn.amount - inv.amount) if inv else Decimal("0.00")

            match = ReconciliationMatch(
                org_id=org_id,
                run_id=exc.run_id or "manual",
                layer=ReconciliationLayerEnum.LAYER_1,
                invoice_id=exc.invoice_id,
                gateway_txn_id=txn.id,
                match_type=MatchTypeEnum.MANUAL,
                confidence_score=Decimal("100.00"),
                status=MatchStatusEnum.MATCHED,
                amount_difference=amt_diff,
                match_details={"manual_resolution_note": note_text, "resolved_by": user_id},
            )
            db.add(match)
            exc.gateway_txn_id = txn.id
            txn.reconciliation_status = GatewayReconStatus.MATCHED
            if inv:
                inv.reconciliation_status = InvoiceReconStatus.MATCHED

        elif exc.gateway_txn_id and target_entity_type == "invoice":
            inv = db.query(Invoice).filter_by(id=target_entity_id, org_id=org_id).first()
            if not inv:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target invoice not found")

            txn = db.query(GatewayTransaction).filter_by(id=exc.gateway_txn_id).first()
            amt_diff = (txn.amount - inv.amount) if txn else Decimal("0.00")

            match = ReconciliationMatch(
                org_id=org_id,
                run_id=exc.run_id or "manual",
                layer=ReconciliationLayerEnum.LAYER_1,
                invoice_id=inv.id,
                gateway_txn_id=exc.gateway_txn_id,
                match_type=MatchTypeEnum.MANUAL,
                confidence_score=Decimal("100.00"),
                status=MatchStatusEnum.MATCHED,
                amount_difference=amt_diff,
                match_details={"manual_resolution_note": note_text, "resolved_by": user_id},
            )
            db.add(match)
            exc.invoice_id = inv.id
            inv.reconciliation_status = InvoiceReconStatus.MATCHED
            if txn:
                txn.reconciliation_status = GatewayReconStatus.MATCHED

        elif exc.bank_credit_id and target_entity_type == "invoice":
            inv = db.query(Invoice).filter_by(id=target_entity_id, org_id=org_id).first()
            if not inv:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target invoice not found")

            credit = db.query(BankCredit).filter_by(id=exc.bank_credit_id).first()
            amt_diff = (credit.credit_amount - inv.amount) if credit else Decimal("0.00")

            match = ReconciliationMatch(
                org_id=org_id,
                run_id=exc.run_id or "manual",
                layer=ReconciliationLayerEnum.LAYER_3,
                bank_credit_id=exc.bank_credit_id,
                invoice_id=inv.id,
                match_type=MatchTypeEnum.MANUAL,
                confidence_score=Decimal("100.00"),
                status=MatchStatusEnum.MATCHED,
                amount_difference=amt_diff,
                match_details={"manual_direct_neft_note": note_text, "resolved_by": user_id},
            )
            db.add(match)
            exc.invoice_id = inv.id
            inv.reconciliation_status = InvoiceReconStatus.MATCHED
            if credit:
                credit.reconciliation_status = BankReconStatus.MATCHED

        # Mark exception resolved
        exc.status = ResolutionStatusEnum.RESOLVED
        exc.resolution_action = ResolutionActionEnum.MANUAL_MATCH
        exc.resolution_notes = note_text
        exc.resolved_by = user_id
        exc.resolved_at = now

        db.commit()
        db.refresh(exc)
        return exc

    @classmethod
    def resolve_with_write_off(
        cls,
        db: Session,
        exception_id: str,
        org_id: str,
        user_id: str,
        notes: Optional[str] = None,
        max_allowed: Decimal = DEFAULT_MAX_WRITE_OFF,
    ) -> ReconciliationException:
        """
        Writes off an immaterial discrepancy delta to the Rounding / Bank Expense ledger.
        """
        exc = (
            db.query(ReconciliationException)
            .filter(
                ReconciliationException.id == exception_id,
                ReconciliationException.org_id == org_id,
            )
            .first()
        )
        if not exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found")

        if exc.discrepancy_amount > max_allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Discrepancy of ₹{exc.discrepancy_amount:.2f} exceeds standard write-off limit of ₹{max_allowed:.2f}.",
            )

        now = datetime.now(timezone.utc)
        exc.status = ResolutionStatusEnum.WRITTEN_OFF
        exc.resolution_action = ResolutionActionEnum.WRITE_OFF
        exc.resolution_notes = notes or f"Immaterial delta of ₹{exc.discrepancy_amount:.2f} written off to Rounding Expense."
        exc.resolved_by = user_id
        exc.resolved_at = now

        db.commit()
        db.refresh(exc)
        return exc

    @classmethod
    def resolve_batch_write_off(
        cls,
        db: Session,
        org_id: str,
        user_id: str,
        max_threshold: Decimal = Decimal("5.00"),
    ) -> List[ReconciliationException]:
        """
        1-Click Bulk Action: writes off all minor fractional rounding exceptions (<= max_threshold) for a tenant.
        """
        exceptions = (
            db.query(ReconciliationException)
            .filter(
                ReconciliationException.org_id == org_id,
                ReconciliationException.status == ResolutionStatusEnum.OPEN,
                ReconciliationException.discrepancy_amount <= max_threshold,
            )
            .all()
        )

        now = datetime.now(timezone.utc)
        for exc in exceptions:
            exc.status = ResolutionStatusEnum.WRITTEN_OFF
            exc.resolution_action = ResolutionActionEnum.WRITE_OFF
            exc.resolution_notes = f"Bulk written off (<= ₹{max_threshold:.2f} rounding variance)."
            exc.resolved_by = user_id
            exc.resolved_at = now

        db.commit()
        for exc in exceptions:
            db.refresh(exc)

        return exceptions

    @classmethod
    def update_status(
        cls,
        db: Session,
        exception_id: str,
        org_id: str,
        user_id: str,
        new_status: ResolutionStatusEnum,
        notes: Optional[str] = None,
    ) -> ReconciliationException:
        """
        Updates exception workflow state (e.g. OPEN -> INVESTIGATING or DISPUTED).
        """
        exc = (
            db.query(ReconciliationException)
            .filter(
                ReconciliationException.id == exception_id,
                ReconciliationException.org_id == org_id,
            )
            .first()
        )
        if not exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found")

        exc.status = new_status
        if notes:
            exc.resolution_notes = notes
        exc.resolved_by = user_id

        if new_status in [ResolutionStatusEnum.RESOLVED, ResolutionStatusEnum.WRITTEN_OFF]:
            exc.resolved_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(exc)
        return exc

