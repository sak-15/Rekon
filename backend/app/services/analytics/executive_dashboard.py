from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.models.invoice import Invoice, ReconciliationStatusEnum
from app.models.gateway import GatewayTransaction, GatewayEnum
from app.models.settlement import SettlementBatch, SettlementLine
from app.models.bank import BankCredit
from app.models.reconciliation import ReconciliationRun
from app.models.reconciliation_exception import (
    ReconciliationException,
    ResolutionStatusEnum,
    ExceptionSeverityEnum,
)
from app.services.fee_audit import FeeAuditEngine
from app.schemas.analytics import (
    ExecutiveKPISummary,
    CashflowWaterfallStep,
    GatewayPerformanceItem,
    ExecutiveAlertItem,
    ExecutiveDashboardResponse,
)


class ExecutiveAnalyticsService:
    """
    Computes high-level financial health, realization waterfalls, gateway take-rate costs,
    and executive alerts for SaaS founders, CFOs, and leadership.
    """

    @classmethod
    def get_dashboard(
        cls,
        db: Session,
        org_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> ExecutiveDashboardResponse:
        """
        Aggregates complete founder dashboard metrics in a single unified response.
        Supports custom date window / month filtering.
        """
        # 1. Query Invoice Totals
        inv_q = db.query(
            func.count(Invoice.id).label("total_count"),
            func.coalesce(func.sum(Invoice.amount + Invoice.tax_amount), Decimal("0.00")).label("total_amount"),
            func.count(
                case((Invoice.reconciliation_status == ReconciliationStatusEnum.MATCHED, 1))
            ).label("matched_count"),
        ).filter(Invoice.org_id == org_id)

        if start_date:
            inv_q = inv_q.filter(Invoice.invoice_date >= start_date)
        if end_date:
            inv_q = inv_q.filter(Invoice.invoice_date <= end_date)

        inv_query = inv_q.first()
        invoice_count = inv_query.total_count or 0
        gross_billed_amount = inv_query.total_amount or Decimal("0.00")
        matched_invoices_count = inv_query.matched_count or 0
        matched_invoices_pct = (
            round((matched_invoices_count / invoice_count) * 100, 1) if invoice_count > 0 else 100.0
        )

        # 2. Query Gateway Totals & Grouping
        gw_q = db.query(
            func.count(GatewayTransaction.id).label("total_count"),
            func.coalesce(func.sum(GatewayTransaction.amount), Decimal("0.00")).label("total_volume"),
            func.coalesce(func.sum(GatewayTransaction.gateway_fee), Decimal("0.00")).label("total_fee"),
            func.coalesce(func.sum(GatewayTransaction.gateway_fee_gst), Decimal("0.00")).label("total_tax"),
        ).filter(GatewayTransaction.org_id == org_id)

        if start_date:
            gw_q = gw_q.filter(GatewayTransaction.captured_at >= start_date)
        if end_date:
            gw_q = gw_q.filter(GatewayTransaction.captured_at <= end_date)

        gw_query = gw_q.first()
        gateway_txn_count = gw_query.total_count or 0
        gross_gateway_volume = gw_query.total_volume or Decimal("0.00")
        total_gateway_fees = gw_query.total_fee or Decimal("0.00")
        total_gateway_gst = gw_query.total_tax or Decimal("0.00")
        total_gateway_deductions = total_gateway_fees + total_gateway_gst

        blended_take_rate_pct = (
            round((float(total_gateway_deductions) / float(gross_gateway_volume)) * 100, 2)
            if gross_gateway_volume > Decimal("0.00")
            else 0.0
        )

        # 3. Query Bank Cleared Cash
        bank_q = db.query(
            func.count(BankCredit.id).label("total_count"),
            func.coalesce(func.sum(BankCredit.credit_amount), Decimal("0.00")).label("total_cash"),
            func.count(
                case((BankCredit.reconciliation_status == ReconciliationStatusEnum.MATCHED, 1))
            ).label("matched_count"),
        ).filter(BankCredit.org_id == org_id)

        if start_date:
            bank_q = bank_q.filter(BankCredit.transaction_date >= start_date)
        if end_date:
            bank_q = bank_q.filter(BankCredit.transaction_date <= end_date)

        bank_query = bank_q.first()
        bank_credit_count = bank_query.total_count or 0
        net_settled_cash = bank_query.total_cash or Decimal("0.00")
        matched_bank_count = bank_query.matched_count or 0
        settled_batches_pct = (
            round((matched_bank_count / bank_credit_count) * 100, 1) if bank_credit_count > 0 else 100.0
        )

        # 4. Run Fee Audit for Leakage / Overcharge Detection
        fee_report = FeeAuditEngine.audit_transactions(
            db, org_id=org_id, start_date=start_date, end_date=end_date
        )
        fee_leakage_detected = fee_report.total_overcharged_amount
        overcharged_txns_count = fee_report.overcharged_count

        # 5. Query Active Exception Exposure
        active_exceptions = (
            db.query(ReconciliationException)
            .filter(
                ReconciliationException.org_id == org_id,
                ReconciliationException.status.in_([
                    ResolutionStatusEnum.OPEN,
                    ResolutionStatusEnum.INVESTIGATING,
                ]),
            )
            .all()
        )
        open_exceptions_count = len(active_exceptions)
        unresolved_exposure = sum(
            (e.discrepancy_amount for e in active_exceptions), Decimal("0.00")
        )

        total_all_exceptions = (
            db.query(func.count(ReconciliationException.id))
            .filter(ReconciliationException.org_id == org_id)
            .scalar()
            or 0
        )

        # 6. Calculate Financial Health Score (0 - 100)
        # 35% Invoice Reconciled %
        # 35% Bank Cleared %
        # 15% Gateway Fee Integrity (100 - overcharge ratio)
        # 15% Exception Clearance Ratio (resolved / total)
        fee_integrity_pct = 100.0
        if total_gateway_fees > Decimal("0.00"):
            leak_ratio = float(fee_leakage_detected) / float(total_gateway_fees)
            fee_integrity_pct = max(0.0, 100.0 - (leak_ratio * 100.0))

        exception_health_pct = 100.0
        if total_all_exceptions > 0:
            open_ratio = float(open_exceptions_count) / float(total_all_exceptions)
            exception_health_pct = max(0.0, 100.0 - (open_ratio * 100.0))

        raw_health_score = (
            (matched_invoices_pct * 0.35)
            + (settled_batches_pct * 0.35)
            + (fee_integrity_pct * 0.15)
            + (exception_health_pct * 0.15)
        )
        health_score = round(max(0.0, min(100.0, raw_health_score)), 1)

        if health_score >= 90.0:
            health_status = "EXCELLENT"
        elif health_score >= 75.0:
            health_status = "GOOD"
        elif health_score >= 60.0:
            health_status = "NEEDS_ATTENTION"
        else:
            health_status = "CRITICAL"

        summary = ExecutiveKPISummary(
            gross_billed_amount=gross_billed_amount,
            invoice_count=invoice_count,
            gross_gateway_volume=gross_gateway_volume,
            gateway_txn_count=gateway_txn_count,
            net_settled_cash=net_settled_cash,
            bank_credit_count=bank_credit_count,
            total_gateway_fees=total_gateway_fees,
            total_gateway_gst=total_gateway_gst,
            total_gateway_deductions=total_gateway_deductions,
            blended_take_rate_pct=blended_take_rate_pct,
            fee_leakage_detected=fee_leakage_detected,
            overcharged_txns_count=overcharged_txns_count,
            unresolved_exposure=unresolved_exposure,
            open_exceptions_count=open_exceptions_count,
            health_score=health_score,
            health_status=health_status,
            matched_invoices_pct=matched_invoices_pct,
            settled_batches_pct=settled_batches_pct,
        )

        # 7. Build Cashflow Waterfall Steps
        waterfall = cls._build_cashflow_waterfall(
            gross_billed=gross_billed_amount,
            gateway_volume=gross_gateway_volume,
            gateway_fees=total_gateway_fees,
            gateway_gst=total_gateway_gst,
            net_bank_cash=net_settled_cash,
        )

        # 8. Build Gateway Comparison
        gateway_comparison = cls._build_gateway_comparison(
            db=db,
            org_id=org_id,
            total_volume=gross_gateway_volume,
            fee_report=fee_report,
            start_date=start_date,
            end_date=end_date,
        )

        # 9. Generate Actionable Alerts
        actionable_alerts = cls._generate_actionable_alerts(
            summary=summary,
            fee_report=fee_report,
        )

        return ExecutiveDashboardResponse(
            summary=summary,
            waterfall=waterfall,
            gateway_comparison=gateway_comparison,
            actionable_alerts=actionable_alerts,
            last_updated=datetime.utcnow().isoformat() + "Z",
        )

    @classmethod
    def _build_cashflow_waterfall(
        cls,
        gross_billed: Decimal,
        gateway_volume: Decimal,
        gateway_fees: Decimal,
        gateway_gst: Decimal,
        net_bank_cash: Decimal,
    ) -> List[CashflowWaterfallStep]:
        """
        Builds the 5-step realization pipeline showing how invoiced revenue translates to bank cash.
        """
        # Baseline reference: prefer gross_billed if positive, else gateway_volume
        base_amount = gross_billed if gross_billed > Decimal("0.00") else gateway_volume
        base_float = float(base_amount) if base_amount > Decimal("0.00") else 1.0

        fee_pct = round((float(gateway_fees) / base_float) * 100, 2)
        gst_pct = round((float(gateway_gst) / base_float) * 100, 2)

        # Calculate In-Transit / Timing Lag
        # Theoretical expected cash after deductions = base_amount - gateway_fees - gateway_gst
        expected_cash = max(Decimal("0.00"), base_amount - gateway_fees - gateway_gst)
        in_transit = max(Decimal("0.00"), expected_cash - net_bank_cash)
        in_transit_pct = round((float(in_transit) / base_float) * 100, 2)

        net_cash_pct = round((float(net_bank_cash) / base_float) * 100, 2)

        return [
            CashflowWaterfallStep(
                step_key="gross_billed",
                label="Gross Billed Revenue",
                amount=base_amount,
                percentage_of_gross=100.0,
                step_type="starting",
                description="Total subscription billing invoiced across Chargebee / Zoho",
            ),
            CashflowWaterfallStep(
                step_key="gateway_mdr",
                label="Gateway MDR Deductions",
                amount=gateway_fees,
                percentage_of_gross=fee_pct,
                step_type="deduction",
                description="Merchant Discount Rate retained by Razorpay / Stripe rails",
            ),
            CashflowWaterfallStep(
                step_key="gateway_gst",
                label="18% GST on Processing",
                amount=gateway_gst,
                percentage_of_gross=gst_pct,
                step_type="deduction",
                description="Statutory Goods and Services Tax charged on processing fees",
            ),
            CashflowWaterfallStep(
                step_key="in_transit_lag",
                label="Settlement Timing Lag / In-Transit",
                amount=in_transit,
                percentage_of_gross=in_transit_pct,
                step_type="deduction",
                description="Funds captured by gateway but pending T+1/T+2 bank batch credit",
            ),
            CashflowWaterfallStep(
                step_key="net_bank_cash",
                label="Net Realized Cash in Bank",
                amount=net_bank_cash,
                percentage_of_gross=net_cash_pct,
                step_type="net_realized",
                description="Verified physical funds credited to corporate bank account",
            ),
        ]

    @classmethod
    def _build_gateway_comparison(
        cls,
        db: Session,
        org_id: str,
        total_volume: Decimal,
        fee_report: Any,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[GatewayPerformanceItem]:
        """
        Breaks down volume, take-rate %, and discrepancies per gateway provider.
        """
        q = db.query(
            GatewayTransaction.gateway,
            func.count(GatewayTransaction.id).label("txn_count"),
            func.coalesce(func.sum(GatewayTransaction.amount), Decimal("0.00")).label("volume"),
            func.coalesce(func.sum(GatewayTransaction.gateway_fee), Decimal("0.00")).label("fee"),
            func.coalesce(func.sum(GatewayTransaction.gateway_fee_gst), Decimal("0.00")).label("tax"),
        ).filter(GatewayTransaction.org_id == org_id)

        if start_date:
            q = q.filter(GatewayTransaction.captured_at >= start_date)
        if end_date:
            q = q.filter(GatewayTransaction.captured_at <= end_date)

        rows = q.group_by(GatewayTransaction.gateway).all()

        total_vol_float = float(total_volume) if total_volume > Decimal("0.00") else 1.0
        results: List[GatewayPerformanceItem] = []

        for row in rows:
            gw_name = row.gateway.value.upper() if hasattr(row.gateway, "value") else str(row.gateway).upper()
            gw_vol = row.volume or Decimal("0.00")
            gw_fee = row.fee or Decimal("0.00")
            gw_tax = row.tax or Decimal("0.00")
            gw_deductions = gw_fee + gw_tax

            gw_vol_float = float(gw_vol)
            take_rate = (
                round((float(gw_deductions) / gw_vol_float) * 100, 2)
                if gw_vol_float > 0
                else 0.0
            )
            share_pct = round((gw_vol_float / total_vol_float) * 100, 1)

            # Check overcharges for this gateway from fee report
            gw_overcharge = Decimal("0.00")
            gw_discrepancy_cnt = 0
            if hasattr(fee_report, "gateway_breakdown") and gw_name.lower() in fee_report.gateway_breakdown:
                gw_info = fee_report.gateway_breakdown[gw_name.lower()]
                gw_overcharge = Decimal(str(gw_info.get("overcharged_amount", 0.0)))
                gw_discrepancy_cnt = gw_info.get("discrepancies", 0)

            results.append(
                GatewayPerformanceItem(
                    gateway=gw_name,
                    transaction_count=row.txn_count or 0,
                    gross_volume=gw_vol,
                    total_fee=gw_fee,
                    total_gst=gw_tax,
                    total_deductions=gw_deductions,
                    effective_take_rate_pct=take_rate,
                    discrepancy_count=gw_discrepancy_cnt,
                    overcharge_amount=gw_overcharge,
                    volume_share_pct=share_pct,
                )
            )

        return results

    @classmethod
    def _generate_actionable_alerts(
        cls,
        summary: ExecutiveKPISummary,
        fee_report: Any,
    ) -> List[ExecutiveAlertItem]:
        """
        Produces top actionable alerts prioritized for founders and CFOs.
        """
        alerts: List[ExecutiveAlertItem] = []

        # 1. Fee Leakage Alert
        if summary.fee_leakage_detected > Decimal("0.00"):
            alerts.append(
                ExecutiveAlertItem(
                    id="fee_leakage",
                    severity="warning",
                    title=f"₹{summary.fee_leakage_detected:,.2f} Gateway Fee Overcharge Detected",
                    description=f"{summary.overcharged_txns_count} transactions exceeded contracted rate card caps or had 18% GST miscalculated. Dispute claims ready to export.",
                    action_label="Review & Export Dispute Sheet",
                    action_target="fee-audit",
                )
            )

        # 2. Unresolved Risk Exposure
        if summary.unresolved_exposure > Decimal("0.00"):
            alerts.append(
                ExecutiveAlertItem(
                    id="unresolved_exposure",
                    severity="critical" if summary.unresolved_exposure > Decimal("10000.00") else "warning",
                    title=f"₹{summary.unresolved_exposure:,.2f} Active Unresolved Exposure",
                    description=f"{summary.open_exceptions_count} reconciliation exceptions pending finance action (timing lags, missing bank credits, or unbilled charges).",
                    action_label="Open Resolution Queue",
                    action_target="exceptions",
                )
            )

        # 3. Take-Rate Benchmark Check
        if summary.blended_take_rate_pct > 2.36:
            alerts.append(
                ExecutiveAlertItem(
                    id="high_take_rate",
                    severity="warning",
                    title=f"Blended Take-Rate High at {summary.blended_take_rate_pct}%",
                    description="Current effective cost exceeds standard 2.00% + 18% GST baseline (2.36%), likely driven by international cards or un-capped debit transactions.",
                    action_label="Audit Rate Cards",
                    action_target="fee-audit",
                )
            )
        elif summary.gross_gateway_volume > Decimal("0.00"):
            alerts.append(
                ExecutiveAlertItem(
                    id="take_rate_optimal",
                    severity="success",
                    title=f"Gateway Take-Rate Healthy at {summary.blended_take_rate_pct}%",
                    description="Payment processing fees and statutory 18% GST are operating within contracted benchmark thresholds.",
                    action_label=None,
                    action_target=None,
                )
            )

        # 4. Reconciliation Health Alert
        if summary.health_score >= 90.0:
            alerts.append(
                ExecutiveAlertItem(
                    id="health_excellent",
                    severity="success",
                    title=f"Financial Integrity Score at {summary.health_score}%",
                    description="Three-layer matching confirms strong alignment between billing, gateway charges, and cleared bank funds.",
                    action_label="View Reconciliation Hub",
                    action_target="reconcile",
                )
            )
        else:
            alerts.append(
                ExecutiveAlertItem(
                    id="health_attention",
                    severity="critical" if summary.health_score < 70.0 else "warning",
                    title=f"Financial Integrity Score at {summary.health_score}% ({summary.health_status})",
                    description=f"Only {summary.matched_invoices_pct}% of invoices and {summary.settled_batches_pct}% of bank deposits are currently verified.",
                    action_label="Run Reconciliation",
                    action_target="reconcile",
                )
            )

        return alerts
