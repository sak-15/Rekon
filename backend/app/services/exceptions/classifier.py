"""
Automated Forensic Exception Classifier Engine.
Analyzes unmatched financial records and discrepancy matches across all three layers
and automatically classifies them into actionable root causes with severity and suggested fixes.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional
import logging
from sqlalchemy.orm import Session

from app.models.invoice import Invoice, ReconciliationStatusEnum as InvoiceReconStatus
from app.models.gateway import GatewayTransaction, TxnStatusEnum, ReconciliationStatusEnum as GatewayReconStatus
from app.models.settlement import SettlementBatch, ReconciliationStatusEnum as SettlementReconStatus
from app.models.bank import BankCredit, ReconciliationStatusEnum as BankReconStatus
from app.models.reconciliation import (
    ReconciliationRun,
    ReconciliationMatch,
    ReconciliationLayerEnum,
    MatchStatusEnum,
)
from app.models.reconciliation_exception import (
    ReconciliationException,
    ExceptionTypeEnum,
    ExceptionSeverityEnum,
    ResolutionStatusEnum,
)

logger = logging.getLogger(__name__)


class ExceptionClassifierEngine:
    """
    Forensic rule-based classification engine for reconciliation exceptions.
    """

    PAISA_WRITE_OFF_LIMIT = Decimal("5.00")
    CLEARING_WINDOW_DAYS = 2

    @classmethod
    def classify_and_record_exceptions(
        cls,
        db: Session,
        run: ReconciliationRun,
        invoices: List[Invoice],
        gateway_txns: List[GatewayTransaction],
        settlement_batches: List[SettlementBatch],
        bank_credits: List[BankCredit],
        matches: List[ReconciliationMatch],
    ) -> List[ReconciliationException]:
        """
        Inspects all records and matches from a reconciliation run,
        generates structured exceptions, and persists them into the database.
        """
        exceptions: List[ReconciliationException] = []
        now = datetime.now(timezone.utc)

        # 1. Classify Matches with DISCREPANCY or PARTIAL
        for match in matches:
            if match.status in [MatchStatusEnum.DISCREPANCY, MatchStatusEnum.PARTIAL]:
                exc = cls._classify_match_discrepancy(run, match)
                if exc:
                    exceptions.append(exc)

        # 2. Classify Unmatched Gateway Transactions (e.g. Unbilled charges or Timing lags)
        for txn in gateway_txns:
            if txn.reconciliation_status == GatewayReconStatus.UNMATCHED and txn.status == TxnStatusEnum.CAPTURED:
                # Check if this txn was captured very recently (< 48h)
                txn_date = txn.captured_at.replace(tzinfo=timezone.utc) if txn.captured_at.tzinfo is None else txn.captured_at
                is_recent = (now - txn_date) < timedelta(days=cls.CLEARING_WINDOW_DAYS)

                if is_recent:
                    exc_type = ExceptionTypeEnum.TIMING_DIFFERENCE
                    severity = ExceptionSeverityEnum.LOW
                    title = f"Timing Lag: Recent Charge of ₹{txn.amount:.2f}"
                    explanation = (
                        f"Payment of ₹{txn.amount:.2f} was captured on {txn.captured_at.strftime('%d %b %Y')} "
                        f"within the last {cls.CLEARING_WINDOW_DAYS} days. Invoice or settlement may still be in transit."
                    )
                    suggested = "Allow standard clearing window to elapse."
                else:
                    exc_type = ExceptionTypeEnum.UNBILLED_CHARGE
                    severity = ExceptionSeverityEnum.HIGH if txn.amount >= Decimal("10000.00") else ExceptionSeverityEnum.MEDIUM
                    title = f"Unbilled Payment of ₹{txn.amount:.2f} ({txn.txn_id})"
                    explanation = (
                        f"Gateway collected ₹{txn.amount:.2f} from {txn.customer_email or 'customer'} via "
                        f"{txn.payment_method.value}, but no corresponding subscription invoice exists in the billing engine."
                    )
                    suggested = "Generate invoice in billing system or manually link to existing customer."

                exc = ReconciliationException(
                    org_id=run.org_id,
                    run_id=run.id,
                    gateway_txn_id=txn.id,
                    exception_type=exc_type,
                    severity=severity,
                    status=ResolutionStatusEnum.OPEN,
                    expected_amount=Decimal("0.00"),
                    actual_amount=Decimal(str(txn.amount)),
                    discrepancy_amount=Decimal(str(txn.amount)),
                    title=title,
                    root_cause_explanation=explanation,
                    suggested_action=suggested,
                )
                exceptions.append(exc)

        # 3. Classify Unmatched Settlement Batches (Missing Bank Deposits)
        for batch in settlement_batches:
            if batch.reconciliation_status == SettlementReconStatus.UNMATCHED:
                batch_date = batch.settlement_date.replace(tzinfo=timezone.utc) if batch.settlement_date.tzinfo is None else batch.settlement_date
                is_recent = (now - batch_date) < timedelta(days=cls.CLEARING_WINDOW_DAYS)

                if is_recent:
                    exc_type = ExceptionTypeEnum.TIMING_DIFFERENCE
                    severity = ExceptionSeverityEnum.LOW
                    title = f"Timing Lag: Settlement Batch {batch.batch_id} in Transit"
                    explanation = (
                        f"Settlement batch of ₹{batch.net_amount:.2f} was initiated on {batch.settlement_date.strftime('%d %b %Y')}. "
                        f"Expected to credit in bank within standard banking clearing cycle."
                    )
                    suggested = "Monitor next bank statement cycle for automated clearing."
                else:
                    exc_type = ExceptionTypeEnum.MISSING_BANK_CREDIT
                    if batch.net_amount >= Decimal("100000.00"):
                        severity = ExceptionSeverityEnum.CRITICAL
                    else:
                        severity = ExceptionSeverityEnum.HIGH

                    utr_ref = batch.utr_number or batch.batch_id
                    title = f"Missing Bank Deposit for {batch.gateway.value.upper()} batch ({utr_ref})"
                    explanation = (
                        f"Gateway claims payout of ₹{batch.net_amount:.2f} was sent with UTR '{batch.utr_number or 'N/A'}' "
                        f"on {batch.settlement_date.strftime('%d %b %Y')}, but no matching deposit appears on the bank statement."
                    )
                    suggested = "Verify UTR with banking operations or file inquiry ticket with gateway support."

                exc = ReconciliationException(
                    org_id=run.org_id,
                    run_id=run.id,
                    settlement_batch_id=batch.id,
                    exception_type=exc_type,
                    severity=severity,
                    status=ResolutionStatusEnum.OPEN,
                    expected_amount=Decimal(str(batch.net_amount)),
                    actual_amount=Decimal("0.00"),
                    discrepancy_amount=Decimal(str(batch.net_amount)),
                    title=title,
                    root_cause_explanation=explanation,
                    suggested_action=suggested,
                )
                exceptions.append(exc)

        # 4. Classify Unmatched Bank Credits (Direct wires / Unknown deposits)
        for credit in bank_credits:
            if credit.reconciliation_status == BankReconStatus.UNMATCHED:
                amt = Decimal(str(credit.credit_amount))
                severity = ExceptionSeverityEnum.HIGH if amt >= Decimal("100000.00") else ExceptionSeverityEnum.MEDIUM
                title = f"Unidentified Bank Deposit of ₹{amt:.2f}"
                date_str = credit.transaction_date.strftime('%d %b %Y') if credit.transaction_date else "Recent"
                explanation = (
                    f"Direct bank credit of ₹{amt:.2f} received on {date_str} "
                    f"with narration '{credit.narration}'. No matching gateway settlement batch found."
                )
                suggested = "Manually link to customer invoice or post to accounts receivable."

                exc = ReconciliationException(
                    org_id=run.org_id,
                    run_id=run.id,
                    bank_credit_id=credit.id,
                    exception_type=ExceptionTypeEnum.UNIDENTIFIED_BANK_DEPOSIT,
                    severity=severity,
                    status=ResolutionStatusEnum.OPEN,
                    expected_amount=Decimal("0.00"),
                    actual_amount=amt,
                    discrepancy_amount=amt,
                    title=title,
                    root_cause_explanation=explanation,
                    suggested_action=suggested,
                )
                exceptions.append(exc)

        # Persist all exceptions
        if exceptions:
            db.add_all(exceptions)
            db.flush()

        logger.info("Classified and created %d exceptions for run %s", len(exceptions), run.id)
        return exceptions

    @classmethod
    def _classify_match_discrepancy(
        cls,
        run: ReconciliationRun,
        match: ReconciliationMatch,
    ) -> Optional[ReconciliationException]:
        """
        Classifies an individual match record with amount variance.
        """
        diff = Decimal(str(match.amount_difference))
        abs_diff = abs(diff)

        # 1. Immaterial Paisa Rounding Delta (<= ₹5.00)
        if abs_diff <= cls.PAISA_WRITE_OFF_LIMIT:
            return ReconciliationException(
                org_id=run.org_id,
                run_id=run.id,
                invoice_id=match.invoice_id,
                gateway_txn_id=match.gateway_txn_id,
                settlement_batch_id=match.settlement_batch_id,
                settlement_line_id=match.settlement_line_id,
                bank_credit_id=match.bank_credit_id,
                exception_type=ExceptionTypeEnum.PAISA_ROUNDING_DELTA,
                severity=ExceptionSeverityEnum.LOW,
                status=ResolutionStatusEnum.OPEN,
                expected_amount=abs_diff,
                actual_amount=Decimal("0.00"),
                discrepancy_amount=abs_diff,
                title=f"Paisa Rounding Delta of ₹{abs_diff:.2f}",
                root_cause_explanation=(
                    f"Immaterial fractional variance of ₹{abs_diff:.2f} across {match.layer.value} records "
                    f"attributable to 18% GST paisa rounding or currency conversion truncation."
                ),
                suggested_action="Eligible for 1-click write-off to Rounding Expense.",
            )

        # 2. Layer 1 Invoice vs Gateway Mismatch
        if match.layer == ReconciliationLayerEnum.LAYER_1:
            return ReconciliationException(
                org_id=run.org_id,
                run_id=run.id,
                invoice_id=match.invoice_id,
                gateway_txn_id=match.gateway_txn_id,
                exception_type=ExceptionTypeEnum.AMOUNT_MISMATCH,
                severity=ExceptionSeverityEnum.MEDIUM,
                status=ResolutionStatusEnum.OPEN,
                expected_amount=abs_diff,
                actual_amount=Decimal("0.00"),
                discrepancy_amount=abs_diff,
                title=f"Invoice Amount Discrepancy (₹{abs_diff:.2f})",
                root_cause_explanation=(
                    f"Payment collected on gateway deviates from invoice total by ₹{abs_diff:.2f}. "
                    f"Customer may have applied a partial coupon or made a partial payment."
                ),
                suggested_action="Verify invoice line items or check for partial refund / offline credit.",
            )

        # 3. Layer 2 Gateway vs Settlement Line Fee Variance
        if match.layer == ReconciliationLayerEnum.LAYER_2:
            return ReconciliationException(
                org_id=run.org_id,
                run_id=run.id,
                gateway_txn_id=match.gateway_txn_id,
                settlement_line_id=match.settlement_line_id,
                exception_type=ExceptionTypeEnum.GATEWAY_FEE_DISCREPANCY,
                severity=ExceptionSeverityEnum.MEDIUM,
                status=ResolutionStatusEnum.OPEN,
                expected_amount=abs_diff,
                actual_amount=Decimal("0.00"),
                discrepancy_amount=abs_diff,
                title=f"Settlement Fee Deduction Variance (₹{abs_diff:.2f})",
                root_cause_explanation=(
                    f"Actual gateway deduction deviates from expected fee schedule by ₹{abs_diff:.2f}. "
                    f"Possible unauthorized MDR markup or GST miscalculation."
                ),
                suggested_action="Audit against contracted gateway rate card or file dispute.",
            )

        # 4. Layer 3 Settlement Batch vs Bank Credit Shortfall
        if match.layer == ReconciliationLayerEnum.LAYER_3:
            severity = ExceptionSeverityEnum.CRITICAL if abs_diff >= Decimal("100000.00") else ExceptionSeverityEnum.HIGH
            return ReconciliationException(
                org_id=run.org_id,
                run_id=run.id,
                settlement_batch_id=match.settlement_batch_id,
                bank_credit_id=match.bank_credit_id,
                exception_type=ExceptionTypeEnum.MISSING_BANK_CREDIT,
                severity=severity,
                status=ResolutionStatusEnum.OPEN,
                expected_amount=abs_diff,
                actual_amount=Decimal("0.00"),
                discrepancy_amount=abs_diff,
                title=f"Bank Credit Shortfall of ₹{abs_diff:.2f}",
                root_cause_explanation=(
                    f"Bank deposited ₹{abs_diff:.2f} less than promised by the gateway settlement payout batch. "
                    f"Possible bank intermediary deduction or holdback."
                ),
                suggested_action="Verify bank deduction charges with banking manager.",
            )

        return None
