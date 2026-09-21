import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.core.security import decode_access_token


# Set up isolated in-memory SQLite database for test suite
TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    """
    Creates fresh schema before each test and drops all tables afterwards.
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def override_get_db():
    """
    FastAPI dependency override to route DB operations to the in-memory test database.
    """
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_register_new_organisation_and_admin():
    """
    Verify successful tenant organisation and admin registration.
    """
    payload = {
        "org_name": "ChargeFlow Technologies",
        "org_slug": "chargeflow",
        "email": "cfo@chargeflow.io",
        "password": "StrongPassword123!",
        "full_name": "Rohan Sharma",
        "currency": "INR",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()

    # Verify token payload
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "cfo@chargeflow.io"
    assert data["user"]["role"] == "admin"
    assert data["organisation"]["slug"] == "chargeflow"
    assert data["organisation"]["currency"] == "INR"

    # Decode and verify JWT claims
    claims = decode_access_token(data["access_token"])
    assert claims["sub"] == data["user"]["id"]
    assert claims["org_id"] == data["organisation"]["id"]
    assert claims["email"] == "cfo@chargeflow.io"


def test_register_duplicate_slug_or_email_rejected():
    """
    Verify collision rejection when duplicate organisation slug or user email is submitted.
    """
    payload = {
        "org_name": "First SaaS",
        "org_slug": "first-saas",
        "email": "admin@firstsaas.com",
        "password": "Password123!",
    }
    # Initial registration should succeed
    res1 = client.post("/api/auth/register", json=payload)
    assert res1.status_code == 201

    # Attempt registration with duplicate slug
    res_dup_slug = client.post(
        "/api/auth/register",
        json={**payload, "email": "different@firstsaas.com"},
    )
    assert res_dup_slug.status_code == 400
    assert "slug 'first-saas' is already taken" in res_dup_slug.json()["detail"]

    # Attempt registration with duplicate email
    res_dup_email = client.post(
        "/api/auth/register",
        json={**payload, "org_slug": "different-slug"},
    )
    assert res_dup_email.status_code == 400
    assert "already exists" in res_dup_email.json()["detail"]


def test_login_flow():
    """
    Verify user login with valid credentials, invalid password, and nonexistent account.
    """
    register_payload = {
        "org_name": "QuickSaaS",
        "org_slug": "quicksaas",
        "email": "finance@quicksaas.com",
        "password": "ValidPassword999",
        "full_name": "Priya Verma",
    }
    client.post("/api/auth/register", json=register_payload)

    # 1. Valid login
    login_res = client.post(
        "/api/auth/login",
        json={"email": "finance@quicksaas.com", "password": "ValidPassword999"},
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data

    # 2. Invalid password
    bad_pass_res = client.post(
        "/api/auth/login",
        json={"email": "finance@quicksaas.com", "password": "WrongPassword!"},
    )
    assert bad_pass_res.status_code == 401

    # 3. Nonexistent user
    unknown_user_res = client.post(
        "/api/auth/login",
        json={"email": "ghost@quicksaas.com", "password": "AnyPassword123"},
    )
    assert unknown_user_res.status_code == 401


def test_get_me_protected_route():
    """
    Verify /api/auth/me returns caller's profile and organisation when provided a valid Bearer token.
    """
    reg_res = client.post(
        "/api/auth/register",
        json={
            "org_name": "CloudNine SaaS",
            "org_slug": "cloudnine",
            "email": "admin@cloudnine.com",
            "password": "SuperSecurePassword123",
            "full_name": "Aman Gupta",
        },
    )
    token = reg_res.json()["access_token"]

    # Call /api/auth/me with valid Authorization header
    me_res = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["user"]["email"] == "admin@cloudnine.com"
    assert me_data["organisation"]["slug"] == "cloudnine"

    # Call /api/auth/me without header
    unauth_res = client.get("/api/auth/me")
    assert unauth_res.status_code == 401


def test_multi_tenant_token_isolation():
    """
    Verify that two different organisations receive distinct JWTs with distinct org_ids.
    """
    res_a = client.post(
        "/api/auth/register",
        json={
            "org_name": "Tenant Alpha",
            "org_slug": "alpha-corp",
            "email": "lead@alpha.com",
            "password": "PasswordAlpha123",
        },
    )
    res_b = client.post(
        "/api/auth/register",
        json={
            "org_name": "Tenant Beta",
            "org_slug": "beta-corp",
            "email": "lead@beta.com",
            "password": "PasswordBeta123",
        },
    )

    claims_a = decode_access_token(res_a.json()["access_token"])
    claims_b = decode_access_token(res_b.json()["access_token"])

    # Assert completely isolated tenant IDs
    assert claims_a["org_id"] != claims_b["org_id"]
    assert claims_a["sub"] != claims_b["sub"]
    assert claims_a["email"] == "lead@alpha.com"
    assert claims_b["email"] == "lead@beta.com"
