"""initial schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-21 20:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Organisations
    op.create_table(
        'organisations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='INR'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_organisations_slug', 'organisations', ['slug'], unique=True)

    # 2. Users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('org_id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='finance_analyst'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_org_id', 'users', ['org_id'], unique=False)

    # 3. Upload Jobs
    op.create_table(
        'upload_jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('org_id', sa.String(length=36), nullable=False),
        sa.Column('file_type', sa.String(length=50), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('total_rows', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('valid_rows', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_rows', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_upload_jobs_org_id', 'upload_jobs', ['org_id'], unique=False)

    # 4. Invoices
    op.create_table(
        'invoices',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('org_id', sa.String(length=36), nullable=False),
        sa.Column('upload_job_id', sa.String(length=36), nullable=True),
        sa.Column('invoice_no', sa.String(length=100), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('customer_name', sa.String(length=255), nullable=True),
        sa.Column('customer_email', sa.String(length=255), nullable=True),
        sa.Column('plan_name', sa.String(length=100), nullable=True),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('tax_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='INR'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='paid'),
        sa.Column('invoice_date', sa.DateTime(), nullable=False),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('billing_period_start', sa.Date(), nullable=True),
        sa.Column('billing_period_end', sa.Date(), nullable=True),
        sa.Column('source_system', sa.String(length=50), nullable=False, server_default='chargebee'),
        sa.Column('reconciliation_status', sa.String(length=50), nullable=False, server_default='unmatched'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['upload_job_id'], ['upload_jobs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'invoice_no', name='uq_org_invoice_no'),
    )
    op.create_index('ix_invoices_org_id', 'invoices', ['org_id'], unique=False)
    op.create_index('ix_invoices_customer_id', 'invoices', ['customer_id'], unique=False)
    op.create_index('ix_invoices_reconciliation_status', 'invoices', ['reconciliation_status'], unique=False)
    op.create_index('ix_invoices_org_customer_amount', 'invoices', ['org_id', 'customer_id', 'amount'], unique=False)

    # 5. Gateway Transactions
    op.create_table(
        'gateway_txns',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('org_id', sa.String(length=36), nullable=False),
        sa.Column('upload_job_id', sa.String(length=36), nullable=True),
        sa.Column('txn_id', sa.String(length=100), nullable=False),
        sa.Column('gateway', sa.String(length=50), nullable=False),
        sa.Column('payment_method', sa.String(length=50), nullable=False, server_default='other'),
        sa.Column('invoice_ref', sa.String(length=100), nullable=True),
        sa.Column('customer_email', sa.String(length=255), nullable=True),
        sa.Column('customer_contact', sa.String(length=50), nullable=True),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='INR'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='captured'),
        sa.Column('gateway_fee', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('gateway_fee_gst', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('net_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('captured_at', sa.DateTime(), nullable=False),
        sa.Column('settlement_status', sa.String(length=50), nullable=False, server_default='unsettled'),
        sa.Column('reconciliation_status', sa.String(length=50), nullable=False, server_default='unmatched'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['upload_job_id'], ['upload_jobs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'txn_id', name='uq_org_txn_id'),
    )
    op.create_index('ix_gateway_txns_org_id', 'gateway_txns', ['org_id'], unique=False)
    op.create_index('ix_gateway_txns_gateway', 'gateway_txns', ['gateway'], unique=False)
    op.create_index('ix_gateway_txns_invoice_ref', 'gateway_txns', ['invoice_ref'], unique=False)
    op.create_index('ix_gateway_txns_captured_at', 'gateway_txns', ['captured_at'], unique=False)
    op.create_index('ix_gateway_txns_reconciliation_status', 'gateway_txns', ['reconciliation_status'], unique=False)
    op.create_index('ix_gateway_txns_org_amount_date', 'gateway_txns', ['org_id', 'amount', 'captured_at'], unique=False)

    # 6. Settlement Batches
    op.create_table(
        'settlement_batches',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('org_id', sa.String(length=36), nullable=False),
        sa.Column('upload_job_id', sa.String(length=36), nullable=True),
        sa.Column('batch_id', sa.String(length=100), nullable=False),
        sa.Column('gateway', sa.String(length=50), nullable=False),
        sa.Column('settlement_date', sa.DateTime(), nullable=False),
        sa.Column('gross_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('total_fees', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('total_gst', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('total_refunds', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('total_adjustments', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('net_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='INR'),
        sa.Column('utr_number', sa.String(length=100), nullable=True),
        sa.Column('bank_account_ref', sa.String(length=50), nullable=True),
        sa.Column('reconciliation_status', sa.String(length=50), nullable=False, server_default='unmatched'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['upload_job_id'], ['upload_jobs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'batch_id', name='uq_org_batch_id'),
    )
    op.create_index('ix_settlement_batches_org_id', 'settlement_batches', ['org_id'], unique=False)
    op.create_index('ix_settlement_batches_gateway', 'settlement_batches', ['gateway'], unique=False)
    op.create_index('ix_settlement_batches_settlement_date', 'settlement_batches', ['settlement_date'], unique=False)
    op.create_index('ix_settlement_batches_utr_number', 'settlement_batches', ['utr_number'], unique=False)
    op.create_index('ix_settlement_batches_reconciliation_status', 'settlement_batches', ['reconciliation_status'], unique=False)
    op.create_index('ix_settlement_batches_org_net_date', 'settlement_batches', ['org_id', 'net_amount', 'settlement_date'], unique=False)

    # 7. Settlement Lines
    op.create_table(
        'settlement_lines',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('org_id', sa.String(length=36), nullable=False),
        sa.Column('batch_id', sa.String(length=36), nullable=False),
        sa.Column('txn_ref', sa.String(length=100), nullable=False),
        sa.Column('line_type', sa.String(length=50), nullable=False, server_default='payment'),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('fee', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('tax', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['batch_id'], ['settlement_batches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_settlement_lines_org_id', 'settlement_lines', ['org_id'], unique=False)
    op.create_index('ix_settlement_lines_batch_id', 'settlement_lines', ['batch_id'], unique=False)
    op.create_index('ix_settlement_lines_txn_ref', 'settlement_lines', ['txn_ref'], unique=False)

    # 8. Bank Credits
    op.create_table(
        'bank_credits',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('org_id', sa.String(length=36), nullable=False),
        sa.Column('upload_job_id', sa.String(length=36), nullable=True),
        sa.Column('transaction_date', sa.DateTime(), nullable=False),
        sa.Column('value_date', sa.DateTime(), nullable=True),
        sa.Column('narration', sa.String(length=500), nullable=False),
        sa.Column('credit_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('debit_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('running_balance', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('reference_no', sa.String(length=100), nullable=True),
        sa.Column('bank_name', sa.String(length=100), nullable=True),
        sa.Column('reconciliation_status', sa.String(length=50), nullable=False, server_default='unmatched'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['upload_job_id'], ['upload_jobs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_bank_credits_org_id', 'bank_credits', ['org_id'], unique=False)
    op.create_index('ix_bank_credits_reference_no', 'bank_credits', ['reference_no'], unique=False)
    op.create_index('ix_bank_credits_transaction_date', 'bank_credits', ['transaction_date'], unique=False)
    op.create_index('ix_bank_credits_reconciliation_status', 'bank_credits', ['reconciliation_status'], unique=False)
    op.create_index('ix_bank_credits_org_credit_date', 'bank_credits', ['org_id', 'credit_amount', 'transaction_date'], unique=False)


def downgrade() -> None:
    op.drop_table('bank_credits')
    op.drop_table('settlement_lines')
    op.drop_table('settlement_batches')
    op.drop_table('gateway_txns')
    op.drop_table('invoices')
    op.drop_table('upload_jobs')
    op.drop_table('users')
    op.drop_table('organisations')

