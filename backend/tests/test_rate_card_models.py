import pytest
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from app.models.rate_card import GatewayRateCard, RateTypeEnum
from app.models.gateway import GatewayEnum, PaymentMethodEnum
from app.models.organisation import Organisation
from app.core.rate_cards import seed_default_rate_cards_for_org, get_default_benchmark_rates


def test_rate_card_fee_calculation_percentage():
    """Test 2% domestic credit card MDR calculation with 18% GST."""
    card = GatewayRateCard(
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.CARD,
        card_network="credit",
        is_international=False,
        rate_type=RateTypeEnum.PERCENTAGE,
        percentage_rate=Decimal("0.0200"),  # 2.00%
        flat_fee=Decimal("0.00"),
        gst_rate=Decimal("0.1800"),         # 18% GST
    )

    # ₹10,000 transaction
    res = card.calculate_expected_charges(Decimal("10000.00"))
    assert res["gross_amount"] == Decimal("10000.00")
    assert res["expected_fee"] == Decimal("200.00")      # 2% of 10,000
    assert res["expected_gst"] == Decimal("36.00")       # 18% of 200
    assert res["expected_total_deduction"] == Decimal("236.00")
    assert res["expected_net_amount"] == Decimal("9764.00")


def test_rate_card_fee_calculation_debit_cap():
    """Test RBI regulatory cap of ₹20 on debit cards even when 0.90% exceeds ₹20."""
    card = GatewayRateCard(
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.CARD,
        card_network="debit",
        is_international=False,
        rate_type=RateTypeEnum.PERCENTAGE,
        percentage_rate=Decimal("0.0090"),  # 0.90%
        flat_fee=Decimal("0.00"),
        gst_rate=Decimal("0.1800"),
        cap_max_fee=Decimal("20.00"),       # ₹20 max cap
    )

    # ₹50,000 debit transaction (0.90% is ₹450, should be clamped to ₹20)
    res = card.calculate_expected_charges(Decimal("50000.00"))
    assert res["expected_fee"] == Decimal("20.00")
    assert res["expected_gst"] == Decimal("3.60")        # 18% of ₹20
    assert res["expected_total_deduction"] == Decimal("23.60")
    assert res["expected_net_amount"] == Decimal("49976.40")

    # Small ₹1,000 debit transaction (0.90% is ₹9, below ₹20 cap)
    res_small = card.calculate_expected_charges(Decimal("1000.00"))
    assert res_small["expected_fee"] == Decimal("9.00")
    assert res_small["expected_gst"] == Decimal("1.62")  # 18% of ₹9
    assert res_small["expected_total_deduction"] == Decimal("10.62")
    assert res_small["expected_net_amount"] == Decimal("989.38")


def test_rate_card_fee_calculation_flat_fee():
    """Test eNACH recurring mandate flat fee of ₹5.00."""
    card = GatewayRateCard(
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.ENACH,
        card_network="all",
        is_international=False,
        rate_type=RateTypeEnum.FLAT,
        percentage_rate=Decimal("0.0000"),
        flat_fee=Decimal("5.00"),
        gst_rate=Decimal("0.1800"),
    )

    res = card.calculate_expected_charges(Decimal("1500.00"))
    assert res["expected_fee"] == Decimal("5.00")
    assert res["expected_gst"] == Decimal("0.90")
    assert res["expected_total_deduction"] == Decimal("5.90")
    assert res["expected_net_amount"] == Decimal("1494.10")


def test_rate_card_fee_calculation_upi_zero_mdr():
    """Test NPCI mandated zero MDR for UPI."""
    card = GatewayRateCard(
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.UPI,
        card_network="all",
        is_international=False,
        rate_type=RateTypeEnum.PERCENTAGE,
        percentage_rate=Decimal("0.0000"),
        flat_fee=Decimal("0.00"),
        gst_rate=Decimal("0.1800"),
    )

    res = card.calculate_expected_charges(Decimal("7500.00"))
    assert res["expected_fee"] == Decimal("0.00")
    assert res["expected_gst"] == Decimal("0.00")
    assert res["expected_total_deduction"] == Decimal("0.00")
    assert res["expected_net_amount"] == Decimal("7500.00")


