import pytest
from decimal import Decimal
from datetime import datetime
from app.models.organisation import Organisation, User, UserRole
from app.models.reconciliation_exception import (
    ReconciliationException,
    ExceptionTypeEnum,
    ExceptionSeverityEnum,
    ResolutionStatusEnum,
    ResolutionActionEnum,
)
from app.models.invoice import Invoice, InvoiceStatusEnum
from app.models.gateway import GatewayTransaction, GatewayEnum, PaymentMethodEnum, TxnStatusEnum


def test_exception_model_creation_and_defaults(db_session):
    """Verify ReconciliationException defaults, monetary values, and enums."""
    org = Organisation(name="Exception Corp", slug="exception-corp")
    db_session.add(org)
    db_session.commit()

    exc = ReconciliationException(
        org_id=org.id,
        exception_type=ExceptionTypeEnum.MISSING_BANK_CREDIT,
        severity=ExceptionSeverityEnum.HIGH,
        expected_amount=Decimal("150000.00"),
        actual_amount=Decimal("0.00"),
        discrepancy_amount=Decimal("150000.00"),
        title="Missing Bank Deposit for UTR_RZP_999",
        root_cause_explanation="Gateway reports settlement payout sent with UTR, but bank shows zero credit entry.",
        suggested_action="Inquire with banking operations or payment gateway support.",
    )
    db_session.add(exc)
    db_session.commit()
    db_session.refresh(exc)

    assert exc.id is not None
    assert exc.status == ResolutionStatusEnum.OPEN
    assert exc.severity == ExceptionSeverityEnum.HIGH
    assert exc.exception_type == ExceptionTypeEnum.MISSING_BANK_CREDIT
    assert exc.discrepancy_amount == Decimal("150000.00")
    assert exc.resolved_at is None
    assert exc.resolved_by is None


def test_exception_resolution_lifecycle(db_session):
    """Verify updating status, recording resolver audit trail, and write-off notes."""
    org = Organisation(name="Resolver Org", slug="resolver-org")
    db_session.add(org)
    db_session.commit()

    user = User(
        org_id=org.id,
        email="operator@resolver.org",
        hashed_password="hash",
        full_name="Finance Operator",
        role=UserRole.FINANCE_ANALYST,
    )
    db_session.add(user)
    db_session.commit()

    exc = ReconciliationException(
        org_id=org.id,
        exception_type=ExceptionTypeEnum.PAISA_ROUNDING_DELTA,
        severity=ExceptionSeverityEnum.LOW,
        expected_amount=Decimal("1000.00"),
        actual_amount=Decimal("999.65"),
        discrepancy_amount=Decimal("0.35"),
        title="Minor 35 paise GST rounding delta",
        root_cause_explanation="Fractional rounding variance under ₹1.00.",
        suggested_action="Write off to Rounding Expense.",
    )
    db_session.add(exc)
    db_session.commit()

    # Operator writes off the 35 paise delta
    exc.status = ResolutionStatusEnum.WRITTEN_OFF
    exc.resolution_action = ResolutionActionEnum.WRITE_OFF
    exc.resolution_notes = "Immaterial variance booked to Rounding / Bank charges ledger."
    exc.resolved_by = user.id
    exc.resolved_at = datetime.utcnow()
    db_session.commit()
    db_session.refresh(exc)

    assert exc.status == ResolutionStatusEnum.WRITTEN_OFF
    assert exc.resolution_action == ResolutionActionEnum.WRITE_OFF
    assert exc.resolved_by == user.id
    assert exc.resolver.email == "operator@resolver.org"
    assert "Round" in exc.resolution_notes


def test_exception_entity_pointers_and_multi_tenant_isolation(db_session):
    """Verify entity relationships and strict tenant isolation."""
    org1 = Organisation(name="Org 1", slug="org-1")
    org2 = Organisation(name="Org 2", slug="org-2")
    db_session.add_all([org1, org2])
    db_session.commit()

    inv = Invoice(
        org_id=org1.id,
        invoice_no="INV-EXC-001",
        customer_id="cust_001",
        customer_name="Customer 1",
        amount=Decimal("14160.00"),
        tax_amount=Decimal("2160.00"),
        currency="INR",
        status=InvoiceStatusEnum.PAID,
        invoice_date=datetime(2026, 4, 1),
    )
    db_session.add(inv)
    db_session.commit()

    exc1 = ReconciliationException(
        org_id=org1.id,
        invoice_id=inv.id,
        exception_type=ExceptionTypeEnum.AMOUNT_MISMATCH,
        severity=ExceptionSeverityEnum.MEDIUM,
        expected_amount=Decimal("14160.00"),
        actual_amount=Decimal("10000.00"),
        discrepancy_amount=Decimal("4160.00"),
        title="Short payment of ₹4,160 on INV-EXC-001",
        root_cause_explanation="Amount collected is short by ₹4,160.",
    )
    exc2 = ReconciliationException(
        org_id=org2.id,
        exception_type=ExceptionTypeEnum.UNBILLED_CHARGE,
        severity=ExceptionSeverityEnum.HIGH,
        expected_amount=Decimal("0.00"),
        actual_amount=Decimal("5000.00"),
        discrepancy_amount=Decimal("5000.00"),
        title="Unbilled payment of ₹5,000",
        root_cause_explanation="Payment captured without invoice.",
    )
    db_session.add_all([exc1, exc2])
    db_session.commit()

    # Query for Org 1 strictly returns Org 1 exception and loads linked invoice
    org1_exceptions = (
        db_session.query(ReconciliationException)
        .filter(ReconciliationException.org_id == org1.id)
        .all()
    )
    assert len(org1_exceptions) == 1
    assert org1_exceptions[0].invoice_id == inv.id
    assert org1_exceptions[0].invoice.invoice_no == "INV-EXC-001"

    # Org 2 strictly sees only its own exception
    org2_exceptions = (
        db_session.query(ReconciliationException)
        .filter(ReconciliationException.org_id == org2.id)
        .all()
    )
    assert len(org2_exceptions) == 1
    assert org2_exceptions[0].exception_type == ExceptionTypeEnum.UNBILLED_CHARGE
