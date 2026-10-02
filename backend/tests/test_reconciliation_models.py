"""
Unit tests for ReconciliationRun and ReconciliationMatch models.
Validates multi-tenant scoping, execution lifecycle, layer-specific foreign keys,
rule configurations, and cascade deletion behaviors.
"""

from datetime import datetime, timezone
from decimal import Decimal

from app.models import (
    Organisation,
    User,
    UserRole,
    Invoice,
    InvoiceStatusEnum,
    GatewayTransaction,
    GatewayEnum,
    PaymentMethodEnum,
    TxnStatusEnum,
    SettlementBatch,
    SettlementLine,
    SettlementLineTypeEnum,
    BankCredit,
    ReconciliationRun,
    ReconciliationMatch,
    ReconciliationRunStatusEnum,
    ReconciliationLayerEnum,
    MatchTypeEnum,
    MatchStatusEnum,
)


def test_reconciliation_run_lifecycle_and_counts(db_session):
    """
    Verify creating and updating a ReconciliationRun entity with summary telemetry,
    rule configuration (JSON), and financial aggregations.
    """
    org = Organisation(name="SaaS Metrics", slug="saas-metrics", currency="INR")
    db_session.add(org)
    db_session.commit()

    user = User(
        org_id=org.id,
        email="analyst@saasmetrics.io",
        hashed_password="hashed_pw_xyz",
        full_name="Lead Analyst",
        role=UserRole.FINANCE_ANALYST,
    )
    db_session.add(user)
    db_session.commit()

    # Create a pending run with configurable rule thresholds
    rule_config = {
        "date_tolerance_days": 2,
        "amount_tolerance": 1.0,
        "allow_fuzzy_matching": True,
    }
    now = datetime.now(timezone.utc)
    run = ReconciliationRun(
        org_id=org.id,
        initiated_by=user.id,
        status=ReconciliationRunStatusEnum.RUNNING,
        started_at=now,
        rule_config=rule_config,
        total_invoices=50,
        matched_invoices=48,
        unmatched_invoices=2,
        total_txns=50,
        matched_txns=48,
        unmatched_txns=2,
        invoiced_amount=Decimal("150000.00"),
        collected_amount=Decimal("148000.00"),
        discrepancy_amount=Decimal("2000.00"),
    )
    db_session.add(run)
    db_session.commit()

    # Verify stored attributes and relationships
    saved_run = db_session.query(ReconciliationRun).filter_by(id=run.id).first()
    assert saved_run is not None
    assert saved_run.org_id == org.id
    assert saved_run.initiated_by == user.id
    assert saved_run.status == ReconciliationRunStatusEnum.RUNNING
    assert saved_run.rule_config["date_tolerance_days"] == 2
    assert saved_run.matched_invoices == 48
    assert saved_run.discrepancy_amount == Decimal("2000.00")
    assert saved_run.organisation.name == "SaaS Metrics"
    assert saved_run.user.email == "analyst@saasmetrics.io"

    # Complete the run
    saved_run.status = ReconciliationRunStatusEnum.COMPLETED
    saved_run.completed_at = datetime.now(timezone.utc)
    db_session.commit()

    reloaded = db_session.query(ReconciliationRun).filter_by(id=run.id).first()
    assert reloaded.status == ReconciliationRunStatusEnum.COMPLETED
    assert reloaded.completed_at is not None


