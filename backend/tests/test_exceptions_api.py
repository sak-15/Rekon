import pytest
from decimal import Decimal
from datetime import datetime
from fastapi.testclient import TestClient
from app.models.reconciliation_exception import (
    ReconciliationException,
    ExceptionTypeEnum,
    ExceptionSeverityEnum,
    ResolutionStatusEnum,
)


@pytest.fixture
def auth_headers(client: TestClient):
    """Register org and return auth headers."""
    resp = client.post(
        "/api/auth/register",
        json={
            "org_name": "Exceptions Corp",
            "org_slug": "exc-corp",
            "email": "lead@exccorp.com",
            "password": "Password123!",
            "full_name": "Finance Lead",
        },
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def other_auth_headers(client: TestClient):
    """Register second org for tenant isolation."""
    resp = client.post(
        "/api/auth/register",
        json={
            "org_name": "Other Exc Corp",
            "org_slug": "other-exc-corp",
            "email": "lead@otherexc.com",
            "password": "Password123!",
            "full_name": "Other Lead",
        },
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_list_and_summary_exceptions_api(client: TestClient, auth_headers: dict, db_session):
    """Test GET /api/exceptions and GET /api/exceptions/summary."""
    me = client.get("/api/auth/me", headers=auth_headers).json()
    org_id = me["user"]["org_id"]

    # Insert 2 exceptions
    e1 = ReconciliationException(
        org_id=org_id,
        exception_type=ExceptionTypeEnum.MISSING_BANK_CREDIT,
        severity=ExceptionSeverityEnum.HIGH,
        status=ResolutionStatusEnum.OPEN,
        expected_amount=Decimal("50000.00"),
        actual_amount=Decimal("0.00"),
        discrepancy_amount=Decimal("50000.00"),
        title="Missing Bank Deposit ₹50k",
        root_cause_explanation="Settlement UTR not found in bank.",
    )
    e2 = ReconciliationException(
        org_id=org_id,
        exception_type=ExceptionTypeEnum.PAISA_ROUNDING_DELTA,
        severity=ExceptionSeverityEnum.LOW,
        status=ResolutionStatusEnum.OPEN,
        expected_amount=Decimal("100.00"),
        actual_amount=Decimal("99.50"),
        discrepancy_amount=Decimal("0.50"),
        title="50 paise delta",
        root_cause_explanation="Tax rounding.",
    )
    db_session.add_all([e1, e2])
    db_session.commit()

    # 1. List all
    list_resp = client.get("/api/exceptions", headers=auth_headers)
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2

    # 2. Filter by status
    filtered_resp = client.get("/api/exceptions?status=resolved", headers=auth_headers)
    assert filtered_resp.status_code == 200
    assert filtered_resp.json()["total"] == 0

    # 3. Summary
    sum_resp = client.get("/api/exceptions/summary", headers=auth_headers)
    assert sum_resp.status_code == 200
    sum_data = sum_resp.json()
    assert sum_data["total_exceptions"] == 2
    assert sum_data["open_count"] == 2
    assert sum_data["total_unresolved_exposure"] == 50000.50
    assert sum_data["severity_breakdown"]["high"] == 1
    assert sum_data["severity_breakdown"]["low"] == 1


def test_write_off_and_batch_write_off_api(client: TestClient, auth_headers: dict, db_session):
    """Test POST /api/exceptions/{id}/write-off and /batch-write-off."""
    me = client.get("/api/auth/me", headers=auth_headers).json()
    org_id = me["user"]["org_id"]

    e1 = ReconciliationException(
        org_id=org_id,
        exception_type=ExceptionTypeEnum.PAISA_ROUNDING_DELTA,
        severity=ExceptionSeverityEnum.LOW,
        status=ResolutionStatusEnum.OPEN,
        expected_amount=Decimal("100.00"),
        discrepancy_amount=Decimal("0.75"),
        title="75p delta",
        root_cause_explanation="GST rounding",
    )
    e2 = ReconciliationException(
        org_id=org_id,
        exception_type=ExceptionTypeEnum.PAISA_ROUNDING_DELTA,
        severity=ExceptionSeverityEnum.LOW,
        status=ResolutionStatusEnum.OPEN,
        expected_amount=Decimal("150.00"),
        discrepancy_amount=Decimal("1.25"),
        title="₹1.25 delta",
        root_cause_explanation="Bank fee rounding",
    )
    db_session.add_all([e1, e2])
    db_session.commit()

    # 1. Single write off on e1
    wo_resp = client.post(
        f"/api/exceptions/{e1.id}/write-off",
        headers=auth_headers,
        json={"notes": "Written off to rounding ledger"},
    )
    assert wo_resp.status_code == 200
    assert wo_resp.json()["status"] == "written_off"
    assert wo_resp.json()["resolution_action"] == "write_off"

    # 2. Batch write-off remaining items
    batch_resp = client.post(
        "/api/exceptions/batch-write-off",
        headers=auth_headers,
        json={"max_threshold": 5.00},
    )
    assert batch_resp.status_code == 200
    assert len(batch_resp.json()) == 1
    assert batch_resp.json()[0]["id"] == e2.id
    assert batch_resp.json()[0]["status"] == "written_off"


def test_update_exception_status_api(client: TestClient, auth_headers: dict, db_session):
    """Test PUT /api/exceptions/{id}/status."""
    me = client.get("/api/auth/me", headers=auth_headers).json()
    org_id = me["user"]["org_id"]

    exc = ReconciliationException(
        org_id=org_id,
        exception_type=ExceptionTypeEnum.MISSING_BANK_CREDIT,
        severity=ExceptionSeverityEnum.CRITICAL,
        status=ResolutionStatusEnum.OPEN,
        discrepancy_amount=Decimal("120000.00"),
        title="Missing ₹1.2L deposit",
        root_cause_explanation="Missing in bank",
    )
    db_session.add(exc)
    db_session.commit()

    # Move to INVESTIGATING
    resp = client.put(
        f"/api/exceptions/{exc.id}/status",
        headers=auth_headers,
        json={"status": "investigating", "notes": "Raised ticket with HDFC branch manager"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "investigating"
    assert "HDFC branch" in resp.json()["resolution_notes"]


def test_exceptions_tenant_isolation_and_auth(client: TestClient, auth_headers: dict, other_auth_headers: dict):
    """Test 401 unauthenticated and multi-tenant isolation."""
    # 1. 401 Unauthorized
    assert client.get("/api/exceptions").status_code == 401
    assert client.get("/api/exceptions/summary").status_code == 401

    # 2. Tenant isolation: Org 2 should see 0 exceptions
    resp = client.get("/api/exceptions", headers=other_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

