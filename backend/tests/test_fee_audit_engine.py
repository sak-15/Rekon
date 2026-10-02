import pytest
from decimal import Decimal
from datetime import datetime
from app.models.gateway import GatewayTransaction, GatewayEnum, PaymentMethodEnum, TxnStatusEnum
from app.models.rate_card import GatewayRateCard, RateTypeEnum
from app.models.organisation import Organisation
from app.services.fee_audit import (
    FeeAuditEngine,
    AuditStatusEnum,
    DisputeCategoryEnum,
)
from app.core.rate_cards import seed_default_rate_cards_for_org


def test_audit_single_transaction_exact_verified():
    """Domestic credit card with exact 2.0% MDR and exact 18% GST matches perfectly."""
    card = GatewayRateCard(
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.CARD,
        card_network="credit",
        is_international=False,
        rate_type=RateTypeEnum.PERCENTAGE,
        percentage_rate=Decimal("0.0200"),
        flat_fee=Decimal("0.00"),
        gst_rate=Decimal("0.1800"),
        is_active=True,
    )

    txn = GatewayTransaction(
        txn_id="pay_verified_01",
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.CARD,
        amount=Decimal("5000.00"),
        gateway_fee=Decimal("100.00"),      # 2% of 5,000
        gateway_fee_gst=Decimal("18.00"),  # 18% of 100
        net_amount=Decimal("4882.00"),
        captured_at=datetime.utcnow(),
    )

    item = FeeAuditEngine.audit_transaction(txn, [card])
    assert item.audit_status == AuditStatusEnum.VERIFIED
    assert item.dispute_category == DisputeCategoryEnum.NO_DISCREPANCY
    assert item.fee_variance == Decimal("0.00")
    assert item.gst_variance == Decimal("0.00")
    assert item.total_overcharge == Decimal("0.00")


def test_audit_single_transaction_missing_debit_cap_overcharge():
    """A ₹50,000 debit card where gateway charged 0.9% (₹450) ignoring ₹20 cap."""
    card = GatewayRateCard(
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.CARD,
        card_network="debit",
        is_international=False,
        rate_type=RateTypeEnum.PERCENTAGE,
        percentage_rate=Decimal("0.0090"),
        flat_fee=Decimal("0.00"),
        gst_rate=Decimal("0.1800"),
        cap_max_fee=Decimal("20.00"),  # RBI Cap
        is_active=True,
    )

    txn = GatewayTransaction(
        txn_id="pay_debit_overcharged",
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.CARD,
        amount=Decimal("50000.00"),
        gateway_fee=Decimal("450.00"),     # uncapped 0.90%
        gateway_fee_gst=Decimal("81.00"),  # 18% of 450
        net_amount=Decimal("49469.00"),
        captured_at=datetime.utcnow(),
    )

    item = FeeAuditEngine.audit_transaction(txn, [card])
    assert item.audit_status == AuditStatusEnum.OVERCHARGED
    assert item.dispute_category == DisputeCategoryEnum.MISSING_DEBIT_CAP
    assert item.expected_fee == Decimal("20.00")
    assert item.actual_fee == Decimal("450.00")
    assert item.fee_variance == Decimal("430.00")
    assert item.expected_gst == Decimal("3.60")
    assert item.actual_gst == Decimal("81.00")
    assert item.gst_variance == Decimal("77.40")
    assert item.total_overcharge == Decimal("507.40")
    assert "exceeded regulatory cap" in item.explanation


def test_audit_single_transaction_gst_miscalculation():
    """Gateway computed 18% GST wrongly (e.g. charged ₹35 instead of ₹18 on a ₹100 fee)."""
    card = GatewayRateCard(
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.CARD,
        card_network="credit",
        is_international=False,
        rate_type=RateTypeEnum.PERCENTAGE,
        percentage_rate=Decimal("0.0200"),
        flat_fee=Decimal("0.00"),
        gst_rate=Decimal("0.1800"),
        is_active=True,
    )

    txn = GatewayTransaction(
        txn_id="pay_gst_bad",
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.CARD,
        amount=Decimal("5000.00"),
        gateway_fee=Decimal("100.00"),     # fee is correct
        gateway_fee_gst=Decimal("35.00"), # GST is ₹17 too high!
        net_amount=Decimal("4865.00"),
        captured_at=datetime.utcnow(),
    )

    item = FeeAuditEngine.audit_transaction(txn, [card])
    assert item.audit_status == AuditStatusEnum.OVERCHARGED
    assert item.dispute_category == DisputeCategoryEnum.GST_MISCALCULATION
    assert item.fee_variance == Decimal("0.00")
    assert item.gst_variance == Decimal("17.00")
    assert item.total_overcharge == Decimal("17.00")


