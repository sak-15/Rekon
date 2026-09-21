import io
import pytest

from app.models.invoice import Invoice
from app.models.gateway import GatewayTransaction
from app.models.settlement import SettlementBatch
from app.models.bank import BankCredit


def get_auth_token(client):
    """
    Helper to register an organisation and return an access token.
    """
    res = client.post(
        "/api/auth/register",
        json={
            "org_name": "Acme SaaS",
            "org_slug": "acme-saas",
            "email": "finance@acmesaas.com",
            "password": "Password123!",
        },
    )
    return res.json()["access_token"]


def test_upload_invoices_api_end_to_end(client):
    """
    Test invoice CSV upload, parsing, database storage, and deduplication.
    """
    token = get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    csv_content = b"""Invoice Number,Customer ID,Customer Name,Plan Name,Total,Invoice Date
INV-101,cust_1,Alpha Corp,Pro Monthly,5000.00,2026-05-01
INV-102,cust_2,Beta Corp,Enterprise,25000.00,2026-05-02
"""
    files = {"file": ("invoices.csv", io.BytesIO(csv_content), "text/csv")}
    response = client.post("/api/uploads/invoices", files=files, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert "Successfully ingested 2 invoices" in data["message"]
    assert data["upload_job"]["valid_rows"] == 2
    assert data["upload_job"]["status"] == "completed"

    # Re-upload the exact same CSV -> should skip duplicates gracefully
    files_dup = {"file": ("invoices.csv", io.BytesIO(csv_content), "text/csv")}
    dup_res = client.post("/api/uploads/invoices", files=files_dup, headers=headers)
    assert dup_res.status_code == 201
    dup_data = dup_res.json()
    assert dup_data["upload_job"]["valid_rows"] == 0
    assert dup_data["upload_job"]["error_rows"] == 2  # 2 duplicates skipped


def test_upload_gateway_txns_api_end_to_end(client):
    """
    Test gateway transaction upload with Razorpay auto-detection.
    """
    token = get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    csv_content = b"""payment_id,amount,status,method,fee,tax,created_at,order_id
pay_Test001,10000.00,captured,upi,200.00,36.00,2026-05-05 10:00:00,INV-101
"""
    files = {"file": ("rzp_txns.csv", io.BytesIO(csv_content), "text/csv")}
    res = client.post("/api/uploads/gateway-txns", files=files, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["upload_job"]["valid_rows"] == 1
    assert data["upload_job"]["status"] == "completed"


def test_upload_settlements_api_end_to_end(client):
    """
    Test settlement batches and itemized lines ingestion.
    """
    token = get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    csv_content = b"""settlement_id,entity_id,amount,fee,tax,type,utr,date
setl_Test99,pay_Test001,10000.00,200.00,36.00,payment,UTR_BATCH_99,2026-05-06
"""
    files = {"file": ("settlements.csv", io.BytesIO(csv_content), "text/csv")}
    res = client.post("/api/uploads/settlements", files=files, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["upload_job"]["valid_rows"] == 1


def test_upload_bank_statements_api_end_to_end(client):
    """
    Test bank statement upload and listing upload jobs.
    """
    token = get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    csv_content = b"""Transaction Date,Narration,Credit Amount,Debit Amount,Chq / Ref No
07/05/2026,RAZORPAY SETTLEMENT UTR_BATCH_99,9764.00,0.00,UTR_BATCH_99
"""
    files = {"file": ("bank.csv", io.BytesIO(csv_content), "text/csv")}
    res = client.post("/api/uploads/bank-statements", files=files, headers=headers)
    assert res.status_code == 201

    # Now verify GET /api/uploads lists this job
    list_res = client.get("/api/uploads", headers=headers)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert list_data["items"][0]["file_type"] == "bank_statement"


def test_unauthenticated_upload_rejected(client):
    """
    Verify upload endpoints require Bearer JWT authentication.
    """
    csv_content = b"header1,header2\nval1,val2"
    files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    res = client.post("/api/uploads/invoices", files=files)
    assert res.status_code == 401
