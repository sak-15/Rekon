import pytest
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.core.database import Base
from app.models import (
    Organisation,
    User,
    UserRole,
    UploadJob,
    FileTypeEnum,
    UploadStatusEnum,
    Invoice,
    InvoiceStatusEnum,
    ReconciliationStatusEnum,
    GatewayTransaction,
    GatewayEnum,
    PaymentMethodEnum,
    TxnStatusEnum,
    SettlementBatch,
    SettlementLine,
    SettlementLineTypeEnum,
    BankCredit,
)


@pytest.fixture
def db_session():
    """
    Creates an isolated in-memory SQLite database for testing models and constraints.
    """
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


def test_organisation_and_user_creation(db_session):
    """
    Verify organisation creation and relationship with users.
    """
    org = Organisation(name="SaaS Alpha", slug="saas-alpha", currency="INR")
    db_session.add(org)
    db_session.commit()

    user = User(
        org_id=org.id,
        email="finance@saasalpha.com",
        hashed_password="secure_hashed_password",
        full_name="Alpha Finance Lead",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    db_session.commit()

    saved_org = db_session.query(Organisation).filter_by(slug="saas-alpha").first()
    assert saved_org is not None
    assert len(saved_org.users) == 1
    assert saved_org.users[0].email == "finance@saasalpha.com"
    assert saved_org.users[0].role == UserRole.ADMIN


def test_multi_tenant_invoice_uniqueness(db_session):
    """
    Verify invoice numbers are unique PER ORGANISATION, allowing two different
    tenants to use the same invoice sequence without conflict.
    """
    org_a = Organisation(name="Tenant A", slug="tenant-a")
    org_b = Organisation(name="Tenant B", slug="tenant-b")
    db_session.add_all([org_a, org_b])
    db_session.commit()

    # Invoice INV-001 for Tenant A
    inv_a = Invoice(
        org_id=org_a.id,
        invoice_no="INV-001",
        customer_id="cust_123",
        customer_name="Acme Corp",
        amount=Decimal("15000.00"),
        invoice_date=datetime(2026, 1, 1),
    )
    # Same Invoice INV-001 for Tenant B (should succeed due to scoped uniqueness)
    inv_b = Invoice(
        org_id=org_b.id,
        invoice_no="INV-001",
        customer_id="cust_999",
        customer_name="Global Industries",
        amount=Decimal("25000.00"),
        invoice_date=datetime(2026, 1, 1),
    )
    db_session.add_all([inv_a, inv_b])
    db_session.commit()

    # Now verify that duplicate INV-001 within Tenant A FAILS
    duplicate_inv_a = Invoice(
        org_id=org_a.id,
        invoice_no="INV-001",
        customer_id="cust_456",
        amount=Decimal("5000.00"),
        invoice_date=datetime(2026, 1, 2),
    )
    db_session.add(duplicate_inv_a)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_gateway_transaction_fee_breakdown(db_session):
    """
    Verify gateway transaction recording with MDR and 18% GST calculation.
    """
    org = Organisation(name="Pay Corp", slug="pay-corp")
    db_session.add(org)
    db_session.commit()

    # Gross: ₹10,000, MDR: 2% (₹200), GST: 18% on ₹200 (₹36), Net: ₹9,764
    gross = Decimal("10000.00")
    fee = Decimal("200.00")
    gst = Decimal("36.00")
    net = gross - fee - gst

    txn = GatewayTransaction(
        org_id=org.id,
        txn_id="pay_K9z8Q12345",
        gateway=GatewayEnum.RAZORPAY,
        payment_method=PaymentMethodEnum.UPI,
        invoice_ref="INV-2026-05",
        amount=gross,
        gateway_fee=fee,
        gateway_fee_gst=gst,
        net_amount=net,
        captured_at=datetime(2026, 5, 10, 14, 30),
        status=TxnStatusEnum.CAPTURED,
    )
    db_session.add(txn)
    db_session.commit()

    fetched = db_session.query(GatewayTransaction).filter_by(txn_id="pay_K9z8Q12345").first()
    assert fetched is not None
    assert fetched.amount == Decimal("10000.00")
    assert fetched.net_amount == Decimal("9764.00")
    assert fetched.gateway == GatewayEnum.RAZORPAY
    assert fetched.payment_method == PaymentMethodEnum.UPI
    assert fetched.reconciliation_status == ReconciliationStatusEnum.UNMATCHED


def test_settlement_batch_and_lines(db_session):
    """
    Verify settlement batch creation with itemized settlement lines.
    """
    org = Organisation(name="SaaS Zeta", slug="saas-zeta")
    db_session.add(org)
    db_session.commit()

    batch = SettlementBatch(
        org_id=org.id,
        batch_id="setl_998877",
        gateway=GatewayEnum.STRIPE,
        settlement_date=datetime(2026, 5, 15),
        gross_amount=Decimal("50000.00"),
        total_fees=Decimal("1000.00"),
        total_gst=Decimal("180.00"),
        net_amount=Decimal("48820.00"),
        utr_number="STRIPE_UTR_20260515",
    )
    db_session.add(batch)
    db_session.commit()

    line_1 = SettlementLine(
        org_id=org.id,
        batch_id=batch.id,
        txn_ref="pi_1001",
        line_type=SettlementLineTypeEnum.PAYMENT,
        amount=Decimal("30000.00"),
        fee=Decimal("600.00"),
        tax=Decimal("108.00"),
    )
    line_2 = SettlementLine(
        org_id=org.id,
        batch_id=batch.id,
        txn_ref="pi_1002",
        line_type=SettlementLineTypeEnum.PAYMENT,
        amount=Decimal("20000.00"),
        fee=Decimal("400.00"),
        tax=Decimal("72.00"),
    )
    db_session.add_all([line_1, line_2])
    db_session.commit()

    fetched_batch = db_session.query(SettlementBatch).filter_by(batch_id="setl_998877").first()
    assert len(fetched_batch.lines) == 2
    total_line_amounts = sum(line.amount for line in fetched_batch.lines)
    assert total_line_amounts == Decimal("50000.00")


def test_bank_credit_recording(db_session):
    """
    Verify bank credit records for reconciling against settlement batches.
    """
    org = Organisation(name="SaaS Omega", slug="saas-omega")
    db_session.add(org)
    db_session.commit()

    bank_entry = BankCredit(
        org_id=org.id,
        transaction_date=datetime(2026, 5, 16),
        narration="CMS/RAZORPAY SETTLEMENT BATCH 2026-05-14 / UTR12345",
        credit_amount=Decimal("48820.00"),
        reference_no="UTR12345",
        bank_name="HDFC Bank",
    )
    db_session.add(bank_entry)
    db_session.commit()

    fetched = db_session.query(BankCredit).filter_by(reference_no="UTR12345").first()
    assert fetched is not None
    assert fetched.credit_amount == Decimal("48820.00")
    assert fetched.reconciliation_status == ReconciliationStatusEnum.UNMATCHED
