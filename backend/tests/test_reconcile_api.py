"""
Integration tests for Reconciliation REST API.
Tests triggering the three-layer pipeline, querying historical runs,
fetching match telemetry, filtering by layer and status, and multi-tenant security.
"""

import io
from decimal import Decimal
import pytest

from app.models import (
    Invoice,
    GatewayTransaction,
    SettlementBatch,
    SettlementLine,
    BankCredit,
    ReconciliationRun,
    ReconciliationMatch,
    ReconciliationLayerEnum,
    MatchStatusEnum,
)


def register_tenant(client, slug: str, email: str) -> str:
    """Helper to register an organisation and return a JWT access token."""
    res = client.post(
        "/api/auth/register",
        json={
            "org_name": f"Org {slug}",
            "org_slug": slug,
            "email": email,
            "password": "Password123!",
        },
    )
    return res.json()["access_token"]


def test_reconcile_api_end_to_end(client):
    """
    Test uploading data across all three layers, triggering a reconciliation run,
    and verifying run telemetry and match query endpoints.
    """
    token = register_tenant(client, "acme-reconcile", "finance@acmereconcile.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Ingest Invoices
    invoice_csv = b"""Invoice Number,Customer ID,Customer Name,Customer Email,Total,Invoice Date
INV-E2E-1,cust_10,Enterprise Client,billing@enterprise.com,10000.00,2026-05-01
INV-E2E-2,cust_20,Startup Client,admin@startup.io,5000.00,2026-05-02
"""
    res_inv = client.post(
        "/api/uploads/invoices",
        files={"file": ("invoices.csv", io.BytesIO(invoice_csv), "text/csv")},
        headers=headers,
    )
    assert res_inv.status_code == 201
    assert res_inv.json()["upload_job"]["valid_rows"] == 2

    # 2. Ingest Gateway Transactions (Razorpay standard export columns)
    txn_csv = b"""payment_id,amount,status,method,fee,tax,created_at,email,order_id
pay_e2e_01,10000.00,captured,upi,200.00,36.00,2026-05-01 10:00:00,billing@enterprise.com,INV-E2E-1
pay_e2e_02,5000.00,captured,card,100.00,18.00,2026-05-02 11:30:00,admin@startup.io,INV-E2E-2
"""
    res_txn = client.post(
        "/api/uploads/gateway-txns",
        files={"file": ("gateway.csv", io.BytesIO(txn_csv), "text/csv")},
        headers=headers,
    )
    assert res_txn.status_code == 201
    assert res_txn.json()["upload_job"]["valid_rows"] == 2

    # 3. Ingest Settlement File
    settlement_csv = b"""settlement_id,entity_id,amount,fee,tax,type,utr,date
setl_batch_e2e,pay_e2e_01,10000.00,200.00,36.00,payment,UTR_E2E_PAYOUT_99,2026-05-03 18:00:00
setl_batch_e2e,pay_e2e_02,5000.00,100.00,18.00,payment,UTR_E2E_PAYOUT_99,2026-05-03 18:00:00
"""
    res_setl = client.post(
        "/api/uploads/settlements",
        files={"file": ("settlements.csv", io.BytesIO(settlement_csv), "text/csv")},
        headers=headers,
    )
    assert res_setl.status_code == 201
    assert res_setl.json()["upload_job"]["valid_rows"] == 1

    # 4. Ingest Bank Statement Credits
    bank_csv = b"""date,narration,withdrawal,credit,balance,reference
2026-05-04,NEFT-RAZORPAY-UTR_E2E_PAYOUT_99-PAYOUT,,14646.00,200000.00,UTR_E2E_PAYOUT_99
"""
    res_bank = client.post(
        "/api/uploads/bank-statements",
        files={"file": ("bank.csv", io.BytesIO(bank_csv), "text/csv")},
        headers=headers,
    )
    assert res_bank.status_code == 201
    assert res_bank.json()["upload_job"]["valid_rows"] == 1

    # 5. Trigger Reconciliation Run via POST /api/reconcile
    trigger_payload = {
        "rule_config": {
            "amount_tolerance": "1.00",
            "layer_1_date_window_days": 2,
            "layer_3_bank_window_days": 4,
            "enable_fuzzy_matching": True,
        }
    }
    trigger_res = client.post("/api/reconcile", json=trigger_payload, headers=headers)
    assert trigger_res.status_code == 201
    run_data = trigger_res.json()

    run_id = run_data["id"]
    assert run_data["status"] == "completed"
    assert run_data["total_invoices"] == 2
    assert run_data["matched_invoices"] == 2
    assert run_data["total_txns"] == 2
    assert run_data["matched_txns"] == 2
    assert run_data["total_settlements"] == 1
    assert run_data["matched_settlements"] == 1
    assert run_data["total_bank_credits"] == 1
    assert run_data["matched_bank_credits"] == 1
    assert Decimal(run_data["invoiced_amount"]) == Decimal("15000.00")
    assert Decimal(run_data["collected_amount"]) == Decimal("15000.00")
    assert Decimal(run_data["settled_amount"]) == Decimal("14646.00")
    assert Decimal(run_data["bank_credited_amount"]) == Decimal("14646.00")

    # 6. Test GET /api/reconcile (List Runs)
    list_res = client.get("/api/reconcile", headers=headers)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert any(r["id"] == run_id for r in list_data["items"])

    # 7. Test GET /api/reconcile/{run_id} (Fetch Run Details)
    detail_res = client.get(f"/api/reconcile/{run_id}", headers=headers)
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["id"] == run_id
    assert detail_data["matched_invoices"] == 2

    # 8. Test GET /api/reconcile/{run_id}/matches (Query Matches)
    matches_res = client.get(f"/api/reconcile/{run_id}/matches", headers=headers)
    assert matches_res.status_code == 200
    matches_data = matches_res.json()
    # 2 Layer 1 matches + 2 Layer 2 matches + 1 Layer 3 match = 5 total matches
    assert matches_data["total"] == 5

    # Test filtering by layer: Layer 1
    l1_res = client.get(
        f"/api/reconcile/{run_id}/matches?layer=layer_1", headers=headers
    )
    assert l1_res.status_code == 200
    assert l1_res.json()["total"] == 2

    # Test filtering by layer: Layer 3
    l3_res = client.get(
        f"/api/reconcile/{run_id}/matches?layer=layer_3", headers=headers
    )
    assert l3_res.status_code == 200
    assert l3_res.json()["total"] == 1
    assert l3_res.json()["items"][0]["layer"] == "layer_3"


def test_reconcile_empty_dataset(client):
    """
    Test triggering reconciliation for an organisation with no uploaded records.
    Verifies that the orchestrator completes cleanly with 0 counts and 0.00 balances.
    """
    token = register_tenant(client, "empty-tenant", "user@emptytenant.com")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post("/api/reconcile", headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "completed"
    assert data["total_invoices"] == 0
    assert data["total_txns"] == 0
    assert data["total_settlements"] == 0
    assert data["total_bank_credits"] == 0
    assert Decimal(data["invoiced_amount"]) == Decimal("0.00")


def test_reconcile_multi_tenant_isolation(client):
    """
    Verify that Tenant Beta cannot access or trigger reconciliation for Tenant Alpha.
    """
    token_alpha = register_tenant(client, "alpha-tenant", "alpha@company.com")
    token_beta = register_tenant(client, "beta-tenant", "beta@company.com")

    headers_alpha = {"Authorization": f"Bearer {token_alpha}"}
    headers_beta = {"Authorization": f"Bearer {token_beta}"}

    # Alpha triggers a run
    run_alpha = client.post("/api/reconcile", headers=headers_alpha).json()
    alpha_run_id = run_alpha["id"]

    # Beta lists runs -> must not include Alpha's run
    beta_list = client.get("/api/reconcile", headers=headers_beta).json()
    assert all(r["id"] != alpha_run_id for r in beta_list["items"])

    # Beta attempts to fetch Alpha's specific run -> 404
    fetch_res = client.get(f"/api/reconcile/{alpha_run_id}", headers=headers_beta)
    assert fetch_res.status_code == 404

    # Beta attempts to fetch matches for Alpha's run -> 404
    matches_res = client.get(
        f"/api/reconcile/{alpha_run_id}/matches", headers=headers_beta
    )
    assert matches_res.status_code == 404


def test_reconcile_unauthenticated_rejected(client):
    """
    Verify that unauthenticated requests to reconciliation endpoints are rejected with 401.
    """
    res_trigger = client.post("/api/reconcile")
    assert res_trigger.status_code == 401

    res_list = client.get("/api/reconcile")
    assert res_list.status_code == 401
