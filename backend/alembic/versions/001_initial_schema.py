"""Initial schema for Adaptix AI

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-04-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create prompt_definitions table
    op.create_table(
        'prompt_definitions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('use_case', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('owner', sa.String(255), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_prompt_definitions_tenant_id', 'prompt_definitions', ['tenant_id'])

    # Create prompt_versions table
    op.create_table(
        'prompt_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('prompt_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('version_label', sa.String(100), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('prompt_text', sa.Text(), nullable=False),
        sa.Column('model_config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('max_tokens', sa.Integer(), nullable=True),
        sa.Column('guardrails_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('pii_masking_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('require_review', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('false'), index=True),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('activated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deactivated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deactivated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('review_status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('previous_version_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['prompt_id'], ['prompt_definitions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['previous_version_id'], ['prompt_versions.id']),
    )
    op.create_index('ix_prompt_versions_prompt_id', 'prompt_versions', ['prompt_id'])
    op.create_index('ix_prompt_versions_tenant_id', 'prompt_versions', ['tenant_id'])
    op.create_index('ix_prompt_versions_is_active', 'prompt_versions', ['is_active'])

    # Create ai_policies table
    op.create_table(
        'ai_policies',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('pii_masking_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('content_guardrails_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('rate_limit_per_minute', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('daily_token_budget', sa.Integer(), nullable=True),
        sa.Column('allowed_providers', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('fallback_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('require_manual_review', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('review_threshold_confidence', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true'), index=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_ai_policies_tenant_id', 'ai_policies', ['tenant_id'])
    op.create_index('ix_ai_policies_is_active', 'ai_policies', ['is_active'])

    # Create policy_revisions table
    op.create_table(
        'policy_revisions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('policy_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('revision_number', sa.Integer(), nullable=False),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('policy_snapshot', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['policy_id'], ['ai_policies.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_policy_revisions_policy_id', 'policy_revisions', ['policy_id'])
    op.create_index('ix_policy_revisions_tenant_id', 'policy_revisions', ['tenant_id'])

    # Create execution_requests table
    op.create_table(
        'execution_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('correlation_id', sa.String(255), nullable=True, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('prompt_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('prompt_version_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('module', sa.String(100), nullable=True, index=True),
        sa.Column('task_type', sa.String(100), nullable=True, index=True),
        sa.Column('input_context', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('input_hash', sa.String(64), nullable=True),
        sa.Column('model_provider', sa.String(100), nullable=False),
        sa.Column('model_id', sa.String(255), nullable=False),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('max_tokens', sa.Integer(), nullable=True),
        sa.Column('guardrails_applied', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('pii_masked', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('policy_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending', index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), index=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['prompt_id'], ['prompt_definitions.id']),
        sa.ForeignKeyConstraint(['prompt_version_id'], ['prompt_versions.id']),
        sa.ForeignKeyConstraint(['policy_id'], ['ai_policies.id']),
    )

    # Create execution_results table
    op.create_table(
        'execution_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('request_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True, index=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('output', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('raw_response', sa.Text(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_type', sa.String(100), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('estimated_cost', sa.Float(), nullable=True),
        sa.Column('cost_currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('phi_detected', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('guardrail_violations', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('warnings', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('hallucination_risk', sa.String(50), nullable=True),
        sa.Column('provider_request_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['request_id'], ['execution_requests.id'], ondelete='CASCADE'),
    )

    # Create usage_ledger_entries table
    op.create_table(
        'usage_ledger_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('request_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('module', sa.String(100), nullable=True, index=True),
        sa.Column('task_type', sa.String(100), nullable=True, index=True),
        sa.Column('model_provider', sa.String(100), nullable=False, index=True),
        sa.Column('model_id', sa.String(255), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('cost_currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('is_estimated', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('success', sa.Boolean(), nullable=False, index=True),
        sa.Column('error_type', sa.String(100), nullable=True, index=True),
        sa.Column('usage_date', sa.Date(), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), index=True),
        sa.ForeignKeyConstraint(['request_id'], ['execution_requests.id']),
    )

    # Create usage_aggregations table
    op.create_table(
        'usage_aggregations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('aggregation_date', sa.Date(), nullable=False, index=True),
        sa.Column('module', sa.String(100), nullable=True, index=True),
        sa.Column('model_provider', sa.String(100), nullable=False, index=True),
        sa.Column('total_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('successful_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('avg_latency_ms', sa.Float(), nullable=True),
        sa.Column('p50_latency_ms', sa.Float(), nullable=True),
        sa.Column('p95_latency_ms', sa.Float(), nullable=True),
        sa.Column('p99_latency_ms', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_usage_aggregations_date_tenant', 'usage_aggregations', ['aggregation_date', 'tenant_id'])

    # Create audit_events table
    op.create_table(
        'audit_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('event_type', sa.String(100), nullable=False, index=True),
        sa.Column('event_category', sa.String(50), nullable=False, index=True),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('actor_role', sa.String(100), nullable=True),
        sa.Column('actor_ip', sa.String(45), nullable=True),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('entity_type', sa.String(100), nullable=True, index=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('before_state', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('after_state', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('severity', sa.String(20), nullable=False, server_default='info'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), index=True),
    )

    # Create review_queue_items table
    op.create_table(
        'review_queue_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('item_type', sa.String(100), nullable=False, index=True),
        sa.Column('entity_type', sa.String(100), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('submitted_by', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('payload', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending', index=True),
        sa.Column('priority', sa.String(20), nullable=False, server_default='normal'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), index=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Create review_actions table
    op.create_table(
        'review_actions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('queue_item_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('actor_role', sa.String(100), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['queue_item_id'], ['review_queue_items.id'], ondelete='CASCADE'),
    )

    # Create system_health_snapshots table
    op.create_table(
        'system_health_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('overall_status', sa.String(50), nullable=False, index=True),
        sa.Column('healthy_components', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('degraded_components', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('down_components', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('active_alerts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('p95_latency_ms', sa.Float(), nullable=True),
        sa.Column('error_rate', sa.Float(), nullable=True),
        sa.Column('component_status', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), index=True),
    )

    # Create provider_health_checks table
    op.create_table(
        'provider_health_checks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('provider_name', sa.String(100), nullable=False, index=True),
        sa.Column('provider_region', sa.String(50), nullable=True),
        sa.Column('is_healthy', sa.Boolean(), nullable=False, index=True),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_type', sa.String(100), nullable=True),
        sa.Column('check_type', sa.String(50), nullable=False, server_default='ping'),
        sa.Column('checked_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), index=True),
    )


def downgrade() -> None:
    op.drop_table('provider_health_checks')
    op.drop_table('system_health_snapshots')
    op.drop_table('review_actions')
    op.drop_table('review_queue_items')
    op.drop_table('audit_events')
    op.drop_table('usage_aggregations')
    op.drop_table('usage_ledger_entries')
    op.drop_table('execution_results')
    op.drop_table('execution_requests')
    op.drop_table('policy_revisions')
    op.drop_table('ai_policies')
    op.drop_table('prompt_versions')
    op.drop_table('prompt_definitions')
