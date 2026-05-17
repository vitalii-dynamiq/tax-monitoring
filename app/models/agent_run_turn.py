from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AgentRunTurn(Base, TimestampMixin):
    """One row per Anthropic Messages API call within a MonitoringJob.

    Lets admins debug the full agentic loop: prompts in, content out,
    tool calls, web searches, tokens, latency.
    """

    __tablename__ = "agent_run_turns"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    monitoring_job_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("monitoring_jobs.id", ondelete="CASCADE"), nullable=False
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    stop_reason: Mapped[str | None] = mapped_column(Text)

    request_messages: Mapped[list] = mapped_column(JSONB, nullable=False)
    response_content: Mapped[list] = mapped_column(JSONB, nullable=False)

    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_creation_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_read_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    web_search_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    job: Mapped["MonitoringJob"] = relationship(back_populates="turns")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("monitoring_job_id", "turn_index", name="uq_turn_per_job"),
        Index("idx_turns_job", "monitoring_job_id"),
    )
