"""
Gateway Transactions CSV Parser (Razorpay and Stripe).

Auto-detects gateway format from column headers and standardizes records into
the canonical GatewayTransaction database model.
"""

import io
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple
import pandas as pd

from app.models.gateway import (
    GatewayTransaction,
    GatewayEnum,
    PaymentMethodEnum,
    TxnStatusEnum,
    SettlementStatusEnum,
)
from app.models.invoice import ReconciliationStatusEnum
from app.services.parsers.base import (
    ParseResult,
    RowError,
    clean_amount,
    clean_string,
    parse_flexible_date,
)


class GatewayParser:
    """
    Parses and normalizes payment transaction reports from Razorpay and Stripe.
    """

    @staticmethod
    def detect_gateway(col_names: list) -> GatewayEnum:
        """
        Inspects CSV headers to identify the originating payment gateway.
        """
        normalized = [str(c).strip().lower() for c in col_names]

        # Razorpay signatures
        razorpay_signatures = {"payment_id", "payment id", "razorpay_payment_id", "order_id", "order id"}
        if any(sig in normalized for sig in razorpay_signatures):
            return GatewayEnum.RAZORPAY

        # Stripe signatures
        stripe_signatures = {"balance transaction id", "charge id", "payment intent id", "customer email", "net"}
        if any(sig in normalized for sig in stripe_signatures):
            return GatewayEnum.STRIPE

        # Fallback heuristic: check if 'id' starts with 'ch_' or 'pi_'
        return GatewayEnum.RAZORPAY

    @classmethod
    def _parse_razorpay(
        cls,
        df: pd.DataFrame,
        org_id: str,
        upload_job_id: Optional[str],
        result: ParseResult[GatewayTransaction],
    ):
        col_map = {str(col).strip().lower(): col for col in df.columns}

        c_txn_id = (
            col_map.get("payment_id") or col_map.get("payment id") or
            col_map.get("id") or col_map.get("txn_id")
        )
        c_amount = col_map.get("amount") or col_map.get("gross amount") or col_map.get("total")
        c_fee = col_map.get("fee") or col_map.get("fees") or col_map.get("mdr")
        c_tax = col_map.get("tax") or col_map.get("fee_tax") or col_map.get("gst")
        c_method = col_map.get("method") or col_map.get("payment method") or col_map.get("payment_method")
        c_status = col_map.get("status") or col_map.get("payment status")
        c_created = col_map.get("created_at") or col_map.get("created at") or col_map.get("date")
        c_email = col_map.get("email") or col_map.get("customer email")
        c_contact = col_map.get("contact") or col_map.get("phone")
        c_inv_ref = (
            col_map.get("notes[invoice_id]") or col_map.get("notes[invoice_no]") or
            col_map.get("invoice_id") or col_map.get("order_id") or col_map.get("description")
        )
        c_curr = col_map.get("currency") or col_map.get("curr")

        if not c_txn_id or not c_amount:
            result.errors.append(
                RowError(
                    row_number=0,
                    field="header",
                    message="Missing required columns ('payment_id' or 'amount') for Razorpay",
                )
            )
            return

        for index, row in df.iterrows():
            row_num = index + 2
            try:
                txn_id = clean_string(row.get(c_txn_id))
                if not txn_id:
                    result.errors.append(
                        RowError(row_number=row_num, field="txn_id", message="Payment ID is empty", raw_data=row.to_dict())
                    )
                    continue

                amount = clean_amount(row.get(c_amount))
                fee = clean_amount(row.get(c_fee)) if c_fee else Decimal("0.00")
                tax = clean_amount(row.get(c_tax)) if c_tax else Decimal("0.00")
                net = amount - fee - tax

                # Date parsing
                created_at = datetime.utcnow()
                if c_created and clean_string(row.get(c_created)):
                    try:
                        created_at = parse_flexible_date(row.get(c_created))
                    except Exception as e:
                        result.errors.append(
                            RowError(row_number=row_num, field="created_at", message=f"Invalid date: {str(e)}")
                        )
                        continue

                # Payment method normalization
                method = PaymentMethodEnum.OTHER
                if c_method and clean_string(row.get(c_method)):
                    m = str(row.get(c_method)).strip().lower()
                    if "upi" in m:
                        method = PaymentMethodEnum.UPI
                    elif "card" in m or "credit" in m or "debit" in m:
                        method = PaymentMethodEnum.CARD
                    elif "nach" in m or "enach" in m or "mandate" in m:
                        method = PaymentMethodEnum.ENACH
                    elif "netbanking" in m or "net_banking" in m:
                        method = PaymentMethodEnum.NETBANKING
                    elif "wallet" in m:
                        method = PaymentMethodEnum.WALLET

                # Transaction Status normalization
                status = TxnStatusEnum.CAPTURED
                if c_status and clean_string(row.get(c_status)):
                    st = str(row.get(c_status)).strip().lower()
                    if "fail" in st:
                        status = TxnStatusEnum.FAILED
                    elif "refund" in st:
                        status = TxnStatusEnum.REFUNDED
                    elif "dispute" in st:
                        status = TxnStatusEnum.DISPUTED
                    else:
                        status = TxnStatusEnum.CAPTURED

                currency = (clean_string(row.get(c_curr)) or "INR").upper()[:3]

                txn = GatewayTransaction(
                    org_id=org_id,
                    upload_job_id=upload_job_id,
                    txn_id=txn_id,
                    gateway=GatewayEnum.RAZORPAY,
                    payment_method=method,
                    invoice_ref=clean_string(row.get(c_inv_ref)) if c_inv_ref else None,
                    customer_email=clean_string(row.get(c_email)) if c_email else None,
                    customer_contact=clean_string(row.get(c_contact)) if c_contact else None,
                    amount=amount,
                    currency=currency,
                    status=status,
                    gateway_fee=fee,
                    gateway_fee_gst=tax,
                    net_amount=net,
                    captured_at=created_at,
                    settlement_status=SettlementStatusEnum.UNSETTLED,
                    reconciliation_status=ReconciliationStatusEnum.UNMATCHED,
                )
                result.valid_records.append(txn)

            except Exception as e:
                result.errors.append(
                    RowError(row_number=row_num, field="general", message=f"Row error: {str(e)}", raw_data=row.to_dict())
                )

    @classmethod
    def _parse_stripe(
        cls,
        df: pd.DataFrame,
        org_id: str,
        upload_job_id: Optional[str],
        result: ParseResult[GatewayTransaction],
    ):
        col_map = {str(col).strip().lower(): col for col in df.columns}

        c_txn_id = (
            col_map.get("id") or col_map.get("balance transaction id") or
            col_map.get("charge id") or col_map.get("payment intent id")
        )
        c_amount = col_map.get("amount") or col_map.get("gross")
        c_fee = col_map.get("fee")
        c_net = col_map.get("net")
        c_status = col_map.get("status")
        c_created = col_map.get("created (utc)") or col_map.get("created") or col_map.get("date")
        c_email = col_map.get("customer email") or col_map.get("email")
        c_inv_ref = col_map.get("description") or col_map.get("invoice_id") or col_map.get("invoice")
        c_curr = col_map.get("currency")
        c_method = col_map.get("payment method type") or col_map.get("card brand") or col_map.get("source")

        if not c_txn_id or not c_amount:
            result.errors.append(
                RowError(
                    row_number=0,
                    field="header",
                    message="Missing required columns ('id' or 'amount') for Stripe",
                )
            )
            return

        for index, row in df.iterrows():
            row_num = index + 2
            try:
                txn_id = clean_string(row.get(c_txn_id))
                if not txn_id:
                    result.errors.append(
                        RowError(row_number=row_num, field="txn_id", message="Stripe ID is empty", raw_data=row.to_dict())
                    )
                    continue

                amount = clean_amount(row.get(c_amount))
                fee = clean_amount(row.get(c_fee)) if c_fee else Decimal("0.00")
                net = clean_amount(row.get(c_net)) if c_net else (amount - fee)

                # For Stripe in India, GST is typically 18% of the gateway fee
                # If GST is not explicitly itemized in standard export, we calculate standard 18% GST portion:
                # fee_before_gst = fee / 1.18; gst = fee - fee_before_gst
                fee_gst = Decimal("0.00")
                if fee > Decimal("0.00"):
                    # Stripe India invoices GST on fees separately or bundled in fee
                    fee_gst = (fee * Decimal("0.18")).quantize(Decimal("0.01"))

                created_at = datetime.utcnow()
                if c_created and clean_string(row.get(c_created)):
                    try:
                        created_at = parse_flexible_date(row.get(c_created))
                    except Exception as e:
                        result.errors.append(
                            RowError(row_number=row_num, field="created_at", message=f"Invalid date: {str(e)}")
                        )
                        continue

                # Method
                method = PaymentMethodEnum.CARD
                if c_method and clean_string(row.get(c_method)):
                    m = str(row.get(c_method)).strip().lower()
                    if "upi" in m:
                        method = PaymentMethodEnum.UPI
                    elif "card" in m or "visa" in m or "mastercard" in m:
                        method = PaymentMethodEnum.CARD

                # Status
                status = TxnStatusEnum.CAPTURED
                if c_status and clean_string(row.get(c_status)):
                    st = str(row.get(c_status)).strip().lower()
                    if "fail" in st:
                        status = TxnStatusEnum.FAILED
                    elif "refund" in st:
                        status = TxnStatusEnum.REFUNDED
                    elif "dispute" in st:
                        status = TxnStatusEnum.DISPUTED

                currency = (clean_string(row.get(c_curr)) or "INR").upper()[:3]

                txn = GatewayTransaction(
                    org_id=org_id,
                    upload_job_id=upload_job_id,
                    txn_id=txn_id,
                    gateway=GatewayEnum.STRIPE,
                    payment_method=method,
                    invoice_ref=clean_string(row.get(c_inv_ref)) if c_inv_ref else None,
                    customer_email=clean_string(row.get(c_email)) if c_email else None,
                    customer_contact=None,
                    amount=amount,
                    currency=currency,
                    status=status,
                    gateway_fee=fee,
                    gateway_fee_gst=fee_gst,
                    net_amount=net,
                    captured_at=created_at,
                    settlement_status=SettlementStatusEnum.UNSETTLED,
                    reconciliation_status=ReconciliationStatusEnum.UNMATCHED,
                )
                result.valid_records.append(txn)

            except Exception as e:
                result.errors.append(
                    RowError(row_number=row_num, field="general", message=f"Row error: {str(e)}", raw_data=row.to_dict())
                )

    @classmethod
    def parse(
        cls,
        csv_content: str,
        org_id: str,
        upload_job_id: Optional[str] = None,
        force_gateway: Optional[GatewayEnum] = None,
    ) -> ParseResult[GatewayTransaction]:
        """
        Ingests a gateway transaction CSV with auto-detection of Razorpay or Stripe.
        """
        result = ParseResult[GatewayTransaction]()

        try:
            df = pd.read_csv(io.StringIO(csv_content), dtype=str)
        except Exception as e:
            result.errors.append(
                RowError(row_number=0, field="file", message=f"Failed to read CSV: {str(e)}")
            )
            return result

        result.total_rows = len(df)
        if df.empty:
            return result

        gateway = force_gateway or cls.detect_gateway(list(df.columns))

        if gateway == GatewayEnum.STRIPE:
            cls._parse_stripe(df, org_id, upload_job_id, result)
        else:
            cls._parse_razorpay(df, org_id, upload_job_id, result)

        return result

