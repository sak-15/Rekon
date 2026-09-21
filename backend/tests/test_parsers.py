from decimal import Decimal
from datetime import datetime
import pytest

from app.models.gateway import GatewayEnum, PaymentMethodEnum, TxnStatusEnum
from app.models.invoice import InvoiceStatusEnum
from app.services.parsers import (
    InvoiceParser,
    GatewayParser,
    SettlementParser,
    BankStatementParser,
    clean_amount,
    parse_flexible_date,
)


def test_clean_amount_helper():
    """
    Verify clean_amount handles symbols, commas, and negative signs.
    """
    assert clean_amount("₹ 15,000.50") == Decimal("15000.50")
    assert clean_amount("$250.00") == Decimal("250.00")
    assert clean_amount("(50.00)") == Decimal("-50.00")
    assert clean_amount("-100.25") == Decimal("-100.25")
    assert clean_amount(None) == Decimal("0.00")


def test_parse_flexible_date_helper():
    """
    Verify parse_flexible_date handles ISO, Indian, and US date formats.
    """
    d1 = parse_flexible_date("2026-05-14")
    assert d1.year == 2026 and d1.month == 5 and d1.day == 14

    d2 = parse_flexible_date("14/05/2026 14:30:00")
    assert d2.day == 14 and d2.month == 5 and d2.hour == 14

    d3 = parse_flexible_date("14-05-2026")
    assert d3.day == 14 and d3.month == 5


def test_chargebee_invoice_parsing():
    """
    Verify parsing a Chargebee subscription invoice export.
    """
    csv_data = """Invoice Number,Customer ID,Customer Name,Customer Email,Plan Name,Total,Tax Amount,Status,Invoice Date,Due Date
INV-2026-001,cust_001,Acme Corp,billing@acme.com,Enterprise Annual,120000.00,21600.00,Paid,2026-04-01,2026-04-15
INV-2026-002,cust_002,Beta Labs,billing@betalabs.io,Pro Monthly,5000.00,900.00,Paid,2026-04-02,2026-04-16
"""
    result = InvoiceParser.parse(csv_data, org_id="org_test_123")
    assert result.total_rows == 2
    assert result.valid_count == 2
    assert result.error_count == 0

    inv1 = result.valid_records[0]
    assert inv1.invoice_no == "INV-2026-001"
    assert inv1.customer_name == "Acme Corp"
    assert inv1.amount == Decimal("120000.00")
    assert inv1.tax_amount == Decimal("21600.00")
    assert inv1.status == InvoiceStatusEnum.PAID
    assert inv1.currency == "INR"


def test_invoice_parsing_with_row_errors():
    """
    Verify that an invalid row is captured in errors without terminating the batch.
    """
    csv_data = """Invoice Number,Customer ID,Total,Invoice Date
INV-OK-1,cust_1,1500.00,2026-05-01
,cust_missing_inv,2000.00,2026-05-02
INV-OK-2,cust_2,3500.00,2026-05-03
"""
    result = InvoiceParser.parse(csv_data, org_id="org_test_123")
    assert result.total_rows == 3
    assert result.valid_count == 2
    assert result.error_count == 1
    assert result.errors[0].row_number == 3
    assert result.errors[0].field == "invoice_no"


def test_razorpay_transactions_parsing():
    """
    Verify auto-detection and parsing of Razorpay transaction reports.
    """
    csv_data = """payment_id,amount,status,method,fee,tax,created_at,email,contact,order_id
pay_Rzp001,15000.00,captured,upi,300.00,54.00,2026-05-10 11:20:00,user@domain.com,9876543210,INV-2026-001
pay_Rzp002,5000.00,captured,card,100.00,18.00,2026-05-11 15:45:00,client@domain.com,9876543211,INV-2026-002
"""
    result = GatewayParser.parse(csv_data, org_id="org_test_123")
    assert result.total_rows == 2
    assert result.valid_count == 2
    assert result.error_count == 0

    txn1 = result.valid_records[0]
    assert txn1.txn_id == "pay_Rzp001"
    assert txn1.gateway == GatewayEnum.RAZORPAY
    assert txn1.payment_method == PaymentMethodEnum.UPI
    assert txn1.amount == Decimal("15000.00")
    assert txn1.gateway_fee == Decimal("300.00")
    assert txn1.gateway_fee_gst == Decimal("54.00")
    # net = 15000 - 300 - 54 = 14646.00
    assert txn1.net_amount == Decimal("14646.00")
    assert txn1.invoice_ref == "INV-2026-001"


def test_stripe_transactions_parsing():
    """
    Verify auto-detection and parsing of Stripe charge reports.
    """
    csv_data = """id,Description,Amount,Fee,Net,Currency,Created (UTC),Customer Email,Payment Method Type
ch_Stripe001,INV-2026-003,25000.00,500.00,24500.00,inr,2026-05-12 09:15:00,alex@stripeuser.com,card
"""
    result = GatewayParser.parse(csv_data, org_id="org_test_123")
    assert result.total_rows == 1
    assert result.valid_count == 1

    txn = result.valid_records[0]
    assert txn.txn_id == "ch_Stripe001"
    assert txn.gateway == GatewayEnum.STRIPE
    assert txn.payment_method == PaymentMethodEnum.CARD
    assert txn.amount == Decimal("25000.00")
    assert txn.gateway_fee == Decimal("500.00")
    assert txn.net_amount == Decimal("24500.00")


def test_settlement_batch_and_lines_parsing():
    """
    Verify settlement batch parsing and itemized line extraction.
    """
    csv_data = """settlement_id,entity_id,amount,fee,tax,type,utr,date
setl_RzpBatch99,pay_Rzp001,15000.00,300.00,54.00,payment,UTR_RZP_998877,2026-05-12
setl_RzpBatch99,pay_Rzp002,5000.00,100.00,18.00,payment,UTR_RZP_998877,2026-05-12
"""
    result = SettlementParser.parse(csv_data, org_id="org_test_123", gateway=GatewayEnum.RAZORPAY)
    assert result.total_rows == 2
    assert result.valid_count == 1  # 1 batch containing 2 lines

    batch = result.valid_records[0]
    assert batch.batch_id == "setl_RzpBatch99"
    assert batch.utr_number == "UTR_RZP_998877"
    assert batch.gross_amount == Decimal("20000.00")
    assert batch.total_fees == Decimal("400.00")
    assert batch.total_gst == Decimal("72.00")
    # net = 20000 - 400 - 72 = 19528.00
    assert batch.net_amount == Decimal("19528.00")
    assert len(batch.lines) == 2


def test_bank_statement_parsing():
    """
    Verify bank statement parsing with UTR narrations and deposits.
    """
    csv_data = """Transaction Date,Narration,Credit Amount,Debit Amount,Chq / Ref No
14/05/2026,CMS/RAZORPAY SETTLEMENT BATCH 2026-05-12 / UTR_RZP_998877,19528.00,0.00,UTR_RZP_998877
15/05/2026,AWS CLOUD SERVICES INDIA,0.00,4500.00,CHQ100234
"""
    result = BankStatementParser.parse(csv_data, org_id="org_test_123", bank_name="HDFC Bank")
    assert result.total_rows == 2
    assert result.valid_count == 2

    credit = result.valid_records[0]
    assert credit.credit_amount == Decimal("19528.00")
    assert credit.reference_no == "UTR_RZP_998877"
    assert "RAZORPAY" in credit.narration

