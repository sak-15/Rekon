"""
Unit & Integration tests for Layer 1 Reconciliation Matching Engine.
Tests exact reference matching, paisa rounding tolerances, heuristic fuzzy fallback,
date proximity windows, discrepancy detection, and multi-tenant isolation.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal

from app.models import (
    Organisation,
    Invoice,
    InvoiceStatusEnum,
    GatewayTransaction,
    GatewayEnum,
    PaymentMethodEnum,
    TxnStatusEnum,
    ReconciliationRun,
    ReconciliationStatusEnum,
    ReconciliationLayerEnum,
    MatchTypeEnum,
    MatchStatusEnum,
)
from app.schemas.reconciliation import ReconciliationRuleConfig
from app.services.matching.layer1 import Layer1MatchingEngine


def test_layer1_exact_reference_match_zero_delta(db_session):
    """
    Verify exact reference matching where invoice_no == txn.invoice_ref and amounts are identical.
    Expected: MATCHED, MatchType.EXACT, 100% confidence, amount_diff = 0.00.
    """
    org = Organisation(name="Exact Match Org", slug="exact-match-org")
    db_session.add(org)
    db_session.commit()

    now = datetime.now(timezone.utc)

    inv = Invoice(
        org_id=org.id,
        invoice_no="INV-1001",
        customer_id="CUST-1",
        customer_email="alice@company.com",
        amount=Decimal("4999.00"),
        status=InvoiceStatusEnum.PAID,
        invoice_date=now,
    )
    txn = GatewayTransaction(
        org_id=org.id,
        txn_id="pay_exact_001",
        gateway=GatewayEnum.RAZORPAY,
        invoice_ref="INV-1001",
        customer_email="alice@company.com",
        amount=Decimal("4999.00"),
        net_amount=Decimal("4889.02"),
        status=TxnStatusEnum.CAPTURED,
        captured_at=now,
    )
    db_session.add_all([inv, txn])
    db_session.commit()

    run = ReconciliationRun(org_id=org.id)
    db_session.add(run)
    db_session.commit()

    engine = Layer1MatchingEngine()
    output = engine.execute(
        org_id=org.id,
        run_id=run.id,
        invoices=[inv],
        gateway_txns=[txn],
    )

    assert output.summary.matched_invoices == 1
    assert output.summary.unmatched_invoices == 0
    assert output.summary.exact_matches_count == 1
    assert len(output.matches) == 1

    match = output.matches[0]
    assert match.layer == ReconciliationLayerEnum.LAYER_1
    assert match.invoice_id == inv.id
    assert match.gateway_txn_id == txn.id
    assert match.match_type == MatchTypeEnum.EXACT
    assert match.confidence_score == Decimal("100.00")
    assert match.status == MatchStatusEnum.MATCHED
    assert match.amount_difference == Decimal("0.00")
    assert inv.reconciliation_status == ReconciliationStatusEnum.MATCHED
    assert txn.reconciliation_status == ReconciliationStatusEnum.MATCHED


def test_layer1_exact_match_with_paisa_tolerance(db_session):
    """
    Verify exact reference matching with minor paisa rounding difference within tolerance (<= ₹1.00).
    Example: Chargebee invoice is ₹5,898.82, Razorpay charge is ₹5,899.00 (delta = ₹0.18).
    Expected: MATCHED, MatchType.EXACT, 95% confidence, delta recorded.
    """
    org = Organisation(name="Paisa Org", slug="paisa-org")
    db_session.add(org)
    db_session.commit()

    now = datetime.now(timezone.utc)

    inv = Invoice(
        org_id=org.id,
        invoice_no="INV-ROUNDING-01",
        customer_id="CUST-2",
        customer_email="bob@saas.com",
        amount=Decimal("5898.82"),
        status=InvoiceStatusEnum.PAID,
        invoice_date=now,
    )
    txn = GatewayTransaction(
        org_id=org.id,
        txn_id="pay_rounding_001",
        gateway=GatewayEnum.RAZORPAY,
        invoice_ref="INV-ROUNDING-01",
        amount=Decimal("5899.00"),
        net_amount=Decimal("5770.00"),
        status=TxnStatusEnum.CAPTURED,
        captured_at=now,
    )
    db_session.add_all([inv, txn])
    db_session.commit()

    run = ReconciliationRun(org_id=org.id)
    db_session.add(run)
    db_session.commit()

    # Run with default rule config (amount_tolerance = 1.00)
    engine = Layer1MatchingEngine(ReconciliationRuleConfig(amount_tolerance=Decimal("1.00")))
    output = engine.execute(
        org_id=org.id,
        run_id=run.id,
        invoices=[inv],
        gateway_txns=[txn],
    )

    assert output.summary.matched_invoices == 1
    assert output.summary.exact_matches_count == 1
    match = output.matches[0]
    assert match.status == MatchStatusEnum.MATCHED
    assert match.amount_difference == Decimal("0.18")
    assert match.confidence_score == Decimal("95.00")
    assert inv.reconciliation_status == ReconciliationStatusEnum.MATCHED


def test_layer1_exact_match_with_amount_discrepancy(db_session):
    """
    Verify exact reference matching where invoice_ref matches but amount difference exceeds tolerance.
    Example: Invoice ₹10,000 billed, customer paid partial ₹7,500 (delta ₹2,500 > ₹1.00).
    Expected: PARTIAL / EXCEPTION status, confidence 80%, flagged in summary.
    """
    org = Organisation(name="Discrepancy Org", slug="discrepancy-org")
    db_session.add(org)
    db_session.commit()

    now = datetime.now(timezone.utc)

    inv = Invoice(
        org_id=org.id,
        invoice_no="INV-PARTIAL-01",
        customer_id="CUST-3",
        amount=Decimal("10000.00"),
        status=InvoiceStatusEnum.PAID,
        invoice_date=now,
    )
    txn = GatewayTransaction(
        org_id=org.id,
        txn_id="pay_partial_001",
        gateway=GatewayEnum.STRIPE,
        invoice_ref="INV-PARTIAL-01",
        amount=Decimal("7500.00"),
        net_amount=Decimal("7300.00"),
        status=TxnStatusEnum.CAPTURED,
        captured_at=now,
    )
    db_session.add_all([inv, txn])
    db_session.commit()

    run = ReconciliationRun(org_id=org.id)
    db_session.add(run)
    db_session.commit()

    engine = Layer1MatchingEngine()
    output = engine.execute(
        org_id=org.id,
        run_id=run.id,
        invoices=[inv],
        gateway_txns=[txn],
    )

    assert output.summary.discrepancy_invoices == 1
    assert output.summary.total_discrepancy_amount == Decimal("2500.00")
    assert inv.reconciliation_status == ReconciliationStatusEnum.EXCEPTION
    assert txn.reconciliation_status == ReconciliationStatusEnum.EXCEPTION

    match = output.matches[0]
    assert match.status == MatchStatusEnum.PARTIAL
    assert match.amount_difference == Decimal("2500.00")


def test_layer1_fuzzy_heuristic_fallback(db_session):
    """
    Verify fuzzy fallback matching when the gateway transaction lacks an invoice_ref.
    Matches by: customer_email + exact amount + date proximity (e.g. captured 1 day after invoice).
    Expected: MATCHED, MatchType.FUZZY, confidence ~88%, audit notes recorded.
    """
    org = Organisation(name="Fuzzy Org", slug="fuzzy-org")
    db_session.add(org)
    db_session.commit()

    invoice_date = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    captured_date = datetime(2026, 9, 2, 14, 30, tzinfo=timezone.utc)  # 1 day later

    inv = Invoice(
        org_id=org.id,
        invoice_no="INV-FUZZY-99",
        customer_id="CUST-4",
        customer_email="founder@startup.io",
        amount=Decimal("2999.00"),
        status=InvoiceStatusEnum.PAID,
        invoice_date=invoice_date,
    )
    # Gateway charge has NO invoice_ref
    txn = GatewayTransaction(
        org_id=org.id,
        txn_id="pay_fuzzy_unlabeled",
        gateway=GatewayEnum.RAZORPAY,
        invoice_ref=None,
        customer_email="founder@startup.io",
        amount=Decimal("2999.00"),
        net_amount=Decimal("2930.00"),
        status=TxnStatusEnum.CAPTURED,
        captured_at=captured_date,
    )
    db_session.add_all([inv, txn])
    db_session.commit()

    run = ReconciliationRun(org_id=org.id)
    db_session.add(run)
    db_session.commit()

    engine = Layer1MatchingEngine(ReconciliationRuleConfig(layer_1_date_window_days=2))
    output = engine.execute(
        org_id=org.id,
        run_id=run.id,
        invoices=[inv],
        gateway_txns=[txn],
    )

    assert output.summary.matched_invoices == 1
    assert output.summary.fuzzy_matches_count == 1
    assert len(output.matches) == 1

    match = output.matches[0]
    assert match.match_type == MatchTypeEnum.FUZZY
    assert match.status == MatchStatusEnum.MATCHED
    assert match.confidence_score >= Decimal("85.00")
    assert match.match_details["matched_by"] == "customer_email_amount_date"
    assert match.match_details["date_diff_days"] == 1
    assert inv.reconciliation_status == ReconciliationStatusEnum.MATCHED
    assert txn.reconciliation_status == ReconciliationStatusEnum.MATCHED


def test_layer1_fuzzy_date_window_boundary_rejection(db_session):
    """
    Verify that fuzzy matching respects the date proximity window.
    If payment occurred 4 days after invoice and date window is 2 days, fuzzy match must NOT link them.
    Expected: Invoice remains UNMATCHED, Transaction remains UNMATCHED.
    """
    org = Organisation(name="Boundary Org", slug="boundary-org")
    db_session.add(org)
    db_session.commit()

    invoice_date = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    captured_date = datetime(2026, 9, 6, 10, 0, tzinfo=timezone.utc)  # 5 days later (> 2 days window)

    inv = Invoice(
        org_id=org.id,
        invoice_no="INV-LAG-01",
        customer_id="CUST-5",
        customer_email="late@payer.com",
        amount=Decimal("1500.00"),
        invoice_date=invoice_date,
    )
    txn = GatewayTransaction(
        org_id=org.id,
        txn_id="pay_late_unlabeled",
        gateway=GatewayEnum.RAZORPAY,
        invoice_ref=None,
        customer_email="late@payer.com",
        amount=Decimal("1500.00"),
        net_amount=Decimal("1460.00"),
        status=TxnStatusEnum.CAPTURED,
        captured_at=captured_date,
    )
    db_session.add_all([inv, txn])
    db_session.commit()

    run = ReconciliationRun(org_id=org.id)
    db_session.add(run)
    db_session.commit()

    engine = Layer1MatchingEngine(ReconciliationRuleConfig(layer_1_date_window_days=2))
    output = engine.execute(
        org_id=org.id,
        run_id=run.id,
        invoices=[inv],
        gateway_txns=[txn],
    )

    assert output.summary.matched_invoices == 0
    assert output.summary.unmatched_invoices == 1
    assert output.summary.unmatched_txns == 1
    assert len(output.matches) == 0
    assert inv.reconciliation_status == ReconciliationStatusEnum.UNMATCHED
    assert txn.reconciliation_status == ReconciliationStatusEnum.UNMATCHED


def test_layer1_multi_tenant_isolation(db_session):
    """
    Verify that an invoice from Tenant Alpha is NEVER matched with a gateway transaction from Tenant Beta,
    even if invoice_no and invoice_ref match.
    """
    org_alpha = Organisation(name="Tenant Alpha", slug="alpha-matching")
    org_beta = Organisation(name="Tenant Beta", slug="beta-matching")
    db_session.add_all([org_alpha, org_beta])
    db_session.commit()

    now = datetime.now(timezone.utc)

    # Invoice in Alpha
    inv_alpha = Invoice(
        org_id=org_alpha.id,
        invoice_no="INV-COLLISION-1",
        customer_id="CUST-A",
        amount=Decimal("5000.00"),
        invoice_date=now,
    )
    # Txn in Beta with identical reference
    txn_beta = GatewayTransaction(
        org_id=org_beta.id,
        txn_id="pay_beta_collision",
        gateway=GatewayEnum.RAZORPAY,
        invoice_ref="INV-COLLISION-1",
        amount=Decimal("5000.00"),
        net_amount=Decimal("4882.00"),
        status=TxnStatusEnum.CAPTURED,
        captured_at=now,
    )
    db_session.add_all([inv_alpha, txn_beta])
    db_session.commit()

    run_alpha = ReconciliationRun(org_id=org_alpha.id)
    db_session.add(run_alpha)
    db_session.commit()

    engine = Layer1MatchingEngine()
    output = engine.execute(
        org_id=org_alpha.id,
        run_id=run_alpha.id,
        invoices=[inv_alpha],
        gateway_txns=[txn_beta],
    )

    # Tenant Alpha's run should NOT match Tenant Beta's transaction
    assert output.summary.matched_invoices == 0
    assert output.summary.unmatched_invoices == 1
    assert len(output.matches) == 0
    assert inv_alpha.reconciliation_status == ReconciliationStatusEnum.UNMATCHED


def test_layer1_custom_rule_config_overrides(db_session):
    """
    Verify client customization: Setting amount_tolerance = 0.05 causes an 18 paise difference
    to be classified as EXCEPTION / DISCREPANCY instead of matched.
    """
    org = Organisation(name="Strict Org", slug="strict-org")
    db_session.add(org)
    db_session.commit()

    now = datetime.now(timezone.utc)

    inv = Invoice(
        org_id=org.id,
        invoice_no="INV-STRICT-01",
        customer_id="CUST-6",
        amount=Decimal("100.18"),
        invoice_date=now,
    )
    txn = GatewayTransaction(
        org_id=org.id,
        txn_id="pay_strict_01",
        gateway=GatewayEnum.RAZORPAY,
        invoice_ref="INV-STRICT-01",
        amount=Decimal("100.00"),  # 0.18 diff
        net_amount=Decimal("98.00"),
        status=TxnStatusEnum.CAPTURED,
        captured_at=now,
    )
    db_session.add_all([inv, txn])
    db_session.commit()

    run = ReconciliationRun(org_id=org.id)
    db_session.add(run)
    db_session.commit()

    # Set strict 5 paise tolerance
    strict_config = ReconciliationRuleConfig(amount_tolerance=Decimal("0.05"))
    engine = Layer1MatchingEngine(config=strict_config)

    output = engine.execute(
        org_id=org.id,
        run_id=run.id,
        invoices=[inv],
        gateway_txns=[txn],
    )

    # 18 paise > 5 paise tolerance -> should be flagged as discrepancy
    assert output.summary.discrepancy_invoices == 1
    assert output.matches[0].status == MatchStatusEnum.PARTIAL

