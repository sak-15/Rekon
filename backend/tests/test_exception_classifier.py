import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from app.models.organisation import Organisation, User, UserRole
from app.models.reconciliation_exception import (
    ReconciliationException,
    ExceptionTypeEnum,
    ExceptionSeverityEnum,
    ResolutionStatusEnum,
    ResolutionActionEnum,
)
from app.models.invoice import Invoice, InvoiceStatusEnum, ReconciliationStatusEnum as InvReconStatus
from app.models.gateway import GatewayTransaction, GatewayEnum, PaymentMethodEnum, TxnStatusEnum, ReconciliationStatusEnum as GtwReconStatus
from app.models.settlement import SettlementBatch, ReconciliationStatusEnum as SetlReconStatus
from app.models.bank import BankCredit, ReconciliationStatusEnum as BnkReconStatus
from app.models.reconciliation import (
    ReconciliationRun,
    ReconciliationRunStatusEnum,
    ReconciliationMatch,
    ReconciliationLayerEnum,
    MatchStatusEnum,
    MatchTypeEnum,
)
from app.services.exceptions.classifier import ExceptionClassifierEngine
from app.services.exceptions.resolver import ExceptionResolverService


def test_classify_missing_bank_credit_and_timing_lag(db_session):
    """Test settlement batches classified as MISSING_BANK_CREDIT or TIMING_DIFFERENCE based on date."""
    org = Organisation(name="SaaS Classifier", slug="saas-classifier")
    db_session.add(org)
    db_session.commit()

    run = ReconciliationRun(
        org_id=org.id,
        status=ReconciliationRunStatusEnum.COMPLETED,
    )
    db_session.add(run)
    db_session.commit()

    # 1. Batch from 6 days ago (older than 2 days) -> MISSING_BANK_CREDIT
    old_batch = SettlementBatch(
        org_id=org.id,
        batch_id="setl_old_01",
        gateway=GatewayEnum.RAZORPAY,
        settlement_date=datetime.now(timezone.utc) - timedelta(days=6),
        gross_amount=Decimal("150000.00"),
        net_amount=Decimal("146460.00"),
        utr_number="UTR_OLD_123",
        reconciliation_status=SetlReconStatus.UNMATCHED,
    )
    # 2. Batch from today -> TIMING_DIFFERENCE
    recent_batch = SettlementBatch(
        org_id=org.id,
        batch_id="setl_recent_02",
        gateway=GatewayEnum.RAZORPAY,
        settlement_date=datetime.now(timezone.utc) - timedelta(hours=4),
        gross_amount=Decimal("50000.00"),
        net_amount=Decimal("48820.00"),
        utr_number="UTR_REC_456",
        reconciliation_status=SetlReconStatus.UNMATCHED,
    )
    db_session.add_all([old_batch, recent_batch])
    db_session.commit()

    exceptions = ExceptionClassifierEngine.classify_and_record_exceptions(
        db=db_session,
        run=run,
        invoices=[],
        gateway_txns=[],
        settlement_batches=[old_batch, recent_batch],
        bank_credits=[],
        matches=[],
    )

    assert len(exceptions) == 2
    old_exc = next(e for e in exceptions if e.settlement_batch_id == old_batch.id)
    recent_exc = next(e for e in exceptions if e.settlement_batch_id == recent_batch.id)

    assert old_exc.exception_type == ExceptionTypeEnum.MISSING_BANK_CREDIT
    assert old_exc.severity == ExceptionSeverityEnum.CRITICAL  # >= 100k
    assert "UTR_OLD_123" in old_exc.title

    assert recent_exc.exception_type == ExceptionTypeEnum.TIMING_DIFFERENCE
    assert recent_exc.severity == ExceptionSeverityEnum.LOW


