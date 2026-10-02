"""exception resolution queue models

Revision ID: 0004_exception_models
Revises: 0003_fee_audit_models
Create Date: 2026-09-22 18:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004_exception_models'
down_revision: Union[str, None] = '0003_fee_audit_models'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'reconciliation_exceptions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('org_id', sa.String(length=36), nullable=False),
        sa.Column('run_id', sa.String(length=36), nullable=True),
        sa.Column('exception_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False, server_default='low'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='open'),
        sa.Column('invoice_id', sa.String(length=36), nullable=True),
        sa.Column('gateway_txn_id', sa.String(length=36), nullable=True),
        sa.Column('settlement_batch_id', sa.String(length=36), nullable=True),
        sa.Column('settlement_line_id', sa.String(length=36), nullable=True),
        sa.Column('bank_credit_id', sa.String(length=36), nullable=True),
        sa.Column('expected_amount', sa.Numeric(precision=14, scale=2), nullable=False, server_default='0.00'),
        sa.Column('actual_amount', sa.Numeric(precision=14, scale=2), nullable=False, server_default='0.00'),
        sa.Column('discrepancy_amount', sa.Numeric(precision=14, scale=2), nullable=False, server_default='0.00'),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('root_cause_explanation', sa.Text(), nullable=False),
        sa.Column('suggested_action', sa.String(length=255), nullable=True),
        sa.Column('resolution_action', sa.String(length=50), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('resolved_by', sa.String(length=36), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['run_id'], ['reconciliation_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['gateway_txn_id'], ['gateway_txns.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['settlement_batch_id'], ['settlement_batches.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['settlement_line_id'], ['settlement_lines.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['bank_credit_id'], ['bank_credits.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_reconciliation_exceptions_org_id', 'reconciliation_exceptions', ['org_id'])
    op.create_index('ix_reconciliation_exceptions_run_id', 'reconciliation_exceptions', ['run_id'])
    op.create_index('ix_reconciliation_exceptions_exception_type', 'reconciliation_exceptions', ['exception_type'])
    op.create_index('ix_reconciliation_exceptions_severity', 'reconciliation_exceptions', ['severity'])
    op.create_index('ix_reconciliation_exceptions_status', 'reconciliation_exceptions', ['status'])
    op.create_index('ix_exceptions_org_status', 'reconciliation_exceptions', ['org_id', 'status'])
    op.create_index('ix_exceptions_org_type', 'reconciliation_exceptions', ['org_id', 'exception_type'])
    op.create_index('ix_exceptions_org_severity', 'reconciliation_exceptions', ['org_id', 'severity'])


def downgrade() -> None:
    op.drop_index('ix_exceptions_org_severity', table_name='reconciliation_exceptions')
    op.drop_index('ix_exceptions_org_type', table_name='reconciliation_exceptions')
    op.drop_index('ix_exceptions_org_status', table_name='reconciliation_exceptions')
    op.drop_index('ix_reconciliation_exceptions_status', table_name='reconciliation_exceptions')
    op.drop_index('ix_reconciliation_exceptions_severity', table_name='reconciliation_exceptions')
    op.drop_index('ix_reconciliation_exceptions_exception_type', table_name='reconciliation_exceptions')
    op.drop_index('ix_reconciliation_exceptions_run_id', table_name='reconciliation_exceptions')
    op.drop_index('ix_reconciliation_exceptions_org_id', table_name='reconciliation_exceptions')
    op.drop_table('reconciliation_exceptions')

