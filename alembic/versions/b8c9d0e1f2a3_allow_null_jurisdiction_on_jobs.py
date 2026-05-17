"""allow null jurisdiction_id on monitoring_jobs

Triage runs span the whole pending queue and have no single jurisdiction.
Monitoring + discovery runs continue to set this column.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-05-18 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "monitoring_jobs",
        "jurisdiction_id",
        existing_type=__import__("sqlalchemy").BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    # Will fail if any triage rows exist with NULL jurisdiction_id — acceptable.
    op.alter_column(
        "monitoring_jobs",
        "jurisdiction_id",
        existing_type=__import__("sqlalchemy").BigInteger(),
        nullable=False,
    )
