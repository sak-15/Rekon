"""fee audit rate cards

Revision ID: 0003_fee_audit_models
Revises: 0002_reconciliation_models
Create Date: 2026-09-22 13:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003_fee_audit_models'
down_revision: Union[str, None] = '0002_reconciliation_models'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'gateway_rate_cards',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('org_id', sa.String(length=36), nullable=False),
        sa.Column('gateway', sa.String(length=50), nullable=False),
        sa.Column('payment_method', sa.String(length=50), nullable=False),
        sa.Column('card_network', sa.String(length=50), nullable=False, server_default='all'),
        sa.Column('is_international', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('rate_type', sa.String(length=50), nullable=False, server_default='percentage'),
        sa.Column('percentage_rate', sa.Numeric(precision=6, scale=4), nullable=False, server_default='0.0000'),
        sa.Column('flat_fee', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('gst_rate', sa.Numeric(precision=5, scale=4), nullable=False, server_default='0.1800'),
        sa.Column('cap_min_fee', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('cap_max_fee', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('effective_from', sa.DateTime(), nullable=True),
        sa.Column('effective_to', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['org_id'], ['organisations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'org_id', 'gateway', 'payment_method', 'card_network', 'is_international', 'is_active',
            name='uq_org_rate_card_rule'
        )
    )
    op.create_index('ix_gateway_rate_cards_org_id', 'gateway_rate_cards', ['org_id'])
    op.create_index('ix_gateway_rate_cards_gateway', 'gateway_rate_cards', ['gateway'])
    op.create_index('ix_gateway_rate_cards_payment_method', 'gateway_rate_cards', ['payment_method'])
    op.create_index('ix_gateway_rate_cards_is_active', 'gateway_rate_cards', ['is_active'])
    op.create_index(
        'ix_rate_cards_lookup', 'gateway_rate_cards',
        ['org_id', 'gateway', 'payment_method', 'is_active']
    )


def downgrade() -> None:
    op.drop_index('ix_rate_cards_lookup', table_name='gateway_rate_cards')
    op.drop_index('ix_gateway_rate_cards_is_active', table_name='gateway_rate_cards')
    op.drop_index('ix_gateway_rate_cards_payment_method', table_name='gateway_rate_cards')
    op.drop_index('ix_gateway_rate_cards_gateway', table_name='gateway_rate_cards')
    op.drop_index('ix_gateway_rate_cards_org_id', table_name='gateway_rate_cards')
    op.drop_table('gateway_rate_cards')

