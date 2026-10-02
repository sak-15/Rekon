"""
Layer 1 Reconciliation Matching Engine.
Matches Subscription Billing Invoices (Chargebee, Zoho) with Payment Gateway Transactions (Razorpay, Stripe).

Supports:
1. Exact reference matching (invoice_no == txn.invoice_ref) with configurable amount tolerance.
2. Heuristic fuzzy matching (customer_email + amount + date window proximity) when invoice reference is missing.
3. Exception & discrepancy detection for partial payments or amount mismatches.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Set, Dict, Tuple

from app.models.invoice import Invoice, ReconciliationStatusEnum
from app.models.gateway import GatewayTransaction, TxnStatusEnum
from app.models.reconciliation import (
    ReconciliationMatch,
    ReconciliationLayerEnum,
    MatchTypeEnum,
    MatchStatusEnum,
)
from app.schemas.reconciliation import (
    ReconciliationRuleConfig,
    Layer1MatchSummary,
)


@dataclass
class Layer1MatchOutput:
    """
    Result container returned by the Layer 1 Matching Engine.
    """
    matches: List[ReconciliationMatch] = field(default_factory=list)
    summary: Layer1MatchSummary = field(default_factory=Layer1MatchSummary)
    matched_invoices: List[Invoice] = field(default_factory=list)
    unmatched_invoices: List[Invoice] = field(default_factory=list)
    discrepant_invoices: List[Invoice] = field(default_factory=list)
    matched_txns: List[GatewayTransaction] = field(default_factory=list)
    unmatched_txns: List[GatewayTransaction] = field(default_factory=list)


class Layer1MatchingEngine:
    """
    Core matching engine executing Layer 1 reconciliation between Invoices and Gateway Transactions.
    """

    def __init__(self, config: Optional[ReconciliationRuleConfig] = None):
        self.config = config or ReconciliationRuleConfig()

    def execute(
        self,
        org_id: str,
        run_id: str,
        invoices: List[Invoice],
        gateway_txns: List[GatewayTransaction],
    ) -> Layer1MatchOutput:
        """
        Execute Layer 1 matching algorithm.

        :param org_id: Organisation UUID ensuring multi-tenant isolation.
        :param run_id: ReconciliationRun UUID linking generated audit matches.
        :param invoices: List of invoices to evaluate.
        :param gateway_txns: List of gateway transactions to evaluate.
        :return: Layer1MatchOutput containing generated matches, summary metrics, and categorized entities.
        """
        # 1. Tenant filter & sanity check
        tenant_invoices = [inv for inv in invoices if str(inv.org_id) == str(org_id)]
        tenant_txns = [
            txn for txn in gateway_txns
            if str(txn.org_id) == str(org_id) and txn.status == TxnStatusEnum.CAPTURED
        ]

        matched_invoice_ids: Set[str] = set()
        matched_txn_ids: Set[str] = set()
        generated_matches: List[ReconciliationMatch] = []

        exact_matches_count = 0
        fuzzy_matches_count = 0
        total_matched_amount = Decimal("0.00")
        total_discrepancy_amount = Decimal("0.00")
        discrepant_invoice_list: List[Invoice] = []

        # =====================================================================
        # Step 1: Deterministic Exact Reference Matching
        # =====================================================================
        # Build lookup table of available transactions by normalized invoice_ref
        txns_by_ref: Dict[str, List[GatewayTransaction]] = defaultdict(list)
        for txn in tenant_txns:
            if txn.invoice_ref:
                normalized_ref = txn.invoice_ref.strip().upper()
                txns_by_ref[normalized_ref].append(txn)

        for inv in tenant_invoices:
            if inv.id in matched_invoice_ids:
                continue

            normalized_inv_no = inv.invoice_no.strip().upper()
            candidates = txns_by_ref.get(normalized_inv_no, [])

            # Find first available unused candidate
            best_txn: Optional[GatewayTransaction] = None
            for candidate in candidates:
                if candidate.id not in matched_txn_ids:
                    best_txn = candidate
                    break

            if best_txn is not None:
                amount_diff = abs(Decimal(str(inv.amount)) - Decimal(str(best_txn.amount)))

                if amount_diff <= self.config.amount_tolerance:
                    # Matched within allowed tolerance (e.g. <= ₹1.00 paisa rounding)
                    is_exact_zero_delta = (amount_diff == Decimal("0.00"))
                    confidence = Decimal("100.00") if is_exact_zero_delta else Decimal("95.00")
                    status = MatchStatusEnum.MATCHED

                    inv.reconciliation_status = ReconciliationStatusEnum.MATCHED
                    best_txn.reconciliation_status = ReconciliationStatusEnum.MATCHED
                    total_matched_amount += Decimal(str(inv.amount))
                    exact_matches_count += 1
                else:
                    # Amount difference exceeds allowed tolerance -> Exception / Partial
                    confidence = Decimal("80.00")
                    status = (
                        MatchStatusEnum.PARTIAL
                        if best_txn.amount < inv.amount
                        else MatchStatusEnum.DISCREPANCY
                    )
                    inv.reconciliation_status = ReconciliationStatusEnum.EXCEPTION
                    best_txn.reconciliation_status = ReconciliationStatusEnum.EXCEPTION
                    total_discrepancy_amount += amount_diff
                    discrepant_invoice_list.append(inv)

                match_record = ReconciliationMatch(
                    org_id=org_id,
                    run_id=run_id,
                    layer=ReconciliationLayerEnum.LAYER_1,
                    invoice_id=inv.id,
                    gateway_txn_id=best_txn.id,
                    match_type=MatchTypeEnum.EXACT,
                    confidence_score=confidence,
                    status=status,
                    amount_difference=amount_diff,
                    match_details={
                        "matched_by": "exact_invoice_ref",
                        "invoice_no": inv.invoice_no,
                        "invoice_ref": best_txn.invoice_ref,
                        "invoice_amount": str(inv.amount),
                        "txn_amount": str(best_txn.amount),
                        "amount_difference": str(amount_diff),
                        "tolerance_applied": str(self.config.amount_tolerance),
                    },
                )
                generated_matches.append(match_record)
                matched_invoice_ids.add(inv.id)
                matched_txn_ids.add(best_txn.id)

        # =====================================================================
        # Step 2: Heuristic Fuzzy Fallback (Customer Email + Amount + Date Window)
        # =====================================================================
        if self.config.enable_fuzzy_matching:
            # Gather remaining unmatched transactions
            available_txns = [
                txn for txn in tenant_txns if txn.id not in matched_txn_ids
            ]

            for inv in tenant_invoices:
                if inv.id in matched_invoice_ids:
                    continue

                if not inv.customer_email:
                    continue

                inv_email = inv.customer_email.strip().lower()
                inv_amount = Decimal(str(inv.amount))
                inv_date = inv.invoice_date.date() if hasattr(inv.invoice_date, "date") else inv.invoice_date

                # Search candidate pool
                best_fuzzy_txn: Optional[GatewayTransaction] = None
                lowest_date_diff: int = 9999
                lowest_amount_diff: Decimal = Decimal("999999.00")

                for txn in available_txns:
                    if txn.id in matched_txn_ids:
                        continue

                    if not txn.customer_email:
                        continue

                    txn_email = txn.customer_email.strip().lower()
                    if txn_email != inv_email:
                        continue

                    # Amount check within tolerance
                    txn_amount = Decimal(str(txn.amount))
                    amount_diff = abs(inv_amount - txn_amount)
                    if amount_diff > self.config.amount_tolerance:
                        continue

                    # Date proximity window check
                    txn_date = txn.captured_at.date() if hasattr(txn.captured_at, "date") else txn.captured_at
                    days_diff = abs((txn_date - inv_date).days)
                    if days_diff > self.config.layer_1_date_window_days:
                        continue

                    # Select closest match (lowest date diff, then lowest amount diff)
                    if (days_diff < lowest_date_diff) or (
                        days_diff == lowest_date_diff and amount_diff < lowest_amount_diff
                    ):
                        best_fuzzy_txn = txn
                        lowest_date_diff = days_diff
                        lowest_amount_diff = amount_diff

                if best_fuzzy_txn is not None:
                    # Calculate confidence score
                    # Base score 90.00% if exact date & amount, reduced by 2% per day of lag
                    confidence = Decimal("90.00") - (Decimal(lowest_date_diff) * Decimal("2.00"))
                    if lowest_amount_diff > Decimal("0.00"):
                        confidence -= Decimal("1.00")

                    if confidence >= self.config.min_fuzzy_confidence:
                        inv.reconciliation_status = ReconciliationStatusEnum.MATCHED
                        best_fuzzy_txn.reconciliation_status = ReconciliationStatusEnum.MATCHED
                        total_matched_amount += inv_amount
                        fuzzy_matches_count += 1

                        match_record = ReconciliationMatch(
                            org_id=org_id,
                            run_id=run_id,
                            layer=ReconciliationLayerEnum.LAYER_1,
                            invoice_id=inv.id,
                            gateway_txn_id=best_fuzzy_txn.id,
                            match_type=MatchTypeEnum.FUZZY,
                            confidence_score=confidence,
                            status=MatchStatusEnum.MATCHED,
                            amount_difference=lowest_amount_diff,
                            match_details={
                                "matched_by": "customer_email_amount_date",
                                "customer_email": inv.customer_email,
                                "date_diff_days": lowest_date_diff,
                                "amount_difference": str(lowest_amount_diff),
                                "date_window_applied": self.config.layer_1_date_window_days,
                                "amount_tolerance_applied": str(self.config.amount_tolerance),
                            },
                        )
                        generated_matches.append(match_record)
                        matched_invoice_ids.add(inv.id)
                        matched_txn_ids.add(best_fuzzy_txn.id)

        # =====================================================================
        # Step 3: Classify Remaining Unmatched Records
        # =====================================================================
        unmatched_invoice_list: List[Invoice] = []
        matched_invoice_list: List[Invoice] = []

        for inv in tenant_invoices:
            if inv.id in matched_invoice_ids:
                if inv not in discrepant_invoice_list:
                    matched_invoice_list.append(inv)
            else:
                inv.reconciliation_status = ReconciliationStatusEnum.UNMATCHED
                unmatched_invoice_list.append(inv)

        unmatched_txn_list: List[GatewayTransaction] = []
        matched_txn_list: List[GatewayTransaction] = []

        for txn in tenant_txns:
            if txn.id in matched_txn_ids:
                matched_txn_list.append(txn)
            else:
                txn.reconciliation_status = ReconciliationStatusEnum.UNMATCHED
                unmatched_txn_list.append(txn)

        # =====================================================================
        # Step 4: Aggregate Summary Telemetry
        # =====================================================================
        summary = Layer1MatchSummary(
            total_invoices_evaluated=len(tenant_invoices),
            matched_invoices=len(matched_invoice_list),
            unmatched_invoices=len(unmatched_invoice_list),
            discrepancy_invoices=len(discrepant_invoice_list),
            total_txns_evaluated=len(tenant_txns),
            matched_txns=len(matched_txn_list),
            unmatched_txns=len(unmatched_txn_list),
            total_matched_amount=total_matched_amount,
            total_discrepancy_amount=total_discrepancy_amount,
            exact_matches_count=exact_matches_count,
            fuzzy_matches_count=fuzzy_matches_count,
        )

        return Layer1MatchOutput(
            matches=generated_matches,
            summary=summary,
            matched_invoices=matched_invoice_list,
            unmatched_invoices=unmatched_invoice_list,
            discrepant_invoices=discrepant_invoice_list,
            matched_txns=matched_txn_list,
            unmatched_txns=unmatched_txn_list,
        )

