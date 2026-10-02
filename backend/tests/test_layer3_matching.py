"""
Unit & Integration tests for Layer 3 Reconciliation Matching Engine.
Validates linking Settlement Batches to Bank Statement Credits via UTR,
narration parsing, clearing lag windows, and missing deposit alerting.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal

from app.models import (
    Organisation,
    GatewayEnum,
    SettlementBatch,
    BankCredit,
    ReconciliationRun,
    ReconciliationStatusEnum,
    ReconciliationLayerEnum,
    MatchTypeEnum,
    MatchStatusEnum,
)
from app.schemas.reconciliation import ReconciliationRuleConfig
from app.services.matching.layer3 import Layer3MatchingEngine


def test_layer3_exact_utr_match_in_reference_no(db_session):
    """
    Verify exact match where batch.utr_number equals credit.reference_no and amounts match.
    """
    org = Organisation(name="UTR Ref Org", slug="utr-ref-org")
    db_session.add(org)
    db_session.commit()

    now = datetime.now(timezone.utc)

    # 1. Settlement Batch with UTR
    batch = SettlementBatch(
        org_id=org.id,
        batch_id="batch_utr_01",
        gateway=GatewayEnum.RAZORPAY,
        settlement_date=now,
        gross_amount=Decimal("50000.00"),
        net_amount=Decimal("48820.00"),
        utr_number="UTR12345678900",
    )
    db_session.add(batch)

    # 2. Bank Credit with exact reference_no
    credit = BankCredit(
        org_id=org.id,
        transaction_date=now,
        narration="NEFT CR - RAZORPAY - UTR12345678900",
        credit_amount=Decimal("48820.00"),
        reference_no="UTR12345678900",
        bank_name="HDFC Bank",
    )
    db_session.add(credit)
    db_session.commit()

    run = ReconciliationRun(org_id=org.id)
    db_session.add(run)
    db_session.commit()

    engine = Layer3MatchingEngine()
    output = engine.execute(
        org_id=org.id,
        run_id=run.id,
        settlement_batches=[batch],
        bank_credits=[credit],
    )

    assert output.summary.matched_batches == 1
    assert output.summary.unmatched_batches == 0
    assert output.summary.utr_matches_count == 1
    assert output.summary.total_settled_amount == Decimal("48820.00")
    assert output.summary.total_bank_credited_amount == Decimal("48820.00")

    assert batch.reconciliation_status == ReconciliationStatusEnum.MATCHED
    assert credit.reconciliation_status == ReconciliationStatusEnum.MATCHED
    assert len(output.matches) == 1

    match = output.matches[0]
    assert match.layer == ReconciliationLayerEnum.LAYER_3
    assert match.settlement_batch_id == batch.id
    assert match.bank_credit_id == credit.id
    assert match.match_type == MatchTypeEnum.EXACT
    assert match.confidence_score == Decimal("100.00")
    assert match.status == MatchStatusEnum.MATCHED


def test_layer3_utr_extracted_from_raw_narration(db_session):
    """
    Verify match when reference_no column is empty in bank statement,
    but the UTR is present inside the bank's complex narration text.
    """
    org = Organisation(name="Narration Extract Org", slug="narration-extract-org")
    db_session.add(org)
    db_session.commit()

    now = datetime.now(timezone.utc)

    batch = SettlementBatch(
        org_id=org.id,
        batch_id="batch_rzp_cms",
        gateway=GatewayEnum.RAZORPAY,
        settlement_date=now,
        gross_amount=Decimal("128000.00"),
        net_amount=Decimal("125000.00"),
        utr_number="CMS9876543210",
    )
    db_session.add(batch)

    # Bank statement has reference_no = None, but UTR in narration
    credit = BankCredit(
        org_id=org.id,
        transaction_date=now,
        narration="NEFT-RAZORPAY SOFTWARE PRIVAT-CMS9876543210-HDFC0000123",
        credit_amount=Decimal("125000.00"),
        reference_no=None,
        bank_name="HDFC Bank",
    )
    db_session.add(credit)
    db_session.commit()

    run = ReconciliationRun(org_id=org.id)
    db_session.add(run)
    db_session.commit()

    engine = Layer3MatchingEngine()
    output = engine.execute(
        org_id=org.id,
        run_id=run.id,
        settlement_batches=[batch],
        bank_credits=[credit],
    )

    assert output.summary.matched_batches == 1
    assert output.summary.utr_matches_count == 1
    assert batch.reconciliation_status == ReconciliationStatusEnum.MATCHED
    assert credit.reconciliation_status == ReconciliationStatusEnum.MATCHED

    match = output.matches[0]
    assert match.match_type == MatchTypeEnum.EXACT
    assert match.match_details["matched_by"] == "utr_number"
    assert match.match_details["utr"] == "CMS9876543210"


def test_layer3_match_with_paisa_tolerance(db_session):
    """
    Verify matching when net batch amount and bank credit amount have minor fractional difference (<= ₹1.00).
    """
    org = Organisation(name="Tolerance Org", slug="tolerance-org")
    db_session.add(org)
    db_session.commit()

    now = datetime.now(timezone.utc)

    batch = SettlementBatch(
        org_id=org.id,
        batch_id="batch_tol_01",
        gateway=GatewayEnum.STRIPE,
        settlement_date=now,
        gross_amount=Decimal("50000.00"),
        net_amount=Decimal("49999.82"),
        utr_number="STRIPE_UTR_44",
    )
    credit = BankCredit(
        org_id=org.id,
        transaction_date=now,
        narration="ACH CREDIT STRIPE STRIPE_UTR_44",
        credit_amount=Decimal("50000.00"),  # 0.18 diff <= 1.00
        reference_no="STRIPE_UTR_44",
    )
    db_session.add_all([batch, credit])
    db_session.commit()

    run = ReconciliationRun(org_id=org.id)
    db_session.add(run)
    db_session.commit()

    engine = Layer3MatchingEngine(ReconciliationRuleConfig(amount_tolerance=Decimal("1.00")))
    output = engine.execute(
        org_id=org.id,
        run_id=run.id,
        settlement_batches=[batch],
        bank_credits=[credit],
    )

    assert output.summary.matched_batches == 1
    match = output.matches[0]
    assert match.status == MatchStatusEnum.MATCHED
    assert match.amount_difference == Decimal("0.18")
    assert match.confidence_score == Decimal("95.00")


def test_layer3_amount_discrepancy_flagging(db_session):
    """
    Verify discrepancy detection: UTR matches, but bank deposited ₹5,000 less than promised in batch net.
    Expected: Status is DISCREPANCY, confidence 85%, discrepancy amount tracked.
    """
    org = Organisation(name="Discrepancy Org", slug="discrepancy-org")
    db_session.add(org)
    db_session.commit()

    now = datetime.now(timezone.utc)

    batch = SettlementBatch(
        org_id=org.id,
        batch_id="batch_short_01",
        gateway=GatewayEnum.RAZORPAY,
        settlement_date=now,
        gross_amount=Decimal("82000.00"),
        net_amount=Decimal("80000.00"),
        utr_number="UTR_SHORT_99",
    )
    # Bank only credited 75,000 (5,000 discrepancy)
    credit = BankCredit(
        org_id=org.id,
        transaction_date=now,
        narration="NEFT-RAZORPAY-UTR_SHORT_99",
        credit_amount=Decimal("75000.00"),
        reference_no="UTR_SHORT_99",
    )
    db_session.add_all([batch, credit])
    db_session.commit()

    run = ReconciliationRun(org_id=org.id)
    db_session.add(run)
    db_session.commit()

    engine = Layer3MatchingEngine()
    output = engine.execute(
        org_id=org.id,
        run_id=run.id,
        settlement_batches=[batch],
        bank_credits=[credit],
    )

    assert output.summary.discrepancy_batches == 1
    assert output.summary.total_discrepancy_amount == Decimal("5000.00")
    assert batch.reconciliation_status == ReconciliationStatusEnum.EXCEPTION
    assert credit.reconciliation_status == ReconciliationStatusEnum.EXCEPTION

    match = output.matches[0]
    assert match.status == MatchStatusEnum.DISCREPANCY
    assert match.amount_difference == Decimal("5000.00")


def test_layer3_heuristic_keyword_and_clearing_window_match(db_session):
    """
    Verify fallback matching when batch lacks UTR:
    Matches by gateway keyword in narration + exact net amount + deposit date within 4 days clearing window.
    """
    org = Organisation(name="Fallback Org", slug="fallback-org")
    db_session.add(org)
    db_session.commit()

    batch_date = datetime(2026, 9, 1, 18, 0, tzinfo=timezone.utc)     # Friday evening payout
    credit_date = datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc)    # Lands Monday morning (2 days later)

    # Batch with NO UTR
    batch = SettlementBatch(
        org_id=org.id,
        batch_id="batch_no_utr",
        gateway=GatewayEnum.RAZORPAY,
        settlement_date=batch_date,
        gross_amount=Decimal("30700.00"),
        net_amount=Decimal("30000.00"),
        utr_number=None,
    )
    credit = BankCredit(
        org_id=org.id,
        transaction_date=credit_date,
        narration="ACH CREDIT - RAZORPAY PAYOUT TO VENDOR",
        credit_amount=Decimal("30000.00"),
        reference_no=None,
    )
    db_session.add_all([batch, credit])
    db_session.commit()

    run = ReconciliationRun(org_id=org.id)
    db_session.add(run)
    db_session.commit()

    engine = Layer3MatchingEngine(ReconciliationRuleConfig(layer_3_bank_window_days=4))
    output = engine.execute(
        org_id=org.id,
        run_id=run.id,
        settlement_batches=[batch],
        bank_credits=[credit],
    )

    assert output.summary.matched_batches == 1
    assert output.summary.fuzzy_matches_count == 1
    assert batch.reconciliation_status == ReconciliationStatusEnum.MATCHED
    assert credit.reconciliation_status == ReconciliationStatusEnum.MATCHED

    match = output.matches[0]
    assert match.match_type == MatchTypeEnum.FUZZY
    assert match.status == MatchStatusEnum.MATCHED
    assert match.match_details["matched_by"] == "gateway_keyword_amount_date"
    assert match.match_details["date_diff_days"] == 2


def test_layer3_clearing_window_boundary_rejection(db_session):
    """
    Verify rejection when bank deposit occurred 7 days after payout (> 4 days clearing window).
    Expected: Batch remains UNMATCHED, Bank credit remains UNMATCHED.
    """
    org = Organisation(name="Boundary Org", slug="boundary-org")
    db_session.add(org)
    db_session.commit()

    batch_date = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    credit_date = datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc)  # 8 days later

    batch = SettlementBatch(
        org_id=org.id,
        batch_id="batch_boundary_01",
        gateway=GatewayEnum.RAZORPAY,
        settlement_date=batch_date,
        net_amount=Decimal("15000.00"),
        utr_number=None,
    )
    credit = BankCredit(
        org_id=org.id,
        transaction_date=credit_date,
        narration="NEFT-RAZORPAY",
        credit_amount=Decimal("15000.00"),
    )
    db_session.add_all([batch, credit])
    db_session.commit()

    run = ReconciliationRun(org_id=org.id)
    db_session.add(run)
    db_session.commit()

    engine = Layer3MatchingEngine(ReconciliationRuleConfig(layer_3_bank_window_days=4))
    output = engine.execute(
        org_id=org.id,
        run_id=run.id,
        settlement_batches=[batch],
        bank_credits=[credit],
    )

    assert output.summary.matched_batches == 0
    assert output.summary.unmatched_batches == 1
    assert output.summary.unmatched_bank_credits == 1
    assert batch.reconciliation_status == ReconciliationStatusEnum.UNMATCHED


def test_layer3_missing_cash_in_transit_alerting(db_session):
    """
    Verify that a settlement batch with no bank credit is identified as UNMATCHED (missing deposit).
    """
    org = Organisation(name="Missing Cash Org", slug="missing-cash-org")
    db_session.add(org)
    db_session.commit()

    now = datetime.now(timezone.utc)

    batch_missing = SettlementBatch(
        org_id=org.id,
        batch_id="batch_unrealized",
        gateway=GatewayEnum.STRIPE,
        settlement_date=now,
        net_amount=Decimal("95000.00"),
        utr_number="STRIPE_LOST_99",
    )
    db_session.add(batch_missing)
    db_session.commit()

    run = ReconciliationRun(org_id=org.id)
    db_session.add(run)
    db_session.commit()

    engine = Layer3MatchingEngine()
    output = engine.execute(
        org_id=org.id,
        run_id=run.id,
        settlement_batches=[batch_missing],
        bank_credits=[],  # No bank credits
    )

    assert output.summary.unmatched_batches == 1
    assert batch_missing.reconciliation_status == ReconciliationStatusEnum.UNMATCHED
    assert len(output.matches) == 0


def test_layer3_multi_tenant_isolation(db_session):
    """
    Verify multi-tenant isolation: Tenant Alpha's settlement batch is never matched
    against Tenant Beta's bank credit even with identical UTRs.
    """
    org_a = Organisation(name="Tenant A", slug="org-a-l3")
    org_b = Organisation(name="Tenant B", slug="org-b-l3")
    db_session.add_all([org_a, org_b])
    db_session.commit()

    now = datetime.now(timezone.utc)

    # Batch in Org A
    batch_a = SettlementBatch(
        org_id=org_a.id,
        batch_id="batch_a_01",
        gateway=GatewayEnum.RAZORPAY,
        settlement_date=now,
        net_amount=Decimal("40000.00"),
        utr_number="SHARED_UTR_99",
    )
    # Credit in Org B with same UTR
    credit_b = BankCredit(
        org_id=org_b.id,
        transaction_date=now,
        narration="NEFT-RAZORPAY-SHARED_UTR_99",
        credit_amount=Decimal("40000.00"),
        reference_no="SHARED_UTR_99",
    )
    db_session.add_all([batch_a, credit_b])
    db_session.commit()

    run_a = ReconciliationRun(org_id=org_a.id)
    db_session.add(run_a)
    db_session.commit()

    engine = Layer3MatchingEngine()
    output = engine.execute(
        org_id=org_a.id,
        run_id=run_a.id,
        settlement_batches=[batch_a],
        bank_credits=[credit_b],
    )

    assert output.summary.matched_batches == 0
    assert output.summary.unmatched_batches == 1
    assert batch_a.reconciliation_status == ReconciliationStatusEnum.UNMATCHED
    assert len(output.matches) == 0

