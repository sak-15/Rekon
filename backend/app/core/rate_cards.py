"""
Commercial Gateway Fee Benchmark Rate Cards.
Central repository for standard Indian payment gateway pricing and benchmark rate cards.
Provides standard defaults that can be seeded for any tenant and easily modified per commercial contract.
"""

from typing import List, Dict, Any
from decimal import Decimal

# Standard Indian payment gateway MDR benchmarks
# Percentages are stored as decimals (e.g., 0.0200 = 2.00%, 0.0090 = 0.90%)
DEFAULT_BENCHMARK_RATE_CARDS: Dict[str, List[Dict[str, Any]]] = {
    "razorpay": [
        {
            "payment_method": "upi",
            "card_network": "all",
            "is_international": False,
            "rate_type": "percentage",
            "percentage_rate": Decimal("0.0000"),  # 0% MDR mandated by NPCI/Govt for UPI P2M
            "flat_fee": Decimal("0.00"),
            "gst_rate": Decimal("0.1800"),         # 18% GST
            "cap_min_fee": None,
            "cap_max_fee": None,
            "notes": "Standard NPCI Zero-MDR mandate for domestic UPI",
        },
        {
            "payment_method": "card",
            "card_network": "debit",
            "is_international": False,
            "rate_type": "percentage",
            "percentage_rate": Decimal("0.0090"),  # 0.90% standard domestic debit
            "flat_fee": Decimal("0.00"),
            "gst_rate": Decimal("0.1800"),
            "cap_min_fee": None,
            "cap_max_fee": Decimal("20.00"),       # RBI regulatory cap: max ₹20 fee on debit cards
            "notes": "Domestic Debit Card (0.90% with RBI ₹20 max cap)",
        },
        {
            "payment_method": "card",
            "card_network": "credit",
            "is_international": False,
            "rate_type": "percentage",
            "percentage_rate": Decimal("0.0200"),  # 2.00% domestic credit card
            "flat_fee": Decimal("0.00"),
            "gst_rate": Decimal("0.1800"),
            "cap_min_fee": None,
            "cap_max_fee": None,
            "notes": "Standard Domestic Credit Card (Visa / Mastercard / RuPay)",
        },
        {
            "payment_method": "card",
            "card_network": "amex",
            "is_international": False,
            "rate_type": "percentage",
            "percentage_rate": Decimal("0.0300"),  # 3.00% corporate/Amex cards
            "flat_fee": Decimal("0.00"),
            "gst_rate": Decimal("0.1800"),
            "cap_min_fee": None,
            "cap_max_fee": None,
            "notes": "Corporate & American Express cards",
        },
        {
            "payment_method": "card",
            "card_network": "all",
            "is_international": True,
            "rate_type": "percentage",
            "percentage_rate": Decimal("0.0300"),  # 3.00% international cards
            "flat_fee": Decimal("0.00"),
            "gst_rate": Decimal("0.1800"),
            "cap_min_fee": None,
            "cap_max_fee": None,
            "notes": "International cross-border cards (non-INR)",
        },
        {
            "payment_method": "enach",
            "card_network": "all",
            "is_international": False,
            "rate_type": "flat",
            "percentage_rate": Decimal("0.0000"),
            "flat_fee": Decimal("5.00"),           # ₹5.00 flat fee per mandate debit
            "gst_rate": Decimal("0.1800"),
            "cap_min_fee": None,
            "cap_max_fee": None,
            "notes": "NPCI eNACH recurring subscription auto-debit",
        },
        {
            "payment_method": "netbanking",
            "card_network": "all",
            "is_international": False,
            "rate_type": "flat",
            "percentage_rate": Decimal("0.0000"),
            "flat_fee": Decimal("10.00"),          # Flat ₹10 per netbanking txn
            "gst_rate": Decimal("0.1800"),
            "cap_min_fee": None,
            "cap_max_fee": None,
            "notes": "Domestic retail Netbanking checkout",
        },
    ],
    "stripe": [
        {
            "payment_method": "card",
            "card_network": "all",
            "is_international": False,
            "rate_type": "percentage",
            "percentage_rate": Decimal("0.0200"),  # 2.00% Stripe India domestic
            "flat_fee": Decimal("0.00"),
            "gst_rate": Decimal("0.1800"),
            "cap_min_fee": None,
            "cap_max_fee": None,
            "notes": "Stripe India domestic card processing",
        },
        {
            "payment_method": "card",
            "card_network": "all",
            "is_international": True,
            "rate_type": "percentage",
            "percentage_rate": Decimal("0.0300"),  # 3.00% Stripe international
            "flat_fee": Decimal("0.00"),
            "gst_rate": Decimal("0.1800"),
            "cap_min_fee": None,
            "cap_max_fee": None,
            "notes": "Stripe cross-border international cards",
        },
    ],
}


def get_default_benchmark_rates(gateway: str) -> List[Dict[str, Any]]:
    """
    Returns default rate card rules for a given payment gateway.
    """
    gw = gateway.lower().strip()
    return DEFAULT_BENCHMARK_RATE_CARDS.get(gw, DEFAULT_BENCHMARK_RATE_CARDS["razorpay"])


def seed_default_rate_cards_for_org(
    db: Any,
    org_id: str,
    gateway: str = "razorpay",
) -> List[Any]:
    """
    Seeds default benchmark rate cards for a given organisation and gateway.
    Idempotent: skips rules that already exist.
    """
    from app.models.rate_card import GatewayRateCard, RateTypeEnum
    from app.models.gateway import GatewayEnum, PaymentMethodEnum

    gw_str = gateway.lower().strip()
    gw_enum = GatewayEnum(gw_str)
    benchmarks = get_default_benchmark_rates(gw_str)

    created_cards = []
    for rule in benchmarks:
        pm_enum = PaymentMethodEnum(rule["payment_method"])
        rt_enum = RateTypeEnum(rule["rate_type"])

        # Check existing active card
        existing = (
            db.query(GatewayRateCard)
            .filter(
                GatewayRateCard.org_id == org_id,
                GatewayRateCard.gateway == gw_enum,
                GatewayRateCard.payment_method == pm_enum,
                GatewayRateCard.card_network == rule["card_network"],
                GatewayRateCard.is_international == rule["is_international"],
                GatewayRateCard.is_active == True,
            )
            .first()
        )

        if not existing:
            card = GatewayRateCard(
                org_id=org_id,
                gateway=gw_enum,
                payment_method=pm_enum,
                card_network=rule["card_network"],
                is_international=rule["is_international"],
                rate_type=rt_enum,
                percentage_rate=rule["percentage_rate"],
                flat_fee=rule["flat_fee"],
                gst_rate=rule["gst_rate"],
                cap_min_fee=rule["cap_min_fee"],
                cap_max_fee=rule["cap_max_fee"],
                notes=rule.get("notes"),
                is_active=True,
            )
            db.add(card)
            created_cards.append(card)

    if created_cards:
        db.commit()
        for c in created_cards:
            db.refresh(c)

    # Return all active rate cards for this org and gateway
    return (
        db.query(GatewayRateCard)
        .filter(
            GatewayRateCard.org_id == org_id,
            GatewayRateCard.gateway == gw_enum,
            GatewayRateCard.is_active == True,
        )
        .all()
    )
