"""
Unit & Integration tests for Layer 2 Reconciliation Matching Engine.
Validates linking Payment Gateway Transactions to Settlement Lines,
fee deduction mathematics, fee discrepancy detection, and unsettled tracking.
"""

from datetime import datetime, timezone
from decimal import Decimal

from app.models import (
    Organisation,
    GatewayTransaction,
    GatewayEnum,
    PaymentMethodEnum,
    TxnStatusEnum,
    SettlementStatusEnum,
    SettlementBatch,
    SettlementLine,
    SettlementLineTypeEnum,
    ReconciliationRun,
    ReconciliationLayerEnum,
    MatchTypeEnum,
    MatchStatusEnum,
)
from app.schemas.reconciliation import ReconciliationRuleConfig
from app.services.matching.layer2 import Layer2MatchingEngine


def test_layer2_exact_match_zero_delta(db_session):
    """
    Verify exact match where txn_id == line.txn_ref, gross amounts are equal,
    and fee deductions (fee + tax) match with zero difference.
    """
    org = Organisation(name="Settlement Org", slug="settlement-org")
    db_session.add(org)
    db_session.commit()

    now = datetime.now(timezone.utc)

    # 1. Gateway Transaction
    txn = GatewayTransaction(
        org_id=org.id,
        txn_id="pay_clean_001",
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.UPI,
        amount=Decimal("5000.00"),
        gateway_fee=Decimal("100.00"),
        gateway_fee_gst=Decimal("18.00"),
        net_amount=Decimal("4882.00"),
        status=TxnStatusEnum.CAPTURED,
        captured_at=now,
    )
    db_session.add(txn)

    # 2. Settlement Batch & Line
    batch = SettlementBatch(
        org_id=org.id,
        batch_id="batch_001",
        gateway=GatewayEnum.RAZORPAY,
        settlement_date=now,
        gross_amount=Decimal("5000.00"),
        total_fees=Decimal("100.00"),
        total_gst=Decimal("18.00"),
        net_amount=Decimal("4882.00"),
    )
    db_session.add(batch)
    db_session.commit()

    line = SettlementLine(
        org_id=org.id,
        batch_id=batch.id,
        txn_ref="pay_clean_001",
        line_type=SettlementLineTypeEnum.PAYMENT,
        amount=Decimal("5000.00"),
        fee=Decimal("100.00"),
        tax=Decimal("18.00"),
    )
    db_session.add(line)
    db_session.commit()

    run = ReconciliationRun(org_id=org.id)
    db_session.add(run)
    db_session.commit()

    engine = Layer2MatchingEngine()
    output = engine.execute(
        org_id=org.id,
        run_id=run.id,
        gateway_txns=[txn],
        settlement_lines=[line],
    )

    assert output.summary.settled_txns == 1
    assert output.summary.unsettled_txns == 0
    assert output.summary.fee_discrepancy_txns == 0
    assert output.summary.total_settled_gross_amount == Decimal("5000.00")
    assert output.summary.total_settled_net_amount == Decimal("4882.00")
    assert output.summary.total_fees_deducted == Decimal("100.00")
    assert output.summary.total_gst_deducted == Decimal("18.00")

    assert txn.settlement_status == SettlementStatusEnum.SETTLED
    assert len(output.matches) == 1

    match = output.matches[0]
    assert match.layer == ReconciliationLayerEnum.LAYER_2
    assert match.gateway_txn_id == txn.id
    assert match.settlement_line_id == line.id
    assert match.settlement_batch_id == batch.id
    assert match.match_type == MatchTypeEnum.EXACT
    assert match.confidence_score == Decimal("100.00")
    assert match.status == MatchStatusEnum.MATCHED
    assert match.amount_difference == Decimal("0.00")


