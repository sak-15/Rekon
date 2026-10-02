import pytest
from decimal import Decimal
from datetime import datetime
from fastapi.testclient import TestClient
from app.models.gateway import GatewayTransaction, GatewayEnum, PaymentMethodEnum, TxnStatusEnum


@pytest.fixture
def auth_headers(client: TestClient):
    """Register an org and admin user, return JWT bearer headers."""
    reg_resp = client.post(
        "/api/auth/register",
        json={
            "org_name": "Audit Corp",
            "org_slug": "audit-corp",
            "email": "cfo@auditcorp.com",
            "full_name": "Chief Financial Officer",
            "password": "SecurePassword123!",
        },
    )
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_auth_headers(client: TestClient):
    """Register another org and user for tenant isolation testing."""
    reg_resp = client.post(
        "/api/auth/register",
        json={
            "org_name": "Other Corp",
            "org_slug": "other-corp",
            "email": "admin@othercorp.com",
            "full_name": "Other Admin",
            "password": "SecurePassword123!",
        },
    )
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_list_rate_cards_auto_seeds_benchmarks(client: TestClient, auth_headers: dict):
    """Calling GET /api/rate-cards when none exist should auto-seed default benchmarks."""
    resp = client.get("/api/rate-cards?gateway=razorpay", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 7
    assert len(data["items"]) == 7

    # Verify domestic UPI zero MDR is present
    upi_rule = next((r for r in data["items"] if r["payment_method"] == "upi"), None)
    assert upi_rule is not None
    assert float(upi_rule["percentage_rate"]) == 0.0

    # Verify debit card RBI cap rule is present
    debit_rule = next((r for r in data["items"] if r["payment_method"] == "card" and r["card_network"] == "debit"), None)
    assert debit_rule is not None
    assert float(debit_rule["cap_max_fee"]) == 20.0


def test_rate_card_crud_lifecycle(client: TestClient, auth_headers: dict):
    """Test creating, updating, and deleting a custom rate card rule."""
    # 1. Create a custom international card rule
    create_resp = client.post(
        "/api/rate-cards",
        headers=auth_headers,
        json={
            "gateway": "razorpay",
            "payment_method": "card",
            "card_network": "visa",
            "is_international": True,
            "rate_type": "percentage",
            "percentage_rate": 0.0275,  # Negotiated 2.75%
            "flat_fee": 0.0,
            "gst_rate": 0.18,
            "notes": "Custom negotiated enterprise rate for Visa International",
        },
    )
    assert create_resp.status_code == 201
    card_data = create_resp.json()
    card_id = card_data["id"]
    assert float(card_data["percentage_rate"]) == 0.0275

    # 2. Update the rule to 2.50%
    update_resp = client.put(
        f"/api/rate-cards/{card_id}",
        headers=auth_headers,
        json={"percentage_rate": 0.0250},
    )
    assert update_resp.status_code == 200
    assert float(update_resp.json()["percentage_rate"]) == 0.0250

    # 3. Delete the rule
    del_resp = client.delete(f"/api/rate-cards/{card_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    # 4. Verify deleted
    get_resp = client.put(f"/api/rate-cards/{card_id}", headers=auth_headers, json={"notes": "test"})
    assert get_resp.status_code == 404


def test_rate_card_interactive_calculator(client: TestClient, auth_headers: dict):
    """Test POST /api/rate-cards/calculate preview math."""
    # First seed rate cards
    list_resp = client.get("/api/rate-cards?gateway=razorpay", headers=auth_headers)
    cards = list_resp.json()["items"]
    credit_card = next(c for c in cards if c["payment_method"] == "card" and c["card_network"] == "credit")

    calc_resp = client.post(
        "/api/rate-cards/calculate",
        headers=auth_headers,
        json={"gross_amount": 10000.00, "rate_card_id": credit_card["id"]},
    )
    assert calc_resp.status_code == 200
    res = calc_resp.json()
    assert float(res["gross_amount"]) == 10000.00
    # Expected fee is 2% (₹200) + 18% GST (₹36) = ₹236 total deduction
    assert float(res["expected_fee"]) == 200.00
    assert float(res["expected_gst"]) == 36.00
    assert float(res["expected_total_deduction"]) == 236.00
    assert float(res["expected_net_amount"]) == 9764.00
    assert float(res["effective_take_rate_pct"]) == 2.36


def test_fee_audit_and_export_endpoints(client: TestClient, auth_headers: dict, db_session):
    """Test GET /api/fee-audit and GET /api/fee-audit/export with simulated transactions."""
    # Get current user org id
    me_resp = client.get("/api/auth/me", headers=auth_headers)
    org_id = me_resp.json()["user"]["org_id"]

    # Seed rate cards
    client.get("/api/rate-cards?gateway=razorpay", headers=auth_headers)

    # Insert 2 transactions into DB: one verified, one overcharged
    t1 = GatewayTransaction(
        org_id=org_id,
        txn_id="pay_audit_01",
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.UPI,
        amount=Decimal("3000.00"),
        gateway_fee=Decimal("0.00"),
        gateway_fee_gst=Decimal("0.00"),
        net_amount=Decimal("3000.00"),
        captured_at=datetime(2026, 3, 10, 10, 0, 0),
        status=TxnStatusEnum.CAPTURED,
    )
    t2 = GatewayTransaction(
        org_id=org_id,
        txn_id="pay_audit_02",
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.CARD,
        amount=Decimal("10000.00"),
        gateway_fee=Decimal("250.00"),     # Overcharged by ₹50
        gateway_fee_gst=Decimal("45.00"),  # GST overcharged by ₹9
        net_amount=Decimal("9705.00"),
        captured_at=datetime(2026, 3, 11, 10, 0, 0),
        status=TxnStatusEnum.CAPTURED,
    )
    db_session.add_all([t1, t2])
    db_session.commit()

    # 1. Test GET /api/fee-audit
    audit_resp = client.get("/api/fee-audit", headers=auth_headers)
    assert audit_resp.status_code == 200
    report = audit_resp.json()
    assert report["total_audited"] == 2
    assert report["verified_count"] == 1
    assert report["overcharged_count"] == 1
    assert float(report["total_overcharged_amount"]) == 59.00
    assert "unauthorized_mdr_markup" in report["discrepancies_by_category"]

    # 2. Test GET /api/fee-audit/export
    export_resp = client.get("/api/fee-audit/export", headers=auth_headers)
    assert export_resp.status_code == 200
    assert "text/csv" in export_resp.headers["content-type"]
    csv_text = export_resp.text
    assert "pay_audit_02" in csv_text
    assert "pay_audit_01" not in csv_text  # only overcharges
    assert "59.00" in csv_text


def test_fee_audit_unauthenticated_and_tenant_isolation(
    client: TestClient,
    auth_headers: dict,
    other_auth_headers: dict,
    db_session,
):
    """Test security: 401 when unauthorized, and zero leakage between tenants."""
    # 1. Unauthenticated 401
    assert client.get("/api/rate-cards").status_code == 401
    assert client.get("/api/fee-audit").status_code == 401
    assert client.get("/api/fee-audit/export").status_code == 401

    # 2. Tenant isolation
    me1 = client.get("/api/auth/me", headers=auth_headers).json()
    me2 = client.get("/api/auth/me", headers=other_auth_headers).json()
    assert me1["user"]["org_id"] != me2["user"]["org_id"]

    # Org 2 should see 0 audited transactions even if Org 1 has transactions
    resp2 = client.get("/api/fee-audit", headers=other_auth_headers)
    assert resp2.status_code == 200
    assert resp2.json()["total_audited"] == 0