def test_classify_unbilled_gateway_charge_and_unidentified_bank_deposit(db_session):
    """Test unmatched gateway charges and unmatched bank credits."""
    org = Organisation(name="Unbilled Corp", slug="unbilled-corp")
    db_session.add(org)
    db_session.commit()

    run = ReconciliationRun(org_id=org.id, status=ReconciliationRunStatusEnum.COMPLETED)
    db_session.add(run)
    db_session.commit()

    # Unmatched charge captured 5 days ago -> UNBILLED_CHARGE
    txn = GatewayTransaction(
        org_id=org.id,
        txn_id="pay_orphan_01",
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.CARD,
        amount=Decimal("15000.00"),
        net_amount=Decimal("15000.00"),
        customer_email="orphan@customer.com",
        captured_at=datetime.now(timezone.utc) - timedelta(days=5),
        status=TxnStatusEnum.CAPTURED,
        reconciliation_status=GtwReconStatus.UNMATCHED,
    )
    # Unmatched bank deposit -> UNIDENTIFIED_BANK_DEPOSIT
    credit = BankCredit(
        org_id=org.id,
        transaction_date=datetime(2026, 4, 10),
        narration="CMS/NEFT/UNKNOWN-ENTERPRISE-WIRE",
        credit_amount=Decimal("250000.00"),
        reconciliation_status=BnkReconStatus.UNMATCHED,
    )
    db_session.add_all([txn, credit])
    db_session.commit()

    exceptions = ExceptionClassifierEngine.classify_and_record_exceptions(
        db=db_session,
        run=run,
        invoices=[],
        gateway_txns=[txn],
        settlement_batches=[],
        bank_credits=[credit],
        matches=[],
    )

    assert len(exceptions) == 2
    txn_exc = next(e for e in exceptions if e.gateway_txn_id == txn.id)
    credit_exc = next(e for e in exceptions if e.bank_credit_id == credit.id)

    assert txn_exc.exception_type == ExceptionTypeEnum.UNBILLED_CHARGE
    assert txn_exc.severity == ExceptionSeverityEnum.HIGH
    assert "orphan@customer.com" in txn_exc.root_cause_explanation

    assert credit_exc.exception_type == ExceptionTypeEnum.UNIDENTIFIED_BANK_DEPOSIT
    assert credit_exc.severity == ExceptionSeverityEnum.HIGH  # >= 100k
    assert "UNKNOWN-ENTERPRISE-WIRE" in credit_exc.root_cause_explanation


def test_classify_paisa_rounding_delta_and_amount_mismatch(db_session):
    """Test match discrepancy classification: <= ₹5 is rounding delta, > ₹5 is amount mismatch."""
    org = Organisation(name="Discrepancy Corp", slug="discrepancy-corp")
    db_session.add(org)
    db_session.commit()

    run = ReconciliationRun(org_id=org.id, status=ReconciliationRunStatusEnum.COMPLETED)
    db_session.add(run)
    db_session.commit()

    # 1. 35 paise delta -> PAISA_ROUNDING_DELTA
    m1 = ReconciliationMatch(
        org_id=org.id,
        run_id=run.id,
        layer=ReconciliationLayerEnum.LAYER_2,
        match_type=MatchTypeEnum.EXACT,
        status=MatchStatusEnum.DISCREPANCY,
        confidence_score=Decimal("95.00"),
        amount_difference=Decimal("0.35"),
    )
    # 2. ₹2,000 delta on Layer 1 -> AMOUNT_MISMATCH
    m2 = ReconciliationMatch(
        org_id=org.id,
        run_id=run.id,
        layer=ReconciliationLayerEnum.LAYER_1,
        match_type=MatchTypeEnum.EXACT,
        status=MatchStatusEnum.PARTIAL,
        confidence_score=Decimal("80.00"),
        amount_difference=Decimal("-2000.00"),
    )
    db_session.add_all([m1, m2])
    db_session.commit()

    exceptions = ExceptionClassifierEngine.classify_and_record_exceptions(
        db=db_session,
        run=run,
        invoices=[],
        gateway_txns=[],
        settlement_batches=[],
        bank_credits=[],
        matches=[m1, m2],
    )

    assert len(exceptions) == 2
    rounding_exc = next(e for e in exceptions if e.exception_type == ExceptionTypeEnum.PAISA_ROUNDING_DELTA)
    mismatch_exc = next(e for e in exceptions if e.exception_type == ExceptionTypeEnum.AMOUNT_MISMATCH)

    assert rounding_exc.severity == ExceptionSeverityEnum.LOW
    assert rounding_exc.discrepancy_amount == Decimal("0.35")
    assert "1-click write-off" in rounding_exc.suggested_action

    assert mismatch_exc.severity == ExceptionSeverityEnum.MEDIUM
    assert mismatch_exc.discrepancy_amount == Decimal("2000.00")