def test_layer2_match_with_paisa_tolerance(db_session):
    """
    Verify matching when fees have minor fractional rounding difference within tolerance (<= ₹1.00).
    Expected: MATCHED, 95% confidence, txn settled.
    """
    org = Organisation(name="Tolerance Org", slug="tolerance-org")
    db_session.add(org)
    db_session.commit()

    now = datetime.now(timezone.utc)

    txn = GatewayTransaction(
        org_id=org.id,
        txn_id="pay_tol_001",
        gateway=GatewayEnum.STRIPE,
        amount=Decimal("4999.00"),
        gateway_fee=Decimal("99.98"),
        gateway_fee_gst=Decimal("18.00"),
        net_amount=Decimal("4881.02"),
        status=TxnStatusEnum.CAPTURED,
        captured_at=now,
    )
    batch = SettlementBatch(
        org_id=org.id,
        batch_id="batch_tol_01",
        gateway=GatewayEnum.STRIPE,
        settlement_date=now,
        gross_amount=Decimal("4999.00"),
        net_amount=Decimal("4881.00"),
    )
    db_session.add_all([txn, batch])
    db_session.commit()

    line = SettlementLine(
        org_id=org.id,
        batch_id=batch.id,
        txn_ref="pay_tol_001",
        amount=Decimal("4999.00"),
        fee=Decimal("100.00"),  # 2 paise diff
        tax=Decimal("18.00"),
    )
    db_session.add(line)
    db_session.commit()

    run = ReconciliationRun(org_id=org.id)
    db_session.add(run)
    db_session.commit()

    engine = Layer2MatchingEngine(ReconciliationRuleConfig(amount_tolerance=Decimal("1.00")))
    output = engine.execute(
        org_id=org.id,
        run_id=run.id,
        gateway_txns=[txn],
        settlement_lines=[line],
    )

    assert output.summary.settled_txns == 1
    assert output.summary.fee_discrepancy_txns == 0
    assert txn.settlement_status == SettlementStatusEnum.SETTLED
    assert output.matches[0].status == MatchStatusEnum.MATCHED
    assert output.matches[0].confidence_score == Decimal("95.00")


def test_layer2_fee_deduction_discrepancy(db_session):
    """
    Verify fee deduction anomaly: Gateway deducted a significantly higher fee in settlement
    than expected in the transaction record (e.g. unexpected rate card tier).
    Expected: Txn marked SETTLED, but match status is DISCREPANCY with fee difference recorded.
    """
    org = Organisation(name="Fee Audit Org", slug="fee-audit-org")
    db_session.add(org)
    db_session.commit()

    now = datetime.now(timezone.utc)

    # Recorded fee: 200.00 + 36.00 GST = 236.00
    txn = GatewayTransaction(
        org_id=org.id,
        txn_id="pay_fee_overcharge",
        gateway=GatewayEnum.RAZORPAY,
        amount=Decimal("10000.00"),
        gateway_fee=Decimal("200.00"),
        gateway_fee_gst=Decimal("36.00"),
        net_amount=Decimal("9764.00"),
        status=TxnStatusEnum.CAPTURED,
        captured_at=now,
    )
    batch = SettlementBatch(
        org_id=org.id,
        batch_id="batch_fee_01",
        gateway=GatewayEnum.RAZORPAY,
        settlement_date=now,
        gross_amount=Decimal("10000.00"),
        net_amount=Decimal("9587.00"),
    )
    db_session.add_all([txn, batch])
    db_session.commit()

    # Settlement file deducted 350.00 fee + 63.00 GST = 413.00 (delta = 177.00)
    line = SettlementLine(
        org_id=org.id,
        batch_id=batch.id,
        txn_ref="pay_fee_overcharge",
        amount=Decimal("10000.00"),
        fee=Decimal("350.00"),
        tax=Decimal("63.00"),
    )
    db_session.add(line)
    db_session.commit()

    run = ReconciliationRun(org_id=org.id)
    db_session.add(run)
    db_session.commit()

    engine = Layer2MatchingEngine()
    output = engine.execute(
        org_id=org.id,
        run_id=run.id,
        gateway_txns=[txn],
        settlement_lines=[line],
    )

    assert output.summary.settled_txns == 1
    assert output.summary.fee_discrepancy_txns == 1
    assert output.summary.total_fee_discrepancy_amount == Decimal("177.00")
    assert txn.settlement_status == SettlementStatusEnum.SETTLED

    match = output.matches[0]
    assert match.status == MatchStatusEnum.DISCREPANCY
    assert match.confidence_score == Decimal("85.00")
    assert match.match_details["total_deduction_diff"] == "177.00"
    assert match.match_details["fee_diff"] == "150.00"
    assert match.match_details["gst_diff"] == "27.00"


