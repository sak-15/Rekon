"""
Invoice CSV Parser (Chargebee, Zoho Subscriptions, and Canonical SaaS formats).

Normalizes subscription invoice exports into canonical Invoice database models.
"""

import io
from decimal import Decimal
from typing import Dict, Any, Optional
import pandas as pd

from app.models.invoice import Invoice, InvoiceStatusEnum, ReconciliationStatusEnum
from app.services.parsers.base import (
    ParseResult,
    RowError,
    clean_amount,
    clean_string,
    parse_flexible_date,
)


class InvoiceParser:
    """
    Parses and sanitizes CSV exports from billing systems like Chargebee and Zoho Subscriptions.
    """

    # Flexible column name mapping (normalized to lowercase with stripped spaces)
    COLUMN_ALIASES = {
        "invoice_no": [
            "invoice number", "invoice_number", "invoice no", "invoice_no",
            "invoice id", "invoice_id", "number", "id"
        ],
        "customer_id": [
            "customer id", "customer_id", "client id", "client_id",
            "customer number", "account id"
        ],
        "customer_name": [
            "customer name", "customer_name", "first name", "company name",
            "client name", "name", "account name"
        ],
        "customer_email": [
            "customer email", "customer_email", "email", "billing email"
        ],
        "plan_name": [
            "plan name", "plan_name", "plan id", "plan_id", "plan",
            "subscription id", "description", "item name"
        ],
        "amount": [
            "total", "amount", "invoice amount", "subtotal", "gross amount", "total (inr)"
        ],
        "tax_amount": [
            "tax", "tax amount", "tax_amount", "gst", "vat", "tax (inr)"
        ],
        "currency": [
            "currency", "currency code", "curr"
        ],
        "status": [
            "status", "invoice status", "payment status"
        ],
        "invoice_date": [
            "invoice date", "invoice_date", "date", "created at", "issue date", "billing date"
        ],
        "due_date": [
            "due date", "due_date", "payment due date"
        ],
        "billing_period_start": [
            "period start", "period_start", "billing start", "billing_start_date"
        ],
        "billing_period_end": [
            "period end", "period_end", "billing end", "billing_end_date"
        ],
    }

    @classmethod
    def _find_column(cls, df_columns: Dict[str, str], target_field: str) -> Optional[str]:
        """
        Matches standard target field name against aliases present in the DataFrame.
        """
        aliases = cls.COLUMN_ALIASES.get(target_field, [])
        for alias in aliases:
            if alias in df_columns:
                return df_columns[alias]
        return None

    @classmethod
    def parse(
        cls,
        csv_content: str,
        org_id: str,
        upload_job_id: Optional[str] = None,
        source_system: str = "chargebee",
    ) -> ParseResult[Invoice]:
        """
        Parses a CSV string into a ParseResult containing validated Invoice models.
        """
        result = ParseResult[Invoice]()

        try:
            df = pd.read_csv(io.StringIO(csv_content), dtype=str)
        except Exception as e:
            result.errors.append(
                RowError(
                    row_number=0,
                    field="file",
                    message=f"Failed to read CSV: {str(e)}",
                )
            )
            return result

        result.total_rows = len(df)
        if df.empty:
            return result

        # Map normalized column headers
        col_map = {str(col).strip().lower(): col for col in df.columns}

        # Resolve column names
        c_inv_no = cls._find_column(col_map, "invoice_no")
        c_cust_id = cls._find_column(col_map, "customer_id")
        c_cust_name = cls._find_column(col_map, "customer_name")
        c_cust_email = cls._find_column(col_map, "customer_email")
        c_plan = cls._find_column(col_map, "plan_name")
        c_amount = cls._find_column(col_map, "amount")
        c_tax = cls._find_column(col_map, "tax_amount")
        c_curr = cls._find_column(col_map, "currency")
        c_status = cls._find_column(col_map, "status")
        c_inv_date = cls._find_column(col_map, "invoice_date")
        c_due_date = cls._find_column(col_map, "due_date")
        c_start = cls._find_column(col_map, "billing_period_start")
        c_end = cls._find_column(col_map, "billing_period_end")

        if not c_inv_no:
            result.errors.append(
                RowError(
                    row_number=0,
                    field="invoice_no",
                    message="Required 'Invoice Number' column could not be found in CSV",
                )
            )
            return result

        if not c_amount:
            result.errors.append(
                RowError(
                    row_number=0,
                    field="amount",
                    message="Required 'Amount' or 'Total' column could not be found in CSV",
                )
            )
            return result

        # Iterate through rows and validate
        for index, row in df.iterrows():
            row_num = index + 2  # 1-indexed including header
            try:
                raw_inv_no = clean_string(row.get(c_inv_no))
                if not raw_inv_no:
                    result.errors.append(
                        RowError(
                            row_number=row_num,
                            field="invoice_no",
                            message="Invoice number cannot be empty",
                            raw_data=row.to_dict(),
                        )
                    )
                    continue

                # Parse Amount
                try:
                    amount = clean_amount(row.get(c_amount))
                except Exception as e:
                    result.errors.append(
                        RowError(
                            row_number=row_num,
                            field="amount",
                            message=f"Invalid invoice amount: {str(e)}",
                            raw_data=row.to_dict(),
                        )
                    )
                    continue

                # Parse Tax Amount
                tax_amount = Decimal("0.00")
                if c_tax and row.get(c_tax):
                    try:
                        tax_amount = clean_amount(row.get(c_tax))
                    except Exception:
                        tax_amount = Decimal("0.00")

                # Parse Invoice Date
                if c_inv_date and clean_string(row.get(c_inv_date)):
                    try:
                        invoice_date = parse_flexible_date(row.get(c_inv_date))
                    except Exception as e:
                        result.errors.append(
                            RowError(
                                row_number=row_num,
                                field="invoice_date",
                                message=f"Invalid invoice date: {str(e)}",
                                raw_data=row.to_dict(),
                            )
                        )
                        continue
                else:
                    # Fallback to current timestamp if missing
                    from datetime import datetime
                    invoice_date = datetime.utcnow()

                # Parse Due Date
                due_date = None
                if c_due_date and clean_string(row.get(c_due_date)):
                    try:
                        due_date = parse_flexible_date(row.get(c_due_date))
                    except Exception:
                        due_date = None

                # Parse Billing Periods
                period_start = None
                if c_start and clean_string(row.get(c_start)):
                    try:
                        period_start = parse_flexible_date(row.get(c_start)).date()
                    except Exception:
                        period_start = None

                period_end = None
                if c_end and clean_string(row.get(c_end)):
                    try:
                        period_end = parse_flexible_date(row.get(c_end)).date()
                    except Exception:
                        period_end = None

                # Status normalization
                status = InvoiceStatusEnum.PAID
                if c_status and clean_string(row.get(c_status)):
                    raw_st = str(row.get(c_status)).strip().lower()
                    if "void" in raw_st or "cancel" in raw_st:
                        status = InvoiceStatusEnum.VOID
                    elif "fail" in raw_st:
                        status = InvoiceStatusEnum.FAILED
                    elif "pend" in raw_st or "open" in raw_st or "unpaid" in raw_st:
                        status = InvoiceStatusEnum.PENDING
                    else:
                        status = InvoiceStatusEnum.PAID

                # Customer ID fallback
                customer_id = clean_string(row.get(c_cust_id)) if c_cust_id else None
                if not customer_id:
                    customer_id = clean_string(row.get(c_cust_email)) or "unknown_customer"

                # Currency
                currency = (clean_string(row.get(c_curr)) or "INR").upper()[:3]

                invoice = Invoice(
                    org_id=org_id,
                    upload_job_id=upload_job_id,
                    invoice_no=raw_inv_no,
                    customer_id=customer_id,
                    customer_name=clean_string(row.get(c_cust_name)) if c_cust_name else None,
                    customer_email=clean_string(row.get(c_cust_email)) if c_cust_email else None,
                    plan_name=clean_string(row.get(c_plan)) if c_plan else None,
                    amount=amount,
                    tax_amount=tax_amount,
                    currency=currency,
                    status=status,
                    invoice_date=invoice_date,
                    due_date=due_date,
                    billing_period_start=period_start,
                    billing_period_end=period_end,
                    source_system=source_system,
                    reconciliation_status=ReconciliationStatusEnum.UNMATCHED,
                )
                result.valid_records.append(invoice)

            except Exception as e:
                result.errors.append(
                    RowError(
                        row_number=row_num,
                        field="general",
                        message=f"Row processing error: {str(e)}",
                        raw_data=row.to_dict(),
                    )
                )

        return result

