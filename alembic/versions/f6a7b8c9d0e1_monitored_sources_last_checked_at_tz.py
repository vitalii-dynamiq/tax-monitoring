"""monitored_sources.last_checked_at use timestamptz

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-17 13:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE monitored_sources "
        "ALTER COLUMN last_checked_at TYPE timestamptz "
        "USING last_checked_at AT TIME ZONE 'UTC'"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE monitored_sources "
        "ALTER COLUMN last_checked_at TYPE timestamp "
        "USING last_checked_at AT TIME ZONE 'UTC'"
    )
