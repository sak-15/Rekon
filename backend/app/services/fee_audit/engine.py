import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.gateway import GatewayTransaction, GatewayEnum, PaymentMethodEnum
from app.models.rate_card import GatewayRateCard, RateTypeEnum
from app.core.rate_cards import get_default_benchmark_rates


class AuditStatusEnum(str, Enum):
    VERIFIED = "verified"
    OVERCHARGED = "overcharged"
    UNDERCHARGED = "undercharged"


class DisputeCategoryEnum(str, Enum):
    NO_DISCREPANCY = "no_discrepancy"
    MISSING_DEBIT_CAP = "missing_debit_cap"
    GST_MISCALCULATION = "gst_miscalculation"
    FLAT_FEE_OVERCHARGE = "flat_fee_overcharge"
    UNAUTHORIZED_MDR_MARKUP = "unauthorized_mdr_markup"
    GATEWAY_DISCOUNT = "gateway_discount"


@dataclass
class AuditedTransaction:
    txn_id: str
    gateway: str
    payment_method: str
    card_network: str
    is_international: bool
    captured_at: Optional[datetime]
    gross_amount: Decimal
    actual_fee: Decimal
    actual_gst: Decimal
    actual_total_deduction: Decimal
    expected_fee: Decimal
    expected_gst: Decimal
    expected_total_deduction: Decimal
    fee_variance: Decimal       # actual_fee - expected_fee
    gst_variance: Decimal       # actual_gst - expected_gst
    total_overcharge: Decimal   # fee_variance + gst_variance (positive = overcharge)
    audit_status: AuditStatusEnum
    dispute_category: DisputeCategoryEnum
    explanation: str
    rate_card_applied: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "txn_id": self.txn_id,
            "gateway": self.gateway,
            "payment_method": self.payment_method,
            "card_network": self.card_network,
            "is_international": self.is_international,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "gross_amount": float(self.gross_amount),
            "actual_fee": float(self.actual_fee),
            "actual_gst": float(self.actual_gst),
            "actual_total_deduction": float(self.actual_total_deduction),
            "expected_fee": float(self.expected_fee),
            "expected_gst": float(self.expected_gst),
            "expected_total_deduction": float(self.expected_total_deduction),
            "fee_variance": float(self.fee_variance),
            "gst_variance": float(self.gst_variance),
            "total_overcharge": float(self.total_overcharge),
            "audit_status": self.audit_status.value,
            "dispute_category": self.dispute_category.value,
            "explanation": self.explanation,
            "rate_card_applied": self.rate_card_applied,
        }


@dataclass
class FeeAuditReport:
    total_audited: int
    total_gross_volume: Decimal
    total_actual_fees: Decimal
    total_expected_fees: Decimal
    total_actual_gst: Decimal
    total_expected_gst: Decimal
    total_overcharged_amount: Decimal  # Recoverable overcharge from overcharged transactions
    total_undercharged_amount: Decimal
    net_variance: Decimal              # Total actual deduction - total expected deduction
    verified_count: int
    overcharged_count: int
    undercharged_count: int
    discrepancies_by_category: Dict[str, Dict[str, Any]]
    items: List[AuditedTransaction] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_audited": self.total_audited,
            "total_gross_volume": float(self.total_gross_volume),
            "total_actual_fees": float(self.total_actual_fees),
            "total_expected_fees": float(self.total_expected_fees),
            "total_actual_gst": float(self.total_actual_gst),
            "total_expected_gst": float(self.total_expected_gst),
            "total_overcharged_amount": float(self.total_overcharged_amount),
            "total_undercharged_amount": float(self.total_undercharged_amount),
            "net_variance": float(self.net_variance),
            "verified_count": self.verified_count,
            "overcharged_count": self.overcharged_count,
            "undercharged_count": self.undercharged_count,
            "discrepancies_by_category": self.discrepancies_by_category,
            "items": [item.to_dict() for item in self.items],
        }