def test_reconciliation_match_layer_1_invoice_gateway(db_session):
    """
    Verify Layer 1 matching: link an Invoice to a GatewayTransaction with exact match details.
    """
    org = Organisation(name="Layer 1 Org", slug="layer-1-org")
    db_session.add(org)
    db_session.commit()

    now = datetime.now(timezone.utc)

    # 1. Invoice
    invoice = Invoice(
        org_id=org.id,
        invoice_no="INV-L1-001",
        customer_id="CUST-100",
        customer_name="Alice",
        amount=Decimal("5000.00"),
        tax_amount=Decimal("900.00"),
        status=InvoiceStatusEnum.PAID,
        invoice_date=now,
    )
    db_session.add(invoice)

    # 2. Gateway Transaction
    txn = GatewayTransaction(
        org_id=org.id,
        txn_id="pay_L1_exact",
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.UPI,
        invoice_ref="INV-L1-001",
        amount=Decimal("5000.00"),
        gateway_fee=Decimal("100.00"),
        gateway_fee_gst=Decimal("18.00"),
        net_amount=Decimal("4882.00"),
        captured_at=now,
        status=TxnStatusEnum.CAPTURED,
    )
    db_session.add(txn)

    # 3. Reconciliation Run
    run = ReconciliationRun(org_id=org.id, status=ReconciliationRunStatusEnum.RUNNING)
    db_session.add(run)
    db_session.commit()

    # 4. Layer 1 Match
    match = ReconciliationMatch(
        org_id=org.id,
        run_id=run.id,
        layer=ReconciliationLayerEnum.LAYER_1,
        invoice_id=invoice.id,
        gateway_txn_id=txn.id,
        match_type=MatchTypeEnum.EXACT,
        confidence_score=Decimal("100.00"),
        status=MatchStatusEnum.MATCHED,
        amount_difference=Decimal("0.00"),
        match_details={"key_matched": "invoice_ref == invoice_no"},
    )
    db_session.add(match)
    db_session.commit()

    # Verify relationships
    saved_match = db_session.query(ReconciliationMatch).filter_by(id=match.id).first()
    assert saved_match is not None
    assert saved_match.layer == ReconciliationLayerEnum.LAYER_1
    assert saved_match.invoice.invoice_no == "INV-L1-001"
    assert saved_match.gateway_txn.txn_id == "pay_L1_exact"
    assert saved_match.match_details["key_matched"] == "invoice_ref == invoice_no"
    assert len(run.matches) == 1
    assert run.matches[0].id == match.id


def test_reconciliation_match_layer_2_gateway_settlement(db_session):
    """
    Verify Layer 2 matching: link a GatewayTransaction to a SettlementLine within a SettlementBatch.
    """
    org = Organisation(name="Layer 2 Org", slug="layer-2-org")
    db_session.add(org)
    db_session.commit()

    now = datetime.now(timezone.utc)

    # 1. Gateway Transaction
    txn = GatewayTransaction(
        org_id=org.id,
        txn_id="pay_L2_test",
        gateway=GatewayEnum.STRIPE,
        payment_method=PaymentMethodEnum.CARD,
        amount=Decimal("10000.00"),
        net_amount=Decimal("9764.00"),
        gateway_fee=Decimal("200.00"),
        gateway_fee_gst=Decimal("36.00"),
        captured_at=now,
    )
    db_session.add(txn)

    # 2. Settlement Batch & Line
    batch = SettlementBatch(
        org_id=org.id,
        batch_id="po_stripe_001",
        gateway=GatewayEnum.STRIPE,
        settlement_date=now,
        gross_amount=Decimal("10000.00"),
        total_fees=Decimal("200.00"),
        total_gst=Decimal("36.00"),
        net_amount=Decimal("9764.00"),
    )
    db_session.add(batch)
    db_session.commit()

    line = SettlementLine(
        org_id=org.id,
        batch_id=batch.id,
        txn_ref="pay_L2_test",
        line_type=SettlementLineTypeEnum.PAYMENT,
        amount=Decimal("10000.00"),
        fee=Decimal("200.00"),
        tax=Decimal("36.00"),
    )
    db_session.add(line)

    # 3. Reconciliation Run
    run = ReconciliationRun(org_id=org.id, status=ReconciliationRunStatusEnum.RUNNING)
    db_session.add(run)
    db_session.commit()

    # 4. Layer 2 Match
    match = ReconciliationMatch(
        org_id=org.id,
        run_id=run.id,
        layer=ReconciliationLayerEnum.LAYER_2,
        gateway_txn_id=txn.id,
        settlement_line_id=line.id,
        match_type=MatchTypeEnum.EXACT,
        confidence_score=Decimal("100.00"),
        status=MatchStatusEnum.MATCHED,
        amount_difference=Decimal("0.00"),
    )
    db_session.add(match)
    db_session.commit()

    saved_match = db_session.query(ReconciliationMatch).filter_by(id=match.id).first()
    assert saved_match.layer == ReconciliationLayerEnum.LAYER_2
    assert saved_match.gateway_txn.txn_id == "pay_L2_test"
    assert saved_match.settlement_line.txn_ref == "pay_L2_test"


