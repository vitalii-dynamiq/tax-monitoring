from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class MonitoringJob(Base, TimestampMixin):
    __tablename__ = "monitoring_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    jurisdiction_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jurisdictions.id"), nullable=False
    )
    job_type: Mapped[str] = mapped_column(Text, nullable=False, default="monitoring")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    trigger_type: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_by: Mapped[str] = mapped_column(Text, nullable=False, default="system")

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    result_summary: Mapped[dict | None] = mapped_column(JSONB)
    changes_detected: Mapped[int] = mapped_column(Integer, default=0)

    error_message: Mapped[str | None] = mapped_column(Text)
    error_traceback: Mapped[str | None] = mapped_column(Text)

    idempotency_key: Mapped[str | None] = mapped_column(Text, unique=True)

    # Relationships
    jurisdiction: Mapped["Jurisdiction"] = relationship(  # noqa: F821
        back_populates="monitoring_jobs"
    )

    __table_args__ = (
        Index("idx_jobs_jurisdiction", "jurisdiction_id"),
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_type", "job_type"),
        Index("idx_jobs_created", "created_at"),
    )