class FeeAuditEngine:
    """
    Mathematical MDR & 18% GST Fee Audit Engine.
    Verifies every gateway fee down to the exact paisa against agreed rate cards.
    """

    TOLERANCE = Decimal("0.02")  # 2 paisa rounding tolerance

    @staticmethod
    def find_matching_rate_card(
        rate_cards: List[GatewayRateCard],
        gateway: GatewayEnum,
        payment_method: PaymentMethodEnum,
        card_network: str = "all",
        is_international: bool = False,
    ) -> Optional[GatewayRateCard]:
        """
        Finds best matching active rate card using prioritized matching:
        1. Exact match (gateway, payment_method, card_network, is_international)
        2. Network wildcard match (gateway, payment_method, 'all', is_international)
        3. International fallback (gateway, payment_method, card_network, False)
        """
        # 1. Exact match
        for card in rate_cards:
            if (
                card.is_active
                and card.gateway == gateway
                and card.payment_method == payment_method
                and card.card_network.lower() == card_network.lower()
                and card.is_international == is_international
            ):
                return card

        # 2. Wildcard card_network="all"
        for card in rate_cards:
            if (
                card.is_active
                and card.gateway == gateway
                and card.payment_method == payment_method
                and card.card_network.lower() == "all"
                and card.is_international == is_international
            ):
                return card

        # 3. Default card_network="all" domestic fallback if not international
        for card in rate_cards:
            if (
                card.is_active
                and card.gateway == gateway
                and card.payment_method == payment_method
            ):
                return card

        return None

    @classmethod
    def audit_transaction(
        cls,
        txn: GatewayTransaction,
        rate_cards: List[GatewayRateCard],
    ) -> AuditedTransaction:
        """
        Audits a single gateway transaction against the applicable rate card.
        """
        gross = Decimal(str(txn.amount))
        actual_fee = Decimal(str(txn.gateway_fee or 0.00)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        actual_gst = Decimal(str(txn.gateway_fee_gst or 0.00)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        actual_total = actual_fee + actual_gst

        # Determine card network / rail from metadata if available, else default to 'all'
        card_network = "credit" if txn.payment_method == PaymentMethodEnum.CARD else "all"
        is_intl = False

        card = cls.find_matching_rate_card(
            rate_cards=rate_cards,
            gateway=txn.gateway,
            payment_method=txn.payment_method,
            card_network=card_network,
            is_international=is_intl,
        )

        rate_card_desc = None
        if card:
            charges = card.calculate_expected_charges(gross)
            expected_fee = charges["expected_fee"]
            expected_gst = charges["expected_gst"]
            expected_total = charges["expected_total_deduction"]
            rate_card_desc = f"{card.rate_type.value}: {card.percentage_rate * 100}% + ₹{card.flat_fee} (+{card.gst_rate * 100}% GST)"
        else:
            # Fallback to zero if absolutely no rate card found
            expected_fee = Decimal("0.00")
            expected_gst = Decimal("0.00")
            expected_total = Decimal("0.00")
            rate_card_desc = "None (No matching rate card)"

        fee_var = actual_fee - expected_fee
        gst_var = actual_gst - expected_gst
        total_overcharge = fee_var + gst_var

        # Determine audit status
        if total_overcharge > cls.TOLERANCE:
            status = AuditStatusEnum.OVERCHARGED
        elif total_overcharge < -cls.TOLERANCE:
            status = AuditStatusEnum.UNDERCHARGED
        else:
            status = AuditStatusEnum.VERIFIED

        # Root-cause classification
        category = DisputeCategoryEnum.NO_DISCREPANCY
        explanation = "Charges perfectly verified to agreed rate card."

        if status == AuditStatusEnum.OVERCHARGED:
            if card and card.cap_max_fee is not None and actual_fee > Decimal(str(card.cap_max_fee)):
                category = DisputeCategoryEnum.MISSING_DEBIT_CAP
                explanation = f"MDR of ₹{actual_fee} exceeded regulatory cap of ₹{card.cap_max_fee} by ₹{actual_fee - Decimal(str(card.cap_max_fee))}."
            elif card and card.rate_type == RateTypeEnum.FLAT and fee_var > cls.TOLERANCE:
                category = DisputeCategoryEnum.FLAT_FEE_OVERCHARGE
                explanation = f"Flat fee of ₹{actual_fee} exceeded agreed ₹{card.flat_fee} by ₹{fee_var}."
            elif abs(fee_var) <= cls.TOLERANCE and gst_var > cls.TOLERANCE:
                category = DisputeCategoryEnum.GST_MISCALCULATION
                explanation = f"GST of ₹{actual_gst} exceeded statutory 18% GST (₹{expected_gst}) by ₹{gst_var}."
            else:
                category = DisputeCategoryEnum.UNAUTHORIZED_MDR_MARKUP
                explanation = f"Gateway MDR markup exceeded contracted rate by ₹{fee_var} + GST delta ₹{gst_var}."
        elif status == AuditStatusEnum.UNDERCHARGED:
            category = DisputeCategoryEnum.GATEWAY_DISCOUNT
            explanation = f"Gateway deducted ₹{abs(total_overcharge)} less than contracted rates."

        return AuditedTransaction(
            txn_id=txn.txn_id,
            gateway=txn.gateway.value if hasattr(txn.gateway, "value") else str(txn.gateway),
            payment_method=txn.payment_method.value if hasattr(txn.payment_method, "value") else str(txn.payment_method),
            card_network=card_network,
            is_international=is_intl,
            captured_at=txn.captured_at,
            gross_amount=gross,
            actual_fee=actual_fee,
            actual_gst=actual_gst,
            actual_total_deduction=actual_total,
            expected_fee=expected_fee,
            expected_gst=expected_gst,
            expected_total_deduction=expected_total,
            fee_variance=fee_var,
            gst_variance=gst_var,
            total_overcharge=total_overcharge,
            audit_status=status,
            dispute_category=category,
            explanation=explanation,
            rate_card_applied=rate_card_desc,
        )

    @classmethod
    def audit_transactions(
        cls,
        db: Session,
        org_id: str,
        gateway: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> FeeAuditReport:
        """
        Runs comprehensive fee audit across all transactions for an organisation.
        """
        # Load active rate cards for tenant
        rate_cards_query = db.query(GatewayRateCard).filter(
            GatewayRateCard.org_id == org_id,
            GatewayRateCard.is_active == True,
        )
        if gateway:
            rate_cards_query = rate_cards_query.filter(GatewayRateCard.gateway == GatewayEnum(gateway.lower()))
        rate_cards = rate_cards_query.all()

        # Query transactions
        txn_query = db.query(GatewayTransaction).filter(
            GatewayTransaction.org_id == org_id,
        )
        if gateway:
            txn_query = txn_query.filter(GatewayTransaction.gateway == GatewayEnum(gateway.lower()))
        if start_date:
            txn_query = txn_query.filter(GatewayTransaction.captured_at >= start_date)
        if end_date:
            txn_query = txn_query.filter(GatewayTransaction.captured_at <= end_date)

        txns = txn_query.order_by(GatewayTransaction.captured_at.desc()).all()

        audited_items: List[AuditedTransaction] = []
        total_gross = Decimal("0.00")
        total_act_fee = Decimal("0.00")
        total_exp_fee = Decimal("0.00")
        total_act_gst = Decimal("0.00")
        total_exp_gst = Decimal("0.00")
        total_overcharge = Decimal("0.00")
        total_undercharge = Decimal("0.00")

        verified_cnt = 0
        overcharged_cnt = 0
        undercharged_cnt = 0

        categories: Dict[str, Dict[str, Any]] = {
            DisputeCategoryEnum.NO_DISCREPANCY.value: {"count": 0, "amount": Decimal("0.00")},
            DisputeCategoryEnum.MISSING_DEBIT_CAP.value: {"count": 0, "amount": Decimal("0.00")},
            DisputeCategoryEnum.GST_MISCALCULATION.value: {"count": 0, "amount": Decimal("0.00")},
            DisputeCategoryEnum.FLAT_FEE_OVERCHARGE.value: {"count": 0, "amount": Decimal("0.00")},
            DisputeCategoryEnum.UNAUTHORIZED_MDR_MARKUP.value: {"count": 0, "amount": Decimal("0.00")},
            DisputeCategoryEnum.GATEWAY_DISCOUNT.value: {"count": 0, "amount": Decimal("0.00")},
        }

        for txn in txns:
            item = cls.audit_transaction(txn, rate_cards)
            audited_items.append(item)

            total_gross += item.gross_amount
            total_act_fee += item.actual_fee
            total_exp_fee += item.expected_fee
            total_act_gst += item.actual_gst
            total_exp_gst += item.expected_gst

            if item.audit_status == AuditStatusEnum.OVERCHARGED:
                overcharged_cnt += 1
                total_overcharge += item.total_overcharge
                categories[item.dispute_category.value]["count"] += 1
                categories[item.dispute_category.value]["amount"] += item.total_overcharge
            elif item.audit_status == AuditStatusEnum.UNDERCHARGED:
                undercharged_cnt += 1
                total_undercharge += abs(item.total_overcharge)
                categories[item.dispute_category.value]["count"] += 1
                categories[item.dispute_category.value]["amount"] += abs(item.total_overcharge)
            else:
                verified_cnt += 1
                categories[DisputeCategoryEnum.NO_DISCREPANCY.value]["count"] += 1

        # Format categories amounts to float for serialization
        formatted_categories = {
            k: {"count": v["count"], "amount": float(v["amount"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))}
            for k, v in categories.items()
        }

        return FeeAuditReport(
            total_audited=len(txns),
            total_gross_volume=total_gross.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            total_actual_fees=total_act_fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            total_expected_fees=total_exp_fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            total_actual_gst=total_act_gst.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            total_expected_gst=total_exp_gst.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            total_overcharged_amount=total_overcharge.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            total_undercharged_amount=total_undercharge.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            net_variance=(total_act_fee + total_act_gst - total_exp_fee - total_exp_gst).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            verified_count=verified_cnt,
            overcharged_count=overcharged_cnt,
            undercharged_count=undercharged_cnt,
            discrepancies_by_category=formatted_categories,
            items=audited_items,
        )

    @staticmethod
    def generate_dispute_claim_csv(report: FeeAuditReport) -> str:
        """
        Generates a standard CSV dispute claim sheet ready to submit to Gateway Merchant Support.
        Only includes OVERCHARGED transactions with clear audit reasoning.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        writer.writerow([
            "Transaction ID",
            "Gateway",
            "Payment Method",
            "Captured At",
            "Gross Amount (INR)",
            "Contracted Fee (INR)",
            "Actual Fee Deducted (INR)",
            "Fee Variance (INR)",
            "Statutory 18% GST (INR)",
            "Actual GST Deducted (INR)",
            "GST Variance (INR)",
            "Total Overcharge Claim (INR)",
            "Dispute Category",
            "Audit Explanation",
        ])

        for item in report.items:
            if item.audit_status == AuditStatusEnum.OVERCHARGED:
                writer.writerow([
                    item.txn_id,
                    item.gateway.upper(),
                    item.payment_method.upper(),
                    item.captured_at.strftime("%Y-%m-%d %H:%M:%S") if item.captured_at else "N/A",
                    f"{item.gross_amount:.2f}",
                    f"{item.expected_fee:.2f}",
                    f"{item.actual_fee:.2f}",
                    f"{item.fee_variance:.2f}",
                    f"{item.expected_gst:.2f}",
                    f"{item.actual_gst:.2f}",
                    f"{item.gst_variance:.2f}",
                    f"{item.total_overcharge:.2f}",
                    item.dispute_category.value,
                    item.explanation,
                ])

        return output.getvalue()