def test_layer2_unsettled_transactions_identification(db_session):
    """
    Verify identification of in-flight / unsettled transactions.
    Captured payments that do not appear in any settlement line must remain UNSETTLED.
    """
    org = Organisation(name="Inflight Org", slug="inflight-org")
    db_session.add(org)
    db_session.commit()

    now = datetime.now(timezone.utc)

    # In-flight payment (no settlement line exists)
    txn_inflight = GatewayTransaction(
        org_id=org.id,
        txn_id="pay_pending_payout",
        gateway=GatewayEnum.RAZORPAY,
        amount=Decimal("8000.00"),
        net_amount=Decimal("7811.20"),
        status=TxnStatusEnum.CAPTURED,
        captured_at=now,
    )
    db_session.add(txn_inflight)
    db_session.commit()

    run = ReconciliationRun(org_id=org.id)
    db_session.add(run)
    db_session.commit()

    engine = Layer2MatchingEngine()
    output = engine.execute(
        org_id=org.id,
        run_id=run.id,
        gateway_txns=[txn_inflight],
        settlement_lines=[],  # No settlement lines uploaded yet
    )

    assert output.summary.settled_txns == 0
    assert output.summary.unsettled_txns == 1
    assert txn_inflight.settlement_status == SettlementStatusEnum.UNSETTLED
    assert len(output.matches) == 0


def test_layer2_unmatched_settlement_lines_identification(db_session):
    """
    Verify identification of orphan settlement lines (e.g. gateway manual adjustments or external charges).
    """
    org = Organisation(name="Orphan Line Org", slug="orphan-line-org")
    db_session.add(org)
    db_session.commit()

    now = datetime.now(timezone.utc)

    batch = SettlementBatch(
        org_id=org.id,
        batch_id="batch_orphan_01",
        gateway=GatewayEnum.RAZORPAY,
        settlement_date=now,
        gross_amount=Decimal("500.00"),
        net_amount=Decimal("500.00"),
    )
    db_session.add(batch)
    db_session.commit()

    line_orphan = SettlementLine(
        org_id=org.id,
        batch_id=batch.id,
        txn_ref="pay_unknown_ghost",
        line_type=SettlementLineTypeEnum.ADJUSTMENT,
        amount=Decimal("500.00"),
        fee=Decimal("0.00"),
        tax=Decimal("0.00"),
    )
    db_session.add(line_orphan)
    db_session.commit()

    run = ReconciliationRun(org_id=org.id)
    db_session.add(run)
    db_session.commit()

    engine = Layer2MatchingEngine()
    output = engine.execute(
        org_id=org.id,
        run_id=run.id,
        gateway_txns=[],
        settlement_lines=[line_orphan],
    )

    assert output.summary.matched_lines == 0
    assert output.summary.unmatched_lines == 1
    assert len(output.unmatched_lines) == 1
    assert output.unmatched_lines[0].txn_ref == "pay_unknown_ghost"


def test_layer2_multi_tenant_isolation(db_session):
    """
    Verify multi-tenant isolation: Tenant Alpha's transaction is NEVER matched
    against Tenant Beta's settlement line even with matching transaction references.
    """
    org_a = Organisation(name="Tenant A", slug="org-a-l2")
    org_b = Organisation(name="Tenant B", slug="org-b-l2")
    db_session.add_all([org_a, org_b])
    db_session.commit()

    now = datetime.now(timezone.utc)

    # Txn in Org A
    txn_a = GatewayTransaction(
        org_id=org_a.id,
        txn_id="pay_shared_ref_01",
        gateway=GatewayEnum.RAZORPAY,
        amount=Decimal("2000.00"),
        net_amount=Decimal("1952.80"),
        status=TxnStatusEnum.CAPTURED,
        captured_at=now,
    )
    # Line in Org B
    batch_b = SettlementBatch(
        org_id=org_b.id,
        batch_id="batch_b_01",
        gateway=GatewayEnum.RAZORPAY,
        settlement_date=now,
        gross_amount=Decimal("2000.00"),
        net_amount=Decimal("1952.80"),
    )
    db_session.add_all([txn_a, batch_b])
    db_session.commit()

    line_b = SettlementLine(
        org_id=org_b.id,
        batch_id=batch_b.id,
        txn_ref="pay_shared_ref_01",
        amount=Decimal("2000.00"),
        fee=Decimal("40.00"),
        tax=Decimal("7.20"),
    )
    db_session.add(line_b)
    db_session.commit()

    run_a = ReconciliationRun(org_id=org_a.id)
    db_session.add(run_a)
    db_session.commit()

    engine = Layer2MatchingEngine()
    output = engine.execute(
        org_id=org_a.id,
        run_id=run_a.id,
        gateway_txns=[txn_a],
        settlement_lines=[line_b],
    )

    # Txn in Org A must remain unsettled; no match created
    assert output.summary.settled_txns == 0
    assert output.summary.unsettled_txns == 1
    assert len(output.matches) == 0
    assert txn_a.settlement_status == SettlementStatusEnum.UNSETTLED