def test_resolver_manual_match_linking(db_session):
    """Test manual match linking invoice to gateway transaction."""
    org = Organisation(name="Match Org", slug="match-org")
    db_session.add(org)
    db_session.commit()

    user = User(
        org_id=org.id,
        email="cfo@matchorg.com",
        hashed_password="hash",
        full_name="CFO",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    db_session.commit()

    inv = Invoice(
        org_id=org.id,
        invoice_no="INV-MANUAL-01",
        customer_id="cust_m1",
        amount=Decimal("5000.00"),
        tax_amount=Decimal("900.00"),
        currency="INR",
        status=InvoiceStatusEnum.PAID,
        invoice_date=datetime(2026, 4, 1),
        reconciliation_status=InvReconStatus.UNMATCHED,
    )
    txn = GatewayTransaction(
        org_id=org.id,
        txn_id="pay_manual_01",
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.UPI,
        amount=Decimal("5000.00"),
        net_amount=Decimal("5000.00"),
        captured_at=datetime.utcnow(),
        status=TxnStatusEnum.CAPTURED,
        reconciliation_status=GtwReconStatus.UNMATCHED,
    )
    db_session.add_all([inv, txn])
    db_session.commit()

    # Exception for unmatched invoice
    exc = ReconciliationException(
        org_id=org.id,
        invoice_id=inv.id,
        exception_type=ExceptionTypeEnum.AMOUNT_MISMATCH,
        severity=ExceptionSeverityEnum.MEDIUM,
        expected_amount=Decimal("5000.00"),
        actual_amount=Decimal("0.00"),
        discrepancy_amount=Decimal("5000.00"),
        title="Unmatched invoice INV-MANUAL-01",
        root_cause_explanation="Invoice not matched to any gateway payment.",
    )
    db_session.add(exc)
    db_session.commit()

    # Execute manual match
    resolved_exc = ExceptionResolverService.resolve_with_manual_match(
        db=db_session,
        exception_id=exc.id,
        org_id=org.id,
        user_id=user.id,
        target_entity_type="gateway_txn",
        target_entity_id=txn.id,
        notes="Customer confirmed payment reference verbally",
    )

    assert resolved_exc.status == ResolutionStatusEnum.RESOLVED
    assert resolved_exc.resolution_action == ResolutionActionEnum.MANUAL_MATCH
    assert resolved_exc.resolved_by == user.id
    assert resolved_exc.gateway_txn_id == txn.id

    # Verify entities are now MATCHED
    db_session.refresh(inv)
    db_session.refresh(txn)
    assert inv.reconciliation_status == InvReconStatus.MATCHED
    assert txn.reconciliation_status == GtwReconStatus.MATCHED

    # Verify manual match created
    match = db_session.query(ReconciliationMatch).filter_by(invoice_id=inv.id, gateway_txn_id=txn.id).first()
    assert match is not None
    assert match.match_type == MatchTypeEnum.MANUAL
    assert match.confidence_score == Decimal("100.00")


def test_resolver_single_and_batch_write_offs(db_session):
    """Test 1-click write-off for minor rounding deltas."""
    org = Organisation(name="WriteOff Corp", slug="writeoff-corp")
    db_session.add(org)
    db_session.commit()

    user = User(
        org_id=org.id,
        email="analyst@writeoff.com",
        hashed_password="hash",
        role=UserRole.FINANCE_ANALYST,
    )
    db_session.add(user)
    db_session.commit()

    # Create 3 open rounding exceptions under ₹5
    e1 = ReconciliationException(
        org_id=org.id,
        exception_type=ExceptionTypeEnum.PAISA_ROUNDING_DELTA,
        severity=ExceptionSeverityEnum.LOW,
        expected_amount=Decimal("100.00"),
        discrepancy_amount=Decimal("0.45"),
        title="45p delta",
        root_cause_explanation="GST round-off",
    )
    e2 = ReconciliationException(
        org_id=org.id,
        exception_type=ExceptionTypeEnum.PAISA_ROUNDING_DELTA,
        severity=ExceptionSeverityEnum.LOW,
        expected_amount=Decimal("200.00"),
        discrepancy_amount=Decimal("1.20"),
        title="₹1.20 delta",
        root_cause_explanation="Bank fee round-off",
    )
    # 1 larger exception of ₹500
    e3 = ReconciliationException(
        org_id=org.id,
        exception_type=ExceptionTypeEnum.AMOUNT_MISMATCH,
        severity=ExceptionSeverityEnum.MEDIUM,
        expected_amount=Decimal("5000.00"),
        discrepancy_amount=Decimal("500.00"),
        title="₹500 delta",
        root_cause_explanation="Underpayment",
    )
    db_session.add_all([e1, e2, e3])
    db_session.commit()

    # 1. Bulk write off minor rounding deltas <= ₹5.00
    batch_res = ExceptionResolverService.resolve_batch_write_off(
        db=db_session,
        org_id=org.id,
        user_id=user.id,
        max_threshold=Decimal("5.00"),
    )
    assert len(batch_res) == 2
    assert all(e.status == ResolutionStatusEnum.WRITTEN_OFF for e in batch_res)

    # e3 remains OPEN (was > ₹5)
    db_session.refresh(e3)
    assert e3.status == ResolutionStatusEnum.OPEN

    # 2. Attempting to write off e3 with default limit (₹50) should be rejected
    with pytest.raises(Exception) as excinfo:
        ExceptionResolverService.resolve_with_write_off(
            db=db_session,
            exception_id=e3.id,
            org_id=org.id,
            user_id=user.id,
            max_allowed=Decimal("50.00"),
        )
    assert "exceeds standard write-off limit" in str(excinfo.value)
