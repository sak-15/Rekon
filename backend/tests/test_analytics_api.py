import pytest
from decimal import Decimal
from datetime import datetime
from fastapi.testclient import TestClient

from app.models.invoice import Invoice, InvoiceStatusEnum, ReconciliationStatusEnum
from app.models.gateway import GatewayTransaction, GatewayEnum, PaymentMethodEnum, TxnStatusEnum, SettlementStatusEnum
from app.models.bank import BankCredit
from app.models.reconciliation_exception import (
    ReconciliationException,
    ExceptionTypeEnum,
    ExceptionSeverityEnum,
    ResolutionStatusEnum,
)


@pytest.fixture
def auth_headers_alpha(client: TestClient):
    """Register tenant alpha and return auth headers."""
    resp = client.post(
        "/api/auth/register",
        json={
            "org_name": "Executive Corp",
            "org_slug": "exec-corp",
            "email": "cfo@execcorp.com",
            "password": "Password123!",
            "full_name": "CFO Leader",
        },
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def auth_headers_beta(client: TestClient):
    """Register tenant beta and return auth headers."""
    resp = client.post(
        "/api/auth/register",
        json={
            "org_name": "Beta Executive Corp",
            "org_slug": "beta-exec",
            "email": "cfo@betaexec.com",
            "password": "Password123!",
            "full_name": "Beta CFO",
        },
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_empty_executive_dashboard(client: TestClient, auth_headers_alpha: dict):
    """
    Verifies that an organization with no transactions receives a valid, non-crashing
    executive dashboard with zeroed amounts, 100% baseline health score, and standard waterfall steps.
    """
    response = client.get("/api/analytics/dashboard", headers=auth_headers_alpha)
    assert response.status_code == 200
    data = response.json()

    assert "summary" in data
    assert "waterfall" in data
    assert "gateway_comparison" in data
    assert "actionable_alerts" in data

    summary = data["summary"]
    assert float(summary["gross_billed_amount"]) == 0.0
    assert float(summary["net_settled_cash"]) == 0.0
    assert summary["blended_take_rate_pct"] == 0.0
    assert summary["health_score"] == 100.0
    assert summary["health_status"] == "EXCELLENT"

    # Waterfall should have 5 canonical stages
    assert len(data["waterfall"]) == 5
    step_keys = [s["step_key"] for s in data["waterfall"]]
    assert step_keys == ["gross_billed", "gateway_mdr", "gateway_gst", "in_transit_lag", "net_bank_cash"]


def test_populated_executive_dashboard(
    client: TestClient,
    db_session,
    auth_headers_alpha: dict,
):
    """
    Verifies metric calculation accuracy with active invoices, gateway transactions,
    bank deposits, and exceptions.
    """
    me = client.get("/api/auth/me", headers=auth_headers_alpha).json()
    org_id = me["user"]["org_id"]

    # 1. Seed Invoice: ₹1,00,000
    inv = Invoice(
        org_id=org_id,
        invoice_no="INV-EXEC-001",
        customer_id="cust_exec_001",
        customer_email="founder@test.com",
        customer_name="Founder Corp",
        amount=Decimal("100000.00"),
        tax_amount=Decimal("0.00"),
        currency="INR",
        status=InvoiceStatusEnum.PAID,
        reconciliation_status=ReconciliationStatusEnum.MATCHED,
        invoice_date=datetime.utcnow(),
    )
    db_session.add(inv)

    # 2. Seed Gateway Txn: ₹1,00,000, Fee: ₹2,000, GST: ₹360 (Total Deduction: ₹2,360)
    txn = GatewayTransaction(
        org_id=org_id,
        gateway=GatewayEnum.RAZORPAY,
        txn_id="pay_exec_001",
        amount=Decimal("100000.00"),
        currency="INR",
        gateway_fee=Decimal("2000.00"),
        gateway_fee_gst=Decimal("360.00"),
        net_amount=Decimal("97640.00"),
        status=TxnStatusEnum.CAPTURED,
        settlement_status=SettlementStatusEnum.SETTLED,
        payment_method=PaymentMethodEnum.CARD,
        captured_at=datetime.utcnow(),
    )
    db_session.add(txn)

    # 3. Seed Bank Credit: ₹97,640
    bank = BankCredit(
        org_id=org_id,
        bank_name="HDFC Bank",
        transaction_date=datetime.utcnow(),
        credit_amount=Decimal("97640.00"),
        narration="CMS/RAZORPAY/SETTLEMENT/UTR999",
        reference_no="UTR999",
        reconciliation_status=ReconciliationStatusEnum.MATCHED,
    )
    db_session.add(bank)

    # 4. Seed Open Exception: ₹500
    exc = ReconciliationException(
        org_id=org_id,
        title="Settlement timing lag",
        exception_type=ExceptionTypeEnum.TIMING_DIFFERENCE,
        severity=ExceptionSeverityEnum.LOW,
        status=ResolutionStatusEnum.OPEN,
        expected_amount=Decimal("500.00"),
        actual_amount=Decimal("0.00"),
        discrepancy_amount=Decimal("500.00"),
        root_cause_explanation="Recent transaction within T+2 settlement lag window.",
    )
    db_session.add(exc)
    db_session.commit()

    # Query Executive Dashboard
    response = client.get("/api/analytics/dashboard", headers=auth_headers_alpha)
    assert response.status_code == 200
    data = response.json()

    summary = data["summary"]
    assert float(summary["gross_billed_amount"]) == 100000.0
    assert float(summary["gross_gateway_volume"]) == 100000.0
    assert float(summary["net_settled_cash"]) == 97640.0
    assert float(summary["total_gateway_fees"]) == 2000.0
    assert float(summary["total_gateway_gst"]) == 360.0
    assert float(summary["total_gateway_deductions"]) == 2360.0
    # Blended take rate = 2360 / 100000 * 100 = 2.36%
    assert summary["blended_take_rate_pct"] == 2.36
    assert float(summary["unresolved_exposure"]) == 500.0
    assert summary["open_exceptions_count"] == 1

    # Gateway comparison
    assert len(data["gateway_comparison"]) >= 1
    gw = next(g for g in data["gateway_comparison"] if g["gateway"] == "RAZORPAY")
    assert float(gw["gross_volume"]) == 100000.0
    assert gw["effective_take_rate_pct"] == 2.36

    # Actionable alerts
    assert len(data["actionable_alerts"]) > 0


def test_multi_tenant_analytics_isolation(
    client: TestClient,
    db_session,
    auth_headers_alpha: dict,
    auth_headers_beta: dict,
):
    """
    Verifies that Tenant Beta cannot see Tenant Alpha's revenue, cash, or metrics.
    """
    me_a = client.get("/api/auth/me", headers=auth_headers_alpha).json()
    org_id_a = me_a["user"]["org_id"]

    # Seed data only for Tenant Alpha
    inv = Invoice(
        org_id=org_id_a,
        invoice_no="INV-ALPHA-TOPSECRET",
        customer_id="cust_alpha_001",
        amount=Decimal("500000.00"),
        tax_amount=Decimal("0.00"),
        currency="INR",
        status=InvoiceStatusEnum.PAID,
        reconciliation_status=ReconciliationStatusEnum.MATCHED,
        invoice_date=datetime.utcnow(),
    )
    db_session.add(inv)
    db_session.commit()

    # Tenant Alpha should see 500k
    resp_a = client.get("/api/analytics/dashboard", headers=auth_headers_alpha)
    assert resp_a.status_code == 200
    assert float(resp_a.json()["summary"]["gross_billed_amount"]) >= 500000.0

    # Tenant Beta should see 0
    resp_b = client.get("/api/analytics/dashboard", headers=auth_headers_beta)
    assert resp_b.status_code == 200
    assert float(resp_b.json()["summary"]["gross_billed_amount"]) == 0.0


def test_analytics_sub_endpoints(
    client: TestClient,
    auth_headers_alpha: dict,
):
    """
    Verifies /summary, /waterfall, and /gateways sub-endpoints respond properly.
    """
    resp_summary = client.get("/api/analytics/summary", headers=auth_headers_alpha)
    assert resp_summary.status_code == 200
    assert "gross_billed_amount" in resp_summary.json()

    resp_waterfall = client.get("/api/analytics/waterfall", headers=auth_headers_alpha)
    assert resp_waterfall.status_code == 200
    assert isinstance(resp_waterfall.json(), list)

    resp_gateways = client.get("/api/analytics/gateways", headers=auth_headers_alpha)
    assert resp_gateways.status_code == 200
    assert isinstance(resp_gateways.json(), list)


def test_analytics_date_range_filtering(
    client: TestClient,
    db_session,
    auth_headers_alpha: dict,
):
    """
    Verifies that start_date and end_date query parameters properly filter transactions.
    """
    me = client.get("/api/auth/me", headers=auth_headers_alpha).json()
    org_id = me["user"]["org_id"]

    # 1. Past invoice in 2025
    inv_2025 = Invoice(
        org_id=org_id,
        invoice_no="INV-OLD-2025",
        customer_id="cust_old",
        amount=Decimal("25000.00"),
        tax_amount=Decimal("0.00"),
        currency="INR",
        status=InvoiceStatusEnum.PAID,
        reconciliation_status=ReconciliationStatusEnum.MATCHED,
        invoice_date=datetime(2025, 6, 15, 10, 0, 0),
    )
    # 2. Recent invoice in 2026
    inv_2026 = Invoice(
        org_id=org_id,
        invoice_no="INV-NEW-2026",
        customer_id="cust_new",
        amount=Decimal("75000.00"),
        tax_amount=Decimal("0.00"),
        currency="INR",
        status=InvoiceStatusEnum.PAID,
        reconciliation_status=ReconciliationStatusEnum.MATCHED,
        invoice_date=datetime(2026, 5, 10, 10, 0, 0),
    )
    db_session.add_all([inv_2025, inv_2026])
    db_session.commit()

    # Query 2026 only
    resp = client.get(
        "/api/analytics/dashboard?start_date=2026-01-01T00:00:00&end_date=2026-12-31T23:59:59",
        headers=auth_headers_alpha,
    )
    assert resp.status_code == 200
    data = resp.json()
    # Should only include 75k, not 25k
    assert float(data["summary"]["gross_billed_amount"]) == 75000.0
    assert data["summary"]["invoice_count"] == 1

    # Query 2025 only
    resp_2025 = client.get(
        "/api/analytics/dashboard?start_date=2025-01-01T00:00:00&end_date=2025-12-31T23:59:59",
        headers=auth_headers_alpha,
    )
    assert resp_2025.status_code == 200
    data_2025 = resp_2025.json()
    assert float(data_2025["summary"]["gross_billed_amount"]) == 25000.0
    assert data_2025["summary"]["invoice_count"] == 1

