"""add job_type to monitoring_jobs

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-27 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'monitoring_jobs',
        sa.Column('job_type', sa.Text(), nullable=False, server_default='monitoring'),
    )
    op.create_index('idx_jobs_type', 'monitoring_jobs', ['job_type'])


def downgrade() -> None:
    op.drop_index('idx_jobs_type', table_name='monitoring_jobs')
    op.drop_column('monitoring_jobs', 'job_type')
