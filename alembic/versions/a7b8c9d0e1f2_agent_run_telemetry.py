"""agent run telemetry: turns table, job telemetry columns, entity back-refs

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-17 14:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── agent_run_turns ───────────────────────────────────────────────
    op.create_table(
        'agent_run_turns',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('monitoring_job_id', sa.BigInteger(), nullable=False),
        sa.Column('turn_index', sa.Integer(), nullable=False),
        sa.Column('model', sa.Text(), nullable=False),
        sa.Column('stop_reason', sa.Text(), nullable=True),
        sa.Column('request_messages', sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column('response_content', sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cache_creation_input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cache_read_input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('web_search_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('latency_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['monitoring_job_id'], ['monitoring_jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('monitoring_job_id', 'turn_index', name='uq_turn_per_job'),
    )
    op.create_index('idx_turns_job', 'agent_run_turns', ['monitoring_job_id'])

    # ── monitoring_jobs: telemetry columns ────────────────────────────
    with op.batch_alter_table('monitoring_jobs') as batch:
        batch.add_column(sa.Column('model', sa.Text(), nullable=True))
        batch.add_column(sa.Column('system_prompt', sa.Text(), nullable=True))
        batch.add_column(sa.Column('initial_user_prompt', sa.Text(), nullable=True))
        batch.add_column(sa.Column('total_input_tokens', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('total_output_tokens', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('total_cache_creation_tokens', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('total_cache_read_tokens', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('total_web_search_count', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('estimated_cost_usd', sa.Numeric(10, 4), nullable=False, server_default='0'))

    # ── back-references on produced entities ──────────────────────────
    for table in ('detected_changes', 'tax_rates', 'tax_rules', 'jurisdictions'):
        op.add_column(
            table,
            sa.Column('monitoring_job_id', sa.BigInteger(), nullable=True),
        )
        op.create_foreign_key(
            f'fk_{table}_monitoring_job',
            table,
            'monitoring_jobs',
            ['monitoring_job_id'],
            ['id'],
            ondelete='SET NULL',
        )
        # index name aligns with the model __table_args__
        idx_name = {
            'detected_changes': 'idx_changes_monitoring_job',
            'tax_rates': 'idx_tax_rates_monitoring_job',
            'tax_rules': 'idx_tax_rules_monitoring_job',
            'jurisdictions': 'idx_jurisdictions_monitoring_job',
        }[table]
        op.create_index(idx_name, table, ['monitoring_job_id'])


def downgrade() -> None:
    for table, idx in (
        ('jurisdictions', 'idx_jurisdictions_monitoring_job'),
        ('tax_rules', 'idx_tax_rules_monitoring_job'),
        ('tax_rates', 'idx_tax_rates_monitoring_job'),
        ('detected_changes', 'idx_changes_monitoring_job'),
    ):
        op.drop_index(idx, table_name=table)
        op.drop_constraint(f'fk_{table}_monitoring_job', table, type_='foreignkey')
        op.drop_column(table, 'monitoring_job_id')

    with op.batch_alter_table('monitoring_jobs') as batch:
        for col in (
            'estimated_cost_usd', 'total_web_search_count',
            'total_cache_read_tokens', 'total_cache_creation_tokens',
            'total_output_tokens', 'total_input_tokens',
            'initial_user_prompt', 'system_prompt', 'model',
        ):
            batch.drop_column(col)

    op.drop_index('idx_turns_job', table_name='agent_run_turns')
    op.drop_table('agent_run_turns')
