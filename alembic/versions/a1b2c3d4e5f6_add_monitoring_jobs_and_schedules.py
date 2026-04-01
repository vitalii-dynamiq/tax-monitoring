"""add monitoring jobs and schedules

Revision ID: a1b2c3d4e5f6
Revises: 59f112253576
Create Date: 2026-03-27 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '59f112253576'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('monitoring_jobs',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('jurisdiction_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('trigger_type', sa.Text(), nullable=False),
        sa.Column('triggered_by', sa.Text(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('result_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('changes_detected', sa.Integer(), nullable=True, default=0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_traceback', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['jurisdiction_id'], ['jurisdictions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('idempotency_key'),
    )
    op.create_index('idx_jobs_jurisdiction', 'monitoring_jobs', ['jurisdiction_id'])
    op.create_index('idx_jobs_status', 'monitoring_jobs', ['status'])
    op.create_index('idx_jobs_created', 'monitoring_jobs', ['created_at'])

    op.create_table('monitoring_schedules',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('jurisdiction_id', sa.BigInteger(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('cadence', sa.Text(), nullable=False),
        sa.Column('cron_expression', sa.Text(), nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['jurisdiction_id'], ['jurisdictions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('jurisdiction_id'),
    )
    op.create_index('idx_schedules_enabled', 'monitoring_schedules', ['enabled'])
    op.create_index('idx_schedules_next_run', 'monitoring_schedules', ['next_run_at'])


def downgrade() -> None:
    op.drop_index('idx_schedules_next_run', table_name='monitoring_schedules')
    op.drop_index('idx_schedules_enabled', table_name='monitoring_schedules')
    op.drop_table('monitoring_schedules')
    op.drop_index('idx_jobs_created', table_name='monitoring_jobs')
    op.drop_index('idx_jobs_status', table_name='monitoring_jobs')
    op.drop_index('idx_jobs_jurisdiction', table_name='monitoring_jobs')
    op.drop_table('monitoring_jobs')
