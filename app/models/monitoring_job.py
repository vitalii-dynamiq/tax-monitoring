from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class MonitoringJob(Base, TimestampMixin):
    __tablename__ = "monitoring_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Nullable: monitoring + discovery always set a country; triage runs span
    # the whole pending queue and have no single jurisdiction.
    jurisdiction_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jurisdictions.id")
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

    # Agent telemetry (populated by AgentRunRecorder.flush)
    model: Mapped[str | None] = mapped_column(Text)
    system_prompt: Mapped[str | None] = mapped_column(Text)
    initial_user_prompt: Mapped[str | None] = mapped_column(Text)
    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cache_creation_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_web_search_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=0)

    # Relationships
    jurisdiction: Mapped["Jurisdiction | None"] = relationship(  # noqa: F821
        back_populates="monitoring_jobs",
        foreign_keys=[jurisdiction_id],
    )
    turns: Mapped[list["AgentRunTurn"]] = relationship(  # noqa: F821
        back_populates="job",
        order_by="AgentRunTurn.turn_index",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_jobs_jurisdiction", "jurisdiction_id"),
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_type", "job_type"),
        Index("idx_jobs_created", "created_at"),
    )