def test_audit_single_transaction_unauthorized_mdr_markup():
    """Gateway charged 2.5% MDR instead of agreed 2.0%."""
    card = GatewayRateCard(
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.CARD,
        card_network="credit",
        is_international=False,
        rate_type=RateTypeEnum.PERCENTAGE,
        percentage_rate=Decimal("0.0200"),
        flat_fee=Decimal("0.00"),
        gst_rate=Decimal("0.1800"),
        is_active=True,
    )

    # ₹10,000 txn: expected fee = ₹200 + ₹36 GST. Actual = ₹250 + ₹45 GST.
    txn = GatewayTransaction(
        txn_id="pay_markup_01",
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.CARD,
        amount=Decimal("10000.00"),
        gateway_fee=Decimal("250.00"),
        gateway_fee_gst=Decimal("45.00"),
        net_amount=Decimal("9705.00"),
        captured_at=datetime.utcnow(),
    )

    item = FeeAuditEngine.audit_transaction(txn, [card])
    assert item.audit_status == AuditStatusEnum.OVERCHARGED
    assert item.dispute_category == DisputeCategoryEnum.UNAUTHORIZED_MDR_MARKUP
    assert item.fee_variance == Decimal("50.00")
    assert item.gst_variance == Decimal("9.00")
    assert item.total_overcharge == Decimal("59.00")


def test_audit_gateway_transactions_and_csv_generation(db_session):
    """Test full org fee audit report aggregation and claim CSV export."""
    org = Organisation(name="Audit SaaS", slug="audit-saas")
    db_session.add(org)
    db_session.commit()

    # Seed default rate cards for org
    seed_default_rate_cards_for_org(db_session, org.id, gateway="razorpay")

    # Add 3 transactions:
    # 1. Verified UPI (0% MDR, 0 GST)
    t1 = GatewayTransaction(
        org_id=org.id,
        txn_id="pay_upi_001",
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.UPI,
        amount=Decimal("2000.00"),
        gateway_fee=Decimal("0.00"),
        gateway_fee_gst=Decimal("0.00"),
        net_amount=Decimal("2000.00"),
        captured_at=datetime(2026, 3, 1, 10, 0, 0),
        status=TxnStatusEnum.CAPTURED,
    )
    # 2. Overcharged Credit Card (charged ₹300 fee instead of ₹200 on ₹10,000)
    t2 = GatewayTransaction(
        org_id=org.id,
        txn_id="pay_card_002",
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.CARD,
        amount=Decimal("10000.00"),
        gateway_fee=Decimal("300.00"),     # Overcharged by ₹100
        gateway_fee_gst=Decimal("54.00"),  # GST overcharged by ₹18
        net_amount=Decimal("9646.00"),
        captured_at=datetime(2026, 3, 2, 11, 0, 0),
        status=TxnStatusEnum.CAPTURED,
    )
    # 3. Verified Credit Card
    t3 = GatewayTransaction(
        org_id=org.id,
        txn_id="pay_card_003",
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.CARD,
        amount=Decimal("5000.00"),
        gateway_fee=Decimal("100.00"),
        gateway_fee_gst=Decimal("18.00"),
        net_amount=Decimal("4882.00"),
        captured_at=datetime(2026, 3, 3, 12, 0, 0),
        status=TxnStatusEnum.CAPTURED,
    )
    db_session.add_all([t1, t2, t3])
    db_session.commit()

    report = FeeAuditEngine.audit_transactions(db_session, org.id, gateway="razorpay")

    assert report.total_audited == 3
    assert report.verified_count == 2
    assert report.overcharged_count == 1
    assert report.total_gross_volume == Decimal("17000.00")
    assert report.total_overcharged_amount == Decimal("118.00")  # ₹100 fee + ₹18 GST

    # Verify CSV generation
    csv_text = FeeAuditEngine.generate_dispute_claim_csv(report)
    assert "pay_card_002" in csv_text
    assert "pay_upi_001" not in csv_text  # Verified txns not included in dispute claim
    assert "118.00" in csv_text
    assert "unauthorized_mdr_markup" in csv_text


def test_fee_audit_multi_tenant_isolation(db_session):
    """Verify that auditing Org 1 only reads Org 1 txns and rate cards."""
    org1 = Organisation(name="Tenant A", slug="tenant-a")
    org2 = Organisation(name="Tenant B", slug="tenant-b")
    db_session.add_all([org1, org2])
    db_session.commit()

    seed_default_rate_cards_for_org(db_session, org1.id, gateway="razorpay")
    seed_default_rate_cards_for_org(db_session, org2.id, gateway="razorpay")

    t1 = GatewayTransaction(
        org_id=org1.id,
        txn_id="pay_t1_org1",
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.UPI,
        amount=Decimal("1000.00"),
        gateway_fee=Decimal("0.00"),
        gateway_fee_gst=Decimal("0.00"),
        net_amount=Decimal("1000.00"),
        captured_at=datetime.utcnow(),
    )
    t2 = GatewayTransaction(
        org_id=org2.id,
        txn_id="pay_t2_org2",
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.CARD,
        amount=Decimal("2000.00"),
        gateway_fee=Decimal("200.00"),  # Heavy markup on org2
        gateway_fee_gst=Decimal("36.00"),
        net_amount=Decimal("1764.00"),
        captured_at=datetime.utcnow(),
    )
    db_session.add_all([t1, t2])
    db_session.commit()

    report1 = FeeAuditEngine.audit_transactions(db_session, org1.id)
    report2 = FeeAuditEngine.audit_transactions(db_session, org2.id)

    assert report1.total_audited == 1
    assert report1.items[0].txn_id == "pay_t1_org1"
    assert report1.overcharged_count == 0

    assert report2.total_audited == 1
    assert report2.items[0].txn_id == "pay_t2_org2"
    assert report2.overcharged_count == 1

