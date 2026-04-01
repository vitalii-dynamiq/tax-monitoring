from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class MonitoredSource(Base, TimestampMixin):
    __tablename__ = "monitored_sources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    jurisdiction_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jurisdictions.id")
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False, default="en")
    check_frequency_days: Mapped[int] = mapped_column(default=7)
    last_checked_at: Mapped[datetime | None] = mapped_column()
    last_content_hash: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_by: Mapped[str] = mapped_column(Text, nullable=False, default="system")

    # Relationships
    jurisdiction: Mapped["Jurisdiction | None"] = relationship(  # noqa: F821
        back_populates="monitored_sources"
    )

    __table_args__ = (
        Index("idx_sources_jurisdiction", "jurisdiction_id"),
        Index("idx_sources_status", "status"),
    )
