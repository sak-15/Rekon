"""
Reconciliation Pipeline Orchestrator.
Coordinates execution of Layer 1, Layer 2, and Layer 3 matching engines in an ACID transaction.
Updates reconciliation statuses on entity records, stores detailed audit matches,
and computes high-level executive financial metrics.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
import logging
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.gateway import GatewayTransaction, TxnStatusEnum
from app.models.settlement import SettlementBatch, SettlementLine
from app.models.bank import BankCredit
from app.models.reconciliation import (
    ReconciliationRun,
    ReconciliationRunStatusEnum,
)
from app.schemas.reconciliation import ReconciliationRuleConfig
from app.services.matching.layer1 import Layer1MatchingEngine
from app.services.matching.layer2 import Layer2MatchingEngine
from app.services.matching.layer3 import Layer3MatchingEngine

logger = logging.getLogger(__name__)


class ReconciliationOrchestrator:
    """
    End-to-end reconciliation pipeline orchestrator.
    """

    def __init__(self, db: Session, config: Optional[ReconciliationRuleConfig] = None):
        self.db = db
        self.config = config or ReconciliationRuleConfig()

    def run(self, org_id: str, user_id: Optional[str] = None) -> ReconciliationRun:
        """
        Execute full three-layer reconciliation pipeline for an organisation.

        :param org_id: Organisation UUID ensuring multi-tenant isolation.
        :param user_id: Optional UUID of the analyst/user who initiated the run.
        :return: Completed ReconciliationRun instance with updated telemetry.
        """
        now = datetime.now(timezone.utc)

        # 1. Initialize run record in RUNNING state
        # Convert Pydantic model to dict for JSON column storage
        rule_dict = {
            "amount_tolerance": str(self.config.amount_tolerance),
            "layer_1_date_window_days": self.config.layer_1_date_window_days,
            "layer_3_bank_window_days": self.config.layer_3_bank_window_days,
            "enable_fuzzy_matching": self.config.enable_fuzzy_matching,
            "min_fuzzy_confidence": str(self.config.min_fuzzy_confidence),
        }

        reconciliation_run = ReconciliationRun(
            org_id=org_id,
            initiated_by=user_id,
            status=ReconciliationRunStatusEnum.RUNNING,
            started_at=now,
            rule_config=rule_dict,
        )
        self.db.add(reconciliation_run)
        self.db.flush()  # Generates reconciliation_run.id

        try:
            # 2. Query tenant's operational data
            invoices = self.db.query(Invoice).filter(Invoice.org_id == org_id).all()
            gateway_txns = (
                self.db.query(GatewayTransaction)
                .filter(GatewayTransaction.org_id == org_id)
                .all()
            )
            settlement_lines = (
                self.db.query(SettlementLine)
                .filter(SettlementLine.org_id == org_id)
                .all()
            )
            settlement_batches = (
                self.db.query(SettlementBatch)
                .filter(SettlementBatch.org_id == org_id)
                .all()
            )
            bank_credits = (
                self.db.query(BankCredit)
                .filter(BankCredit.org_id == org_id)
                .all()
            )

            # 3. Layer 1: Invoices ↔ Gateway Transactions
            engine_l1 = Layer1MatchingEngine(self.config)
            l1_output = engine_l1.execute(
                org_id=org_id,
                run_id=reconciliation_run.id,
                invoices=invoices,
                gateway_txns=gateway_txns,
            )

            # 4. Layer 2: Gateway Transactions ↔ Settlement Lines
            engine_l2 = Layer2MatchingEngine(self.config)
            l2_output = engine_l2.execute(
                org_id=org_id,
                run_id=reconciliation_run.id,
                gateway_txns=gateway_txns,
                settlement_lines=settlement_lines,
            )

            # 5. Layer 3: Settlement Batches ↔ Bank Credits
            engine_l3 = Layer3MatchingEngine(self.config)
            l3_output = engine_l3.execute(
                org_id=org_id,
                run_id=reconciliation_run.id,
                settlement_batches=settlement_batches,
                bank_credits=bank_credits,
            )

            # 6. Persist all generated matches across all 3 layers
            all_matches = (
                l1_output.matches + l2_output.matches + l3_output.matches
            )
            if all_matches:
                self.db.add_all(all_matches)

            # 7. Compute aggregate financial summaries
            invoiced_sum = sum(
                (Decimal(str(inv.amount)) for inv in invoices),
                Decimal("0.00"),
            )
            collected_sum = sum(
                (
                    Decimal(str(txn.amount))
                    for txn in gateway_txns
                    if txn.status == TxnStatusEnum.CAPTURED
                ),
                Decimal("0.00"),
            )
            settled_sum = sum(
                (Decimal(str(b.net_amount)) for b in settlement_batches),
                Decimal("0.00"),
            )
            bank_credited_sum = sum(
                (Decimal(str(c.credit_amount)) for c in bank_credits),
                Decimal("0.00"),
            )
            discrepancy_sum = (
                l1_output.summary.total_discrepancy_amount
                + l2_output.summary.total_fee_discrepancy_amount
                + l3_output.summary.total_discrepancy_amount
            )

            # 8. Update run counters and telemetry
            reconciliation_run.total_invoices = l1_output.summary.total_invoices_evaluated
            reconciliation_run.matched_invoices = l1_output.summary.matched_invoices
            reconciliation_run.unmatched_invoices = (
                l1_output.summary.unmatched_invoices
                + l1_output.summary.discrepancy_invoices
            )

            reconciliation_run.total_txns = l1_output.summary.total_txns_evaluated
            reconciliation_run.matched_txns = l1_output.summary.matched_txns
            reconciliation_run.unmatched_txns = l1_output.summary.unmatched_txns

            reconciliation_run.total_settlements = l3_output.summary.total_batches_evaluated
            reconciliation_run.matched_settlements = l3_output.summary.matched_batches
            reconciliation_run.unmatched_settlements = (
                l3_output.summary.unmatched_batches
                + l3_output.summary.discrepancy_batches
            )

            reconciliation_run.total_bank_credits = (
                l3_output.summary.total_bank_credits_evaluated
            )
            reconciliation_run.matched_bank_credits = (
                l3_output.summary.matched_bank_credits
            )
            reconciliation_run.unmatched_bank_credits = (
                l3_output.summary.unmatched_bank_credits
            )

            reconciliation_run.invoiced_amount = invoiced_sum
            reconciliation_run.collected_amount = collected_sum
            reconciliation_run.settled_amount = settled_sum
            reconciliation_run.bank_credited_amount = bank_credited_sum
            reconciliation_run.discrepancy_amount = discrepancy_sum

            # 8b. Automated Forensic Exception Classification (Phase 4)
            all_matches = l1_output.matches + l2_output.matches + l3_output.matches
            from app.services.exceptions.classifier import ExceptionClassifierEngine
            ExceptionClassifierEngine.classify_and_record_exceptions(
                db=self.db,
                run=reconciliation_run,
                invoices=invoices,
                gateway_txns=gateway_txns,
                settlement_batches=settlement_batches,
                bank_credits=bank_credits,
                matches=all_matches,
            )

            # 9. Mark completed
            reconciliation_run.status = ReconciliationRunStatusEnum.COMPLETED
            reconciliation_run.completed_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(reconciliation_run)
            return reconciliation_run

        except Exception as e:
            self.db.rollback()
            logger.exception("Reconciliation run failed with error: %s", str(e))
            # Mark run failed in a separate transaction
            try:
                failed_run = (
                    self.db.query(ReconciliationRun)
                    .filter_by(id=reconciliation_run.id)
                    .first()
                )
                if failed_run:
                    failed_run.status = ReconciliationRunStatusEnum.FAILED
                    failed_run.error_message = str(e)[:1000]
                    failed_run.completed_at = datetime.now(timezone.utc)
                    self.db.commit()
            except Exception:
                pass
            raise e

