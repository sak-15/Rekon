"""
Bank Statement CSV Parser (HDFC, ICICI, Axis, and generic Indian bank formats).

Extracts credits, debits, UTR references, and narrations into canonical BankCredit models.
"""

import io
from datetime import datetime
from decimal import Decimal
from typing import Optional
import pandas as pd

from app.models.bank import BankCredit
from app.models.invoice import ReconciliationStatusEnum
from app.services.parsers.base import (
    ParseResult,
    RowError,
    clean_amount,
    clean_string,
    parse_flexible_date,
)


class BankStatementParser:
    """
    Parses bank statement CSVs from major Indian banks and generic banking portals.
    """

    @classmethod
    def parse(
        cls,
        csv_content: str,
        org_id: str,
        upload_job_id: Optional[str] = None,
        bank_name: Optional[str] = None,
    ) -> ParseResult[BankCredit]:
        result = ParseResult[BankCredit]()

        try:
            df = pd.read_csv(io.StringIO(csv_content), dtype=str)
        except Exception as e:
            result.errors.append(RowError(row_number=0, field="file", message=f"Failed to read CSV: {str(e)}"))
            return result

        result.total_rows = len(df)
        if df.empty:
            return result

        col_map = {str(col).strip().lower(): col for col in df.columns}

        c_date = (
            col_map.get("date") or col_map.get("transaction date") or
            col_map.get("txn date") or col_map.get("value date") or col_map.get("tran date")
        )
        c_val_date = col_map.get("value date") or col_map.get("value_date")
        c_narration = (
            col_map.get("narration") or col_map.get("description") or
            col_map.get("particulars") or col_map.get("transaction remarks") or col_map.get("remarks")
        )
        c_credit = (
            col_map.get("credit") or col_map.get("deposit") or
            col_map.get("credit amount") or col_map.get("cr") or col_map.get("deposit amount (inr)")
        )
        c_debit = (
            col_map.get("debit") or col_map.get("withdrawal") or
            col_map.get("debit amount") or col_map.get("dr") or col_map.get("withdrawal amount (inr)")
        )
        c_ref = (
            col_map.get("chq / ref no") or col_map.get("chq/ref no.") or
            col_map.get("reference") or col_map.get("ref no") or col_map.get("cheque no") or col_map.get("utr")
        )
        c_balance = col_map.get("balance") or col_map.get("closing balance")

        if not c_narration and not c_credit:
            result.errors.append(
                RowError(
                    row_number=0,
                    field="header",
                    message="Missing required bank columns ('narration' and 'credit')",
                )
            )
            return result

        for index, row in df.iterrows():
            row_num = index + 2
            try:
                narration = clean_string(row.get(c_narration)) if c_narration else "Unknown narration"
                if not narration:
                    # Skip blank rows in bank statements
                    continue

                credit = clean_amount(row.get(c_credit)) if c_credit else Decimal("0.00")
                debit = clean_amount(row.get(c_debit)) if c_debit else Decimal("0.00")

                # Parse Transaction Date
                txn_date = datetime.utcnow()
                if c_date and clean_string(row.get(c_date)):
                    try:
                        txn_date = parse_flexible_date(row.get(c_date))
                    except Exception as e:
                        result.errors.append(
                            RowError(row_number=row_num, field="date", message=f"Invalid date: {str(e)}")
                        )
                        continue

                # Value Date
                val_date = None
                if c_val_date and clean_string(row.get(c_val_date)):
                    try:
                        val_date = parse_flexible_date(row.get(c_val_date))
                    except Exception:
                        val_date = None

                # Balance
                running_balance = None
                if c_balance and clean_string(row.get(c_balance)):
                    try:
                        running_balance = clean_amount(row.get(c_balance))
                    except Exception:
                        running_balance = None

                ref_no = clean_string(row.get(c_ref)) if c_ref else None

                credit_entry = BankCredit(
                    org_id=org_id,
                    upload_job_id=upload_job_id,
                    transaction_date=txn_date,
                    value_date=val_date,
                    narration=narration,
                    credit_amount=credit,
                    debit_amount=debit,
                    running_balance=running_balance,
                    reference_no=ref_no,
                    bank_name=bank_name or "Bank",
                    reconciliation_status=ReconciliationStatusEnum.UNMATCHED,
                )
                result.valid_records.append(credit_entry)

            except Exception as e:
                result.errors.append(
                    RowError(row_number=row_num, field="general", message=f"Row error: {str(e)}", raw_data=row.to_dict())
                )

        return result

