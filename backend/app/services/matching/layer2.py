"""
Layer 2 Reconciliation Matching Engine.
Matches Gateway Transactions (Razorpay, Stripe) with Settlement Batch Lines.

Supports:
1. Deterministic transaction reference matching (txn_id == settlement_line.txn_ref).
2. Mathematical verification of fee deductions:
   Net Payout = Gross Amount - MDR Fee - 18% GST.
3. Overcharge and fee discrepancy audit detection.
4. Automatic identification and tracking of unsettled (in-flight) transactions.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional, Set, Dict

from app.models.gateway import GatewayTransaction, TxnStatusEnum, SettlementStatusEnum
from app.models.settlement import SettlementLine
from app.models.reconciliation import (
    ReconciliationMatch,
    ReconciliationLayerEnum,
    MatchTypeEnum,
    MatchStatusEnum,
)
from app.schemas.reconciliation import (
    ReconciliationRuleConfig,
    Layer2MatchSummary,
)


@dataclass
class Layer2MatchOutput:
    """
    Result container returned by the Layer 2 Matching Engine.
    """
    matches: List[ReconciliationMatch] = field(default_factory=list)
    summary: Layer2MatchSummary = field(default_factory=Layer2MatchSummary)
    settled_txns: List[GatewayTransaction] = field(default_factory=list)
    unsettled_txns: List[GatewayTransaction] = field(default_factory=list)
    fee_discrepancy_txns: List[GatewayTransaction] = field(default_factory=list)
    matched_lines: List[SettlementLine] = field(default_factory=list)
    unmatched_lines: List[SettlementLine] = field(default_factory=list)


class Layer2MatchingEngine:
    """
    Core matching engine executing Layer 2 reconciliation between Gateway Transactions and Settlement Lines.
    """

    def __init__(self, config: Optional[ReconciliationRuleConfig] = None):
        self.config = config or ReconciliationRuleConfig()

    def execute(
        self,
        org_id: str,
        run_id: str,
        gateway_txns: List[GatewayTransaction],
        settlement_lines: List[SettlementLine],
    ) -> Layer2MatchOutput:
        """
        Execute Layer 2 matching algorithm.

        :param org_id: Organisation UUID ensuring multi-tenant isolation.
        :param run_id: ReconciliationRun UUID linking generated audit matches.
        :param gateway_txns: List of gateway transactions to evaluate.
        :param settlement_lines: List of settlement lines to match against.
        :return: Layer2MatchOutput containing matches, summary metrics, and categorized entities.
        """
        # 1. Multi-tenant filtering
        tenant_txns = [
            txn for txn in gateway_txns
            if str(txn.org_id) == str(org_id) and txn.status == TxnStatusEnum.CAPTURED
        ]
        tenant_lines = [
            line for line in settlement_lines
            if str(line.org_id) == str(org_id)
        ]

        matched_txn_ids: Set[str] = set()
        matched_line_ids: Set[str] = set()
        generated_matches: List[ReconciliationMatch] = []

        settled_txns_list: List[GatewayTransaction] = []
        fee_discrepancy_txns_list: List[GatewayTransaction] = []
        matched_lines_list: List[SettlementLine] = []

        total_settled_gross = Decimal("0.00")
        total_settled_net = Decimal("0.00")
        total_fees = Decimal("0.00")
        total_gst = Decimal("0.00")
        total_fee_discrepancy_amount = Decimal("0.00")

        # 2. Index settlement lines by normalized txn_ref
        lines_by_ref: Dict[str, List[SettlementLine]] = defaultdict(list)
        for line in tenant_lines:
            if line.txn_ref:
                normalized_ref = line.txn_ref.strip().upper()
                lines_by_ref[normalized_ref].append(line)

        # 3. Match each captured transaction against settlement lines
        for txn in tenant_txns:
            if txn.id in matched_txn_ids:
                continue

            normalized_txn_id = txn.txn_id.strip().upper()
            candidates = lines_by_ref.get(normalized_txn_id, [])

            # Find first available unused line
            best_line: Optional[SettlementLine] = None
            for candidate in candidates:
                if candidate.id not in matched_line_ids:
                    best_line = candidate
                    break

            if best_line is not None:
                txn_amount = Decimal(str(txn.amount))
                line_amount = Decimal(str(best_line.amount))
                gross_diff = abs(txn_amount - line_amount)

                # Settlement line net calculation: Gross - Fee - Tax
                line_fee = Decimal(str(best_line.fee))
                line_tax = Decimal(str(best_line.tax))
                line_net = line_amount - line_fee - line_tax

                txn_fee = Decimal(str(txn.gateway_fee))
                txn_gst = Decimal(str(txn.gateway_fee_gst))
                txn_net = Decimal(str(txn.net_amount))

                fee_diff = abs(txn_fee - line_fee)
                gst_diff = abs(txn_gst - line_tax)
                total_deduction_diff = abs((txn_fee + txn_gst) - (line_fee + line_tax))
                net_diff = abs(txn_net - line_net)

                # Check if gross matches within tolerance
                if gross_diff <= self.config.amount_tolerance:
                    # Check if fee deductions match within tolerance
                    if total_deduction_diff <= self.config.amount_tolerance:
                        # Clean match
                        is_exact_zero = (gross_diff == Decimal("0.00") and total_deduction_diff == Decimal("0.00"))
                        confidence = Decimal("100.00") if is_exact_zero else Decimal("95.00")
                        status = MatchStatusEnum.MATCHED
                    else:
                        # Fee discrepancy detected (gateway deducted a different MDR or tax)
                        confidence = Decimal("85.00")
                        status = MatchStatusEnum.DISCREPANCY
                        total_fee_discrepancy_amount += total_deduction_diff
                        fee_discrepancy_txns_list.append(txn)

                    # Update transaction settlement status
                    txn.settlement_status = SettlementStatusEnum.SETTLED
                    settled_txns_list.append(txn)
                    matched_lines_list.append(best_line)

                    total_settled_gross += txn_amount
                    total_settled_net += line_net
                    total_fees += line_fee
                    total_gst += line_tax

                    line_type_str = (
                        best_line.line_type.value
                        if hasattr(best_line.line_type, "value")
                        else str(best_line.line_type)
                    )

                    match_record = ReconciliationMatch(
                        org_id=org_id,
                        run_id=run_id,
                        layer=ReconciliationLayerEnum.LAYER_2,
                        gateway_txn_id=txn.id,
                        settlement_line_id=best_line.id,
                        settlement_batch_id=best_line.batch_id,
                        match_type=MatchTypeEnum.EXACT,
                        confidence_score=confidence,
                        status=status,
                        amount_difference=gross_diff,
                        match_details={
                            "matched_by": "txn_id == txn_ref",
                            "txn_id": txn.txn_id,
                            "txn_ref": best_line.txn_ref,
                            "line_type": line_type_str,
                            "txn_gross": str(txn_amount),
                            "line_gross": str(line_amount),
                            "gross_diff": str(gross_diff),
                            "txn_fee": str(txn_fee),
                            "line_fee": str(line_fee),
                            "fee_diff": str(fee_diff),
                            "txn_gst": str(txn_gst),
                            "line_tax": str(line_tax),
                            "gst_diff": str(gst_diff),
                            "total_deduction_diff": str(total_deduction_diff),
                            "txn_net": str(txn_net),
                            "line_net": str(line_net),
                            "net_diff": str(net_diff),
                            "tolerance_applied": str(self.config.amount_tolerance),
                        },
                    )
                    generated_matches.append(match_record)
                    matched_txn_ids.add(txn.id)
                    matched_line_ids.add(best_line.id)

        # 4. Identify unsettled / in-flight transactions
        unsettled_txns_list: List[GatewayTransaction] = []
        for txn in tenant_txns:
            if txn.id not in matched_txn_ids:
                txn.settlement_status = SettlementStatusEnum.UNSETTLED
                unsettled_txns_list.append(txn)

        # 5. Identify unmatched settlement lines
        unmatched_lines_list: List[SettlementLine] = [
            line for line in tenant_lines if line.id not in matched_line_ids
        ]

        # 6. Aggregate Layer 2 summary telemetry
        summary = Layer2MatchSummary(
            total_txns_evaluated=len(tenant_txns),
            settled_txns=len(settled_txns_list),
            unsettled_txns=len(unsettled_txns_list),
            fee_discrepancy_txns=len(fee_discrepancy_txns_list),
            total_settlement_lines_evaluated=len(tenant_lines),
            matched_lines=len(matched_lines_list),
            unmatched_lines=len(unmatched_lines_list),
            total_settled_gross_amount=total_settled_gross,
            total_settled_net_amount=total_settled_net,
            total_fees_deducted=total_fees,
            total_gst_deducted=total_gst,
            total_fee_discrepancy_amount=total_fee_discrepancy_amount,
        )

        return Layer2MatchOutput(
            matches=generated_matches,
            summary=summary,
            settled_txns=settled_txns_list,
            unsettled_txns=unsettled_txns_list,
            fee_discrepancy_txns=fee_discrepancy_txns_list,
            matched_lines=matched_lines_list,
            unmatched_lines=unmatched_lines_list,
        )

