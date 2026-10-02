"""
Layer 3 Reconciliation Matching Engine.
Matches Gateway Settlement Batches (Razorpay, Stripe) with Bank Statement Credits (HDFC, ICICI, etc.).

Supports:
1. Exact UTR matching via bank reference number or raw narration extraction.
2. Heuristic fallback matching via gateway keyword + net amount + bank clearing window (±4 days).
3. Paisa rounding tolerance (<= ₹1.00).
4. Bank deposit discrepancy detection.
5. Missing cash in transit / delayed payout identification.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional, Set, Dict

from app.models.settlement import SettlementBatch
from app.models.bank import BankCredit
from app.models.invoice import ReconciliationStatusEnum
from app.models.reconciliation import (
    ReconciliationMatch,
    ReconciliationLayerEnum,
    MatchTypeEnum,
    MatchStatusEnum,
)
from app.schemas.reconciliation import (
    ReconciliationRuleConfig,
    Layer3MatchSummary,
)


@dataclass
class Layer3MatchOutput:
    """
    Result container returned by the Layer 3 Matching Engine.
    """
    matches: List[ReconciliationMatch] = field(default_factory=list)
    summary: Layer3MatchSummary = field(default_factory=Layer3MatchSummary)
    matched_batches: List[SettlementBatch] = field(default_factory=list)
    unmatched_batches: List[SettlementBatch] = field(default_factory=list)
    discrepant_batches: List[SettlementBatch] = field(default_factory=list)
    matched_bank_credits: List[BankCredit] = field(default_factory=list)
    unmatched_bank_credits: List[BankCredit] = field(default_factory=list)


# Gateway keyword signatures commonly observed in Indian bank statement narrations
GATEWAY_NARRATION_KEYWORDS: Dict[str, List[str]] = {
    "razorpay": ["RAZORPAY", "RZP", "RAZORPAY SOFTWARE"],
    "stripe": ["STRIPE", "STRIPE INDIA", "STRIPEPAY"],
    "cashfree": ["CASHFREE", "CASHFREE PAYMENTS"],
    "payu": ["PAYU", "PAYU PAYMENTS"],
}


class Layer3MatchingEngine:
    """
    Core matching engine executing Layer 3 reconciliation between Settlement Batches and Bank Statement Credits.
    """

    def __init__(self, config: Optional[ReconciliationRuleConfig] = None):
        self.config = config or ReconciliationRuleConfig()

    def execute(
        self,
        org_id: str,
        run_id: str,
        settlement_batches: List[SettlementBatch],
        bank_credits: List[BankCredit],
    ) -> Layer3MatchOutput:
        """
        Execute Layer 3 matching algorithm.

        :param org_id: Organisation UUID ensuring multi-tenant isolation.
        :param run_id: ReconciliationRun UUID linking generated audit matches.
        :param settlement_batches: List of settlement batches to evaluate.
        :param bank_credits: List of bank statement credit entries to match against.
        :return: Layer3MatchOutput containing matches, summary metrics, and categorized entities.
        """
        # 1. Multi-tenant filtering
        tenant_batches = [
            batch for batch in settlement_batches
            if str(batch.org_id) == str(org_id)
        ]
        tenant_credits = [
            credit for credit in bank_credits
            if str(credit.org_id) == str(org_id)
        ]

        matched_batch_ids: Set[str] = set()
        matched_credit_ids: Set[str] = set()
        generated_matches: List[ReconciliationMatch] = []

        matched_batches_list: List[SettlementBatch] = []
        discrepant_batches_list: List[SettlementBatch] = []
        unmatched_batches_list: List[SettlementBatch] = []

        matched_credits_list: List[BankCredit] = []
        unmatched_credits_list: List[BankCredit] = []

        utr_matches_count = 0
        fuzzy_matches_count = 0
        total_settled_amount = Decimal("0.00")
        total_bank_credited_amount = Decimal("0.00")
        total_discrepancy_amount = Decimal("0.00")

        # 2. Build index of bank credits by reference_no for fast exact lookup
        credits_by_ref: Dict[str, List[BankCredit]] = defaultdict(list)
        for credit in tenant_credits:
            if credit.reference_no:
                normalized_ref = credit.reference_no.strip().upper()
                credits_by_ref[normalized_ref].append(credit)

        # =====================================================================
        # Step 1: Deterministic UTR Matching
        # =====================================================================
        for batch in tenant_batches:
            if batch.id in matched_batch_ids:
                continue

            if not batch.utr_number:
                continue

            clean_utr = batch.utr_number.strip().upper()
            candidate_credit: Optional[BankCredit] = None

            # 1a. Try lookup by exact reference_no column
            ref_candidates = credits_by_ref.get(clean_utr, [])
            for cand in ref_candidates:
                if cand.id not in matched_credit_ids:
                    candidate_credit = cand
                    break

            # 1b. If not found in reference_no, search inside bank narration string
            if candidate_credit is None and len(clean_utr) >= 5:
                for credit in tenant_credits:
                    if credit.id not in matched_credit_ids:
                        if clean_utr in credit.narration.upper():
                            candidate_credit = credit
                            break

            if candidate_credit is not None:
                batch_net = Decimal(str(batch.net_amount))
                credit_amount = Decimal(str(candidate_credit.credit_amount))
                amount_diff = abs(batch_net - credit_amount)

                if amount_diff <= self.config.amount_tolerance:
                    is_exact_zero = (amount_diff == Decimal("0.00"))
                    confidence = Decimal("100.00") if is_exact_zero else Decimal("95.00")
                    status = MatchStatusEnum.MATCHED

                    batch.reconciliation_status = ReconciliationStatusEnum.MATCHED
                    candidate_credit.reconciliation_status = ReconciliationStatusEnum.MATCHED
                    matched_batches_list.append(batch)
                    matched_credits_list.append(candidate_credit)

                    total_settled_amount += batch_net
                    total_bank_credited_amount += credit_amount
                    utr_matches_count += 1
                else:
                    # Amount difference exceeds allowed tolerance -> Discrepancy
                    confidence = Decimal("85.00")
                    status = MatchStatusEnum.DISCREPANCY

                    batch.reconciliation_status = ReconciliationStatusEnum.EXCEPTION
                    candidate_credit.reconciliation_status = ReconciliationStatusEnum.EXCEPTION
                    discrepant_batches_list.append(batch)

                    total_discrepancy_amount += amount_diff

                match_record = ReconciliationMatch(
                    org_id=org_id,
                    run_id=run_id,
                    layer=ReconciliationLayerEnum.LAYER_3,
                    settlement_batch_id=batch.id,
                    bank_credit_id=candidate_credit.id,
                    match_type=MatchTypeEnum.EXACT,
                    confidence_score=confidence,
                    status=status,
                    amount_difference=amount_diff,
                    match_details={
                        "matched_by": "utr_number",
                        "utr": clean_utr,
                        "batch_id": batch.batch_id,
                        "batch_net": str(batch_net),
                        "credit_amount": str(credit_amount),
                        "amount_diff": str(amount_diff),
                        "bank_narration": candidate_credit.narration,
                        "reference_no": candidate_credit.reference_no,
                        "tolerance_applied": str(self.config.amount_tolerance),
                    },
                )
                generated_matches.append(match_record)
                matched_batch_ids.add(batch.id)
                matched_credit_ids.add(candidate_credit.id)

        # =====================================================================
        # Step 2: Heuristic Fallback (Gateway Keyword + Net Amount + Clearing Window)
        # =====================================================================
        if self.config.enable_fuzzy_matching:
            available_credits = [
                c for c in tenant_credits if c.id not in matched_credit_ids
            ]

            for batch in tenant_batches:
                if batch.id in matched_batch_ids:
                    continue

                batch_net = Decimal(str(batch.net_amount))
                batch_date = (
                    batch.settlement_date.date()
                    if hasattr(batch.settlement_date, "date")
                    else batch.settlement_date
                )

                # Determine gateway keywords to look for
                gateway_val = (
                    batch.gateway.value
                    if hasattr(batch.gateway, "value")
                    else str(batch.gateway).lower()
                )
                keywords = GATEWAY_NARRATION_KEYWORDS.get(gateway_val, [gateway_val.upper()])

                best_fuzzy_credit: Optional[BankCredit] = None
                lowest_date_diff = 9999
                lowest_amount_diff = Decimal("999999.00")

                for credit in available_credits:
                    if credit.id in matched_credit_ids:
                        continue

                    credit_amount = Decimal(str(credit.credit_amount))
                    amount_diff = abs(batch_net - credit_amount)
                    if amount_diff > self.config.amount_tolerance:
                        continue

                    # Clearing window check
                    credit_date = (
                        credit.transaction_date.date()
                        if hasattr(credit.transaction_date, "date")
                        else credit.transaction_date
                    )
                    days_diff = abs((credit_date - batch_date).days)
                    if days_diff > self.config.layer_3_bank_window_days:
                        continue

                    # Check for gateway signature keyword in narration
                    narration_upper = credit.narration.upper()
                    has_keyword = any(kw in narration_upper for kw in keywords)
                    if not has_keyword:
                        continue

                    # Select best candidate
                    if (days_diff < lowest_date_diff) or (
                        days_diff == lowest_date_diff and amount_diff < lowest_amount_diff
                    ):
                        best_fuzzy_credit = credit
                        lowest_date_diff = days_diff
                        lowest_amount_diff = amount_diff

                if best_fuzzy_credit is not None:
                    # Base confidence: 90% minus 2% per day of lag
                    confidence = Decimal("90.00") - (Decimal(lowest_date_diff) * Decimal("2.00"))
                    if lowest_amount_diff > Decimal("0.00"):
                        confidence -= Decimal("1.00")

                    if confidence >= self.config.min_fuzzy_confidence:
                        batch.reconciliation_status = ReconciliationStatusEnum.MATCHED
                        best_fuzzy_credit.reconciliation_status = ReconciliationStatusEnum.MATCHED
                        matched_batches_list.append(batch)
                        matched_credits_list.append(best_fuzzy_credit)

                        total_settled_amount += batch_net
                        total_bank_credited_amount += Decimal(str(best_fuzzy_credit.credit_amount))
                        fuzzy_matches_count += 1

                        match_record = ReconciliationMatch(
                            org_id=org_id,
                            run_id=run_id,
                            layer=ReconciliationLayerEnum.LAYER_3,
                            settlement_batch_id=batch.id,
                            bank_credit_id=best_fuzzy_credit.id,
                            match_type=MatchTypeEnum.FUZZY,
                            confidence_score=confidence,
                            status=MatchStatusEnum.MATCHED,
                            amount_difference=lowest_amount_diff,
                            match_details={
                                "matched_by": "gateway_keyword_amount_date",
                                "gateway": gateway_val,
                                "batch_id": batch.batch_id,
                                "batch_net": str(batch_net),
                                "credit_amount": str(best_fuzzy_credit.credit_amount),
                                "date_diff_days": lowest_date_diff,
                                "amount_difference": str(lowest_amount_diff),
                                "bank_narration": best_fuzzy_credit.narration,
                                "bank_window_applied": self.config.layer_3_bank_window_days,
                                "amount_tolerance_applied": str(self.config.amount_tolerance),
                            },
                        )
                        generated_matches.append(match_record)
                        matched_batch_ids.add(batch.id)
                        matched_credit_ids.add(best_fuzzy_credit.id)

        # =====================================================================
        # Step 3: Classify Remaining Unmatched Batches & Bank Credits
        # =====================================================================
        for batch in tenant_batches:
            if batch.id not in matched_batch_ids:
                batch.reconciliation_status = ReconciliationStatusEnum.UNMATCHED
                unmatched_batches_list.append(batch)

        for credit in tenant_credits:
            if credit.id not in matched_credit_ids:
                credit.reconciliation_status = ReconciliationStatusEnum.UNMATCHED
                unmatched_credits_list.append(credit)

        # =====================================================================
        # Step 4: Aggregate Summary Telemetry
        # =====================================================================
        summary = Layer3MatchSummary(
            total_batches_evaluated=len(tenant_batches),
            matched_batches=len(matched_batches_list),
            unmatched_batches=len(unmatched_batches_list),
            discrepancy_batches=len(discrepant_batches_list),
            total_bank_credits_evaluated=len(tenant_credits),
            matched_bank_credits=len(matched_credits_list),
            unmatched_bank_credits=len(unmatched_credits_list),
            total_settled_amount=total_settled_amount,
            total_bank_credited_amount=total_bank_credited_amount,
            total_discrepancy_amount=total_discrepancy_amount,
            utr_matches_count=utr_matches_count,
            fuzzy_matches_count=fuzzy_matches_count,
        )

        return Layer3MatchOutput(
            matches=generated_matches,
            summary=summary,
            matched_batches=matched_batches_list,
            unmatched_batches=unmatched_batches_list,
            discrepant_batches=discrepant_batches_list,
            matched_bank_credits=matched_credits_list,
            unmatched_bank_credits=unmatched_credits_list,
        )