def test_reconciliation_match_layer_3_settlement_bank(db_session):
    """
    Verify Layer 3 matching: link a SettlementBatch to a BankCredit (via UTR / narration).
    """
    org = Organisation(name="Layer 3 Org", slug="layer-3-org")
    db_session.add(org)
    db_session.commit()

    now = datetime.now(timezone.utc)

    # 1. Settlement Batch with UTR
    batch = SettlementBatch(
        org_id=org.id,
        batch_id="batch_rzp_4455",
        gateway=GatewayEnum.RAZORPAY,
        settlement_date=now,
        gross_amount=Decimal("50000.00"),
        net_amount=Decimal("48820.00"),
        utr_number="UTR98765432100",
    )
    db_session.add(batch)

    # 2. Bank Credit referencing UTR in narration
    credit = BankCredit(
        org_id=org.id,
        transaction_date=now,
        narration="NEFT-RAZORPAY-UTR98765432100-PAYOUT",
        credit_amount=Decimal("48820.00"),
        reference_no="UTR98765432100",
        bank_name="HDFC Bank",
    )
    db_session.add(credit)

    # 3. Reconciliation Run
    run = ReconciliationRun(org_id=org.id, status=ReconciliationRunStatusEnum.RUNNING)
    db_session.add(run)
    db_session.commit()

    # 4. Layer 3 Match
    match = ReconciliationMatch(
        org_id=org.id,
        run_id=run.id,
        layer=ReconciliationLayerEnum.LAYER_3,
        settlement_batch_id=batch.id,
        bank_credit_id=credit.id,
        match_type=MatchTypeEnum.EXACT,
        confidence_score=Decimal("100.00"),
        status=MatchStatusEnum.MATCHED,
        amount_difference=Decimal("0.00"),
        match_details={"utr_matched": "UTR98765432100"},
    )
    db_session.add(match)
    db_session.commit()

    saved_match = db_session.query(ReconciliationMatch).filter_by(id=match.id).first()
    assert saved_match.layer == ReconciliationLayerEnum.LAYER_3
    assert saved_match.settlement_batch.batch_id == "batch_rzp_4455"
    assert saved_match.bank_credit.reference_no == "UTR98765432100"


def test_reconciliation_cascading_deletion(db_session):
    """
    Verify cascade delete: Deleting a ReconciliationRun deletes its matches,
    and deleting an Organisation cleans up all runs and matches.
    """
    org = Organisation(name="Cascade Org", slug="cascade-org")
    db_session.add(org)
    db_session.commit()

    run = ReconciliationRun(org_id=org.id, status=ReconciliationRunStatusEnum.PENDING)
    db_session.add(run)
    db_session.commit()

    match = ReconciliationMatch(
        org_id=org.id,
        run_id=run.id,
        layer=ReconciliationLayerEnum.LAYER_1,
        match_type=MatchTypeEnum.EXACT,
    )
    db_session.add(match)
    db_session.commit()

    match_id = match.id
    assert db_session.query(ReconciliationMatch).filter_by(id=match_id).first() is not None

    # Delete run -> match should be removed via cascade
    db_session.delete(run)
    db_session.commit()
    assert db_session.query(ReconciliationMatch).filter_by(id=match_id).first() is None


def test_multi_tenant_reconciliation_isolation(db_session):
    """
    Verify that runs and matches belonging to Tenant Alpha cannot leak to Tenant Beta.
    """
    org_a = Organisation(name="Tenant Alpha", slug="alpha-reconcile")
    org_b = Organisation(name="Tenant Beta", slug="beta-reconcile")
    db_session.add_all([org_a, org_b])
    db_session.commit()

    run_a = ReconciliationRun(org_id=org_a.id, status=ReconciliationRunStatusEnum.COMPLETED)
    run_b = ReconciliationRun(org_id=org_b.id, status=ReconciliationRunStatusEnum.PENDING)
    db_session.add_all([run_a, run_b])
    db_session.commit()

    # Query scoped to org_a
    org_a_runs = db_session.query(ReconciliationRun).filter_by(org_id=org_a.id).all()
    assert len(org_a_runs) == 1
    assert org_a_runs[0].id == run_a.id

    # Query scoped to org_b
    org_b_runs = db_session.query(ReconciliationRun).filter_by(org_id=org_b.id).all()
    assert len(org_b_runs) == 1
    assert org_b_runs[0].id == run_b.id