def test_rate_card_fee_calculation_hybrid():
    """Test hybrid rate (e.g. 2% + ₹3.00 flat fee)."""
    card = GatewayRateCard(
        gateway=GatewayEnum.STRIPE,
        payment_method=PaymentMethodEnum.CARD,
        card_network="all",
        is_international=True,
        rate_type=RateTypeEnum.HYBRID,
        percentage_rate=Decimal("0.0200"),
        flat_fee=Decimal("3.00"),
        gst_rate=Decimal("0.1800"),
    )

    # ₹2,000 transaction: fee = 2% of 2000 (₹40) + ₹3 = ₹43.00
    res = card.calculate_expected_charges(Decimal("2000.00"))
    assert res["expected_fee"] == Decimal("43.00")
    assert res["expected_gst"] == Decimal("7.74")  # 18% of 43
    assert res["expected_total_deduction"] == Decimal("50.74")
    assert res["expected_net_amount"] == Decimal("1949.26")


def test_seed_default_rate_cards_idempotency_and_multi_tenant(db_session):
    """Verify seeding default benchmark rate cards is idempotent and tenant-isolated."""
    org1 = Organisation(name="SaaS Alpha", slug="saas-alpha")
    org2 = Organisation(name="SaaS Beta", slug="saas-beta")
    db_session.add_all([org1, org2])
    db_session.commit()

    # Seed for org1
    cards_org1 = seed_default_rate_cards_for_org(db_session, org1.id, gateway="razorpay")
    assert len(cards_org1) == 7

    # Seed again - should be idempotent, return same 7
    cards_org1_again = seed_default_rate_cards_for_org(db_session, org1.id, gateway="razorpay")
    assert len(cards_org1_again) == 7

    # Seed for org2
    cards_org2 = seed_default_rate_cards_for_org(db_session, org2.id, gateway="razorpay")
    assert len(cards_org2) == 7

    # Ensure total in DB is 14 (7 per org)
    total_cards = db_session.query(GatewayRateCard).count()
    assert total_cards == 14

    # Org1 customizing their credit card rate to 1.80% does not touch Org2
    org1_credit_card = (
        db_session.query(GatewayRateCard)
        .filter(
            GatewayRateCard.org_id == org1.id,
            GatewayRateCard.payment_method == PaymentMethodEnum.CARD,
            GatewayRateCard.card_network == "credit",
        )
        .first()
    )
    org1_credit_card.percentage_rate = Decimal("0.0180")
    db_session.commit()

    # Org2 remains untouched at 2.00%
    org2_credit_card = (
        db_session.query(GatewayRateCard)
        .filter(
            GatewayRateCard.org_id == org2.id,
            GatewayRateCard.payment_method == PaymentMethodEnum.CARD,
            GatewayRateCard.card_network == "credit",
        )
        .first()
    )
    assert org2_credit_card.percentage_rate == Decimal("0.0200")
    assert org1_credit_card.percentage_rate == Decimal("0.0180")


def test_unique_constraint_on_rate_card(db_session):
    """Verify unique constraint prevents duplicate active rules for the same payment rail."""
    org = Organisation(name="Unique Org", slug="unique-org")
    db_session.add(org)
    db_session.commit()

    card1 = GatewayRateCard(
        org_id=org.id,
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.UPI,
        card_network="all",
        is_international=False,
        rate_type=RateTypeEnum.PERCENTAGE,
        percentage_rate=Decimal("0.0000"),
        flat_fee=Decimal("0.00"),
        gst_rate=Decimal("0.1800"),
        is_active=True,
    )
    db_session.add(card1)
    db_session.commit()

    card2 = GatewayRateCard(
        org_id=org.id,
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.UPI,
        card_network="all",
        is_international=False,
        rate_type=RateTypeEnum.PERCENTAGE,
        percentage_rate=Decimal("0.0050"),  # conflicting rule
        flat_fee=Decimal("0.00"),
        gst_rate=Decimal("0.1800"),
        is_active=True,
    )
    db_session.add(card2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

