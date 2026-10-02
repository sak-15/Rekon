"""reconciliation models

Revision ID: 0002_reconciliation_models
Revises: 0001_initial_schema
Create Date: 2026-09-22 11:36:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_reconciliation_models'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Reconciliation Runs
    op.create_table(
        'reconciliation_runs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('org_id', sa.String(length=36), nullable=False),
        sa.Column('initiated_by', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.String(length=1000), nullable=True),
        sa.Column('rule_config', sa.JSON(), nullable=True),
        sa.Column('total_invoices', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('matched_invoices', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('unmatched_invoices', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_txns', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('matched_txns', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('unmatched_txns', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_settlements', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('matched_settlements', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('unmatched_settlements', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_bank_credits', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('matched_bank_credits', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('unmatched_bank_credits', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('invoiced_amount', sa.Numeric(precision=14, scale=2), nullable=False, server_default='0.00'),
        sa.Column('collected_amount', sa.Numeric(precision=14, scale=2), nullable=False, server_default='0.00'),
        sa.Column('settled_amount', sa.Numeric(precision=14, scale=2), nullable=False, server_default='0.00'),
        sa.Column('bank_credited_amount', sa.Numeric(precision=14, scale=2), nullable=False, server_default='0.00'),
        sa.Column('discrepancy_amount', sa.Numeric(precision=14, scale=2), nullable=False, server_default='0.00'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['initiated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_reconciliation_runs_org_id', 'reconciliation_runs', ['org_id'])
    op.create_index('ix_reconciliation_runs_initiated_by', 'reconciliation_runs', ['initiated_by'])
    op.create_index('ix_reconciliation_runs_status', 'reconciliation_runs', ['status'])
    op.create_index('ix_reconciliation_runs_org_status', 'reconciliation_runs', ['org_id', 'status'])
    op.create_index('ix_reconciliation_runs_org_created', 'reconciliation_runs', ['org_id', 'created_at'])

    # 2. Reconciliation Matches
    op.create_table(
        'reconciliation_matches',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('org_id', sa.String(length=36), nullable=False),
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('layer', sa.String(length=50), nullable=False),
        sa.Column('invoice_id', sa.String(length=36), nullable=True),
        sa.Column('gateway_txn_id', sa.String(length=36), nullable=True),
        sa.Column('settlement_line_id', sa.String(length=36), nullable=True),
        sa.Column('settlement_batch_id', sa.String(length=36), nullable=True),
        sa.Column('bank_credit_id', sa.String(length=36), nullable=True),
        sa.Column('match_type', sa.String(length=50), nullable=False),
        sa.Column('confidence_score', sa.Numeric(precision=5, scale=2), nullable=False, server_default='100.00'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='matched'),
        sa.Column('amount_difference', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('match_details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['run_id'], ['reconciliation_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['gateway_txn_id'], ['gateway_txns.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['settlement_line_id'], ['settlement_lines.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['settlement_batch_id'], ['settlement_batches.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['bank_credit_id'], ['bank_credits.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_reconciliation_matches_org_id', 'reconciliation_matches', ['org_id'])
    op.create_index('ix_reconciliation_matches_run_id', 'reconciliation_matches', ['run_id'])
    op.create_index('ix_reconciliation_matches_layer', 'reconciliation_matches', ['layer'])
    op.create_index('ix_reconciliation_matches_invoice_id', 'reconciliation_matches', ['invoice_id'])
    op.create_index('ix_reconciliation_matches_gateway_txn_id', 'reconciliation_matches', ['gateway_txn_id'])
    op.create_index('ix_reconciliation_matches_settlement_line_id', 'reconciliation_matches', ['settlement_line_id'])
    op.create_index('ix_reconciliation_matches_settlement_batch_id', 'reconciliation_matches', ['settlement_batch_id'])
    op.create_index('ix_reconciliation_matches_bank_credit_id', 'reconciliation_matches', ['bank_credit_id'])
    op.create_index('ix_reconciliation_matches_org_layer', 'reconciliation_matches', ['org_id', 'layer'])
    op.create_index('ix_reconciliation_matches_run_layer', 'reconciliation_matches', ['run_id', 'layer'])


def downgrade() -> None:
    op.drop_table('reconciliation_matches')
    op.drop_table('reconciliation_runs')

