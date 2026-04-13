"""Add budget tracking models

Revision ID: 002_budget_tracking
Revises: 001_initial_schema
Create Date: 2026-04-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_budget_tracking'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create budgets table
    op.create_table(
        'budgets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('scope_type', sa.String(50), nullable=False, index=True),
        sa.Column('scope_value', sa.String(255), nullable=True, index=True),
        sa.Column('period', sa.String(50), nullable=False, server_default='monthly'),
        sa.Column('limit_usd', sa.Float(), nullable=False),
        sa.Column('soft_cap_threshold', sa.Float(), nullable=False, server_default='0.9'),
        sa.Column('hard_cap_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('alert_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_budgets_tenant_id', 'budgets', ['tenant_id'])
    op.create_index('ix_budgets_scope_type', 'budgets', ['scope_type'])
    op.create_index('ix_budgets_scope_value', 'budgets', ['scope_value'])

    # Create budget_consumptions table
    op.create_table(
        'budget_consumptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('budget_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('period_start', sa.Date(), nullable=False, index=True),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('consumed_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('request_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_soft_cap_exceeded', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_hard_cap_exceeded', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('soft_cap_exceeded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('hard_cap_exceeded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['budget_id'], ['budgets.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_budget_consumptions_budget_id', 'budget_consumptions', ['budget_id'])
    op.create_index('ix_budget_consumptions_tenant_id', 'budget_consumptions', ['tenant_id'])
    op.create_index('ix_budget_consumptions_period_start', 'budget_consumptions', ['period_start'])

    # Create cost_alerts table
    op.create_table(
        'cost_alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('alert_type', sa.String(100), nullable=False, index=True),
        sa.Column('severity', sa.String(50), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('budget_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('scope_type', sa.String(50), nullable=True),
        sa.Column('scope_value', sa.String(255), nullable=True),
        sa.Column('current_spend_usd', sa.Float(), nullable=True),
        sa.Column('budget_limit_usd', sa.Float(), nullable=True),
        sa.Column('is_resolved', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('notified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notification_sent', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), index=True),
        sa.ForeignKeyConstraint(['budget_id'], ['budgets.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_cost_alerts_tenant_id', 'cost_alerts', ['tenant_id'])
    op.create_index('ix_cost_alerts_alert_type', 'cost_alerts', ['alert_type'])
    op.create_index('ix_cost_alerts_severity', 'cost_alerts', ['severity'])
    op.create_index('ix_cost_alerts_created_at', 'cost_alerts', ['created_at'])


def downgrade() -> None:
    op.drop_table('cost_alerts')
    op.drop_table('budget_consumptions')
    op.drop_table('budgets')
