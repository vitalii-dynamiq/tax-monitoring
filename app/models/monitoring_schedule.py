from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class MonitoringSchedule(Base, TimestampMixin):
    __tablename__ = "monitoring_schedules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    jurisdiction_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jurisdictions.id"), unique=True, nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    cadence: Mapped[str] = mapped_column(Text, nullable=False, default="weekly")
    cron_expression: Mapped[str | None] = mapped_column(Text)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    jurisdiction: Mapped["Jurisdiction"] = relationship(  # noqa: F821
        back_populates="monitoring_schedule"
    )

    __table_args__ = (
        Index("idx_schedules_enabled", "enabled"),
        Index("idx_schedules_next_run", "next_run_at"),
    )
