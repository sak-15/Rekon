"""
Settlement CSV Parser (Razorpay Settlements and Stripe Payouts).

Parses itemized settlement reports, grouping lines into SettlementBatch headers
with individual SettlementLine child records.
"""

import io
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
import pandas as pd

from app.models.gateway import GatewayEnum
from app.models.invoice import ReconciliationStatusEnum
from app.models.settlement import (
    SettlementBatch,
    SettlementLine,
    SettlementLineTypeEnum,
)
from app.services.parsers.base import (
    ParseResult,
    RowError,
    clean_amount,
    clean_string,
    parse_flexible_date,
)


class SettlementParser:
    """
    Parses gateway settlement files into batches and itemized settlement lines.
    """

    @classmethod
    def parse(
        cls,
        csv_content: str,
        org_id: str,
        upload_job_id: Optional[str] = None,
        gateway: GatewayEnum = GatewayEnum.RAZORPAY,
    ) -> ParseResult[SettlementBatch]:
        result = ParseResult[SettlementBatch]()

        try:
            df = pd.read_csv(io.StringIO(csv_content), dtype=str)
        except Exception as e:
            result.errors.append(RowError(row_number=0, field="file", message=f"Failed to read CSV: {str(e)}"))
            return result

        result.total_rows = len(df)
        if df.empty:
            return result

        col_map = {str(col).strip().lower(): col for col in df.columns}

        c_batch_id = (
            col_map.get("settlement_id") or col_map.get("settlement id") or
            col_map.get("payout_id") or col_map.get("payout id") or col_map.get("batch_id")
        )
        c_txn_ref = (
            col_map.get("payment_id") or col_map.get("entity_id") or
            col_map.get("txn_id") or col_map.get("transaction id") or col_map.get("id")
        )
        c_amount = col_map.get("amount") or col_map.get("credit") or col_map.get("net")
        c_fee = col_map.get("fee") or col_map.get("fees") or col_map.get("mdr")
        c_tax = col_map.get("tax") or col_map.get("gst")
        c_type = col_map.get("type") or col_map.get("entity_type")
        c_utr = col_map.get("utr") or col_map.get("utr_number") or col_map.get("reference")
        c_date = col_map.get("settlement_date") or col_map.get("created_at") or col_map.get("date")

        if not c_batch_id:
            # If batch_id column is missing, generate a default batch ID from date or upload
            c_batch_id = None

        if not c_amount:
            result.errors.append(
                RowError(row_number=0, field="header", message="Missing required amount column in settlement file")
            )
            return result

        # Group lines by batch_id
        batches_map: Dict[str, SettlementBatch] = {}
        batch_lines_map: Dict[str, List[SettlementLine]] = {}

        for index, row in df.iterrows():
            row_num = index + 2
            try:
                # Determine batch ID
                batch_id_val = clean_string(row.get(c_batch_id)) if c_batch_id else None
                if not batch_id_val:
                    # Fallback batch identifier
                    batch_id_val = f"batch_{upload_job_id or 'default'}"

                txn_ref = clean_string(row.get(c_txn_ref)) if c_txn_ref else f"ref_{row_num}"
                amount = clean_amount(row.get(c_amount))
                fee = clean_amount(row.get(c_fee)) if c_fee else Decimal("0.00")
                tax = clean_amount(row.get(c_tax)) if c_tax else Decimal("0.00")
                utr = clean_string(row.get(c_utr)) if c_utr else None

                # Date parsing
                settle_date = datetime.utcnow()
                if c_date and clean_string(row.get(c_date)):
                    try:
                        settle_date = parse_flexible_date(row.get(c_date))
                    except Exception:
                        pass

                # Line type
                line_type = SettlementLineTypeEnum.PAYMENT
                if c_type and clean_string(row.get(c_type)):
                    t = str(row.get(c_type)).strip().lower()
                    if "refund" in t:
                        line_type = SettlementLineTypeEnum.REFUND
                    elif "dispute" in t or "chargeback" in t:
                        line_type = SettlementLineTypeEnum.CHARGEBACK
                    elif "adjust" in t:
                        line_type = SettlementLineTypeEnum.ADJUSTMENT

                # Initialize batch if not encountered yet
                if batch_id_val not in batches_map:
                    batches_map[batch_id_val] = SettlementBatch(
                        org_id=org_id,
                        upload_job_id=upload_job_id,
                        batch_id=batch_id_val,
                        gateway=gateway,
                        settlement_date=settle_date,
                        gross_amount=Decimal("0.00"),
                        total_fees=Decimal("0.00"),
                        total_gst=Decimal("0.00"),
                        total_refunds=Decimal("0.00"),
                        total_adjustments=Decimal("0.00"),
                        net_amount=Decimal("0.00"),
                        currency="INR",
                        utr_number=utr,
                        reconciliation_status=ReconciliationStatusEnum.UNMATCHED,
                    )
                    batch_lines_map[batch_id_val] = []

                batch = batches_map[batch_id_val]
                if utr and not batch.utr_number:
                    batch.utr_number = utr

                # Accumulate batch totals
                if line_type == SettlementLineTypeEnum.REFUND:
                    batch.total_refunds += abs(amount)
                elif line_type == SettlementLineTypeEnum.ADJUSTMENT:
                    batch.total_adjustments += amount
                else:
                    batch.gross_amount += amount

                batch.total_fees += fee
                batch.total_gst += tax

                # Create SettlementLine
                line = SettlementLine(
                    org_id=org_id,
                    txn_ref=txn_ref,
                    line_type=line_type,
                    amount=amount,
                    fee=fee,
                    tax=tax,
                )
                batch_lines_map[batch_id_val].append(line)

            except Exception as e:
                result.errors.append(
                    RowError(row_number=row_num, field="general", message=f"Settlement line error: {str(e)}", raw_data=row.to_dict())
                )

        # Finalize batch net amounts and associate lines
        for b_id, batch in batches_map.items():
            # net = gross - total_fees - total_gst - refunds + adjustments
            calculated_net = batch.gross_amount - batch.total_fees - batch.total_gst - batch.total_refunds + batch.total_adjustments
            batch.net_amount = calculated_net
            batch.lines = batch_lines_map[b_id]
            result.valid_records.append(batch)

        return result

