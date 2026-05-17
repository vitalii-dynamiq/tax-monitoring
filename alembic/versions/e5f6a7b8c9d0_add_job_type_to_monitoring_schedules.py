"""add job_type to monitoring_schedules

Revision ID: e5f6a7b8c9d0
Revises: 2f928776fcbb
Create Date: 2026-05-17 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = '2f928776fcbb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'monitoring_schedules',
        sa.Column('job_type', sa.Text(), nullable=False, server_default='monitoring'),
    )
    # Drop the auto-named unique constraint on jurisdiction_id. The original
    # migration created it via unnamed UniqueConstraint('jurisdiction_id'),
    # which Postgres names <table>_<col>_key. Use raw SQL with IF EXISTS in
    # case a custom name was assigned.
    op.execute(
        "ALTER TABLE monitoring_schedules "
        "DROP CONSTRAINT IF EXISTS monitoring_schedules_jurisdiction_id_key"
    )
    op.create_unique_constraint(
        'uq_schedules_jurisdiction_type',
        'monitoring_schedules',
        ['jurisdiction_id', 'job_type'],
    )
    op.create_index('idx_schedules_type', 'monitoring_schedules', ['job_type'])


def downgrade() -> None:
    op.drop_index('idx_schedules_type', table_name='monitoring_schedules')
    op.drop_constraint(
        'uq_schedules_jurisdiction_type',
        'monitoring_schedules',
        type_='unique',
    )
    op.create_unique_constraint(
        'monitoring_schedules_jurisdiction_id_key',
        'monitoring_schedules',
        ['jurisdiction_id'],
    )
    op.drop_column('monitoring_schedules', 'job_type')
