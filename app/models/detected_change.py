from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class DetectedChange(Base):
    __tablename__ = "detected_changes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("monitored_sources.id"))
    jurisdiction_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jurisdictions.id")
    )
    change_type: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(default=func.now())

    # AI extraction
    extracted_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    source_quote: Mapped[str | None] = mapped_column(Text)
    source_snapshot_url: Mapped[str | None] = mapped_column(Text)

    # Review workflow
    review_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column()
    review_notes: Mapped[str | None] = mapped_column(Text)

    # Applied entities
    applied_rate_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("tax_rates.id"))
    applied_rule_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("tax_rules.id"))

    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    source: Mapped["MonitoredSource | None"] = relationship()  # noqa: F821
    jurisdiction: Mapped["Jurisdiction | None"] = relationship()  # noqa: F821

    __table_args__ = (
        Index("idx_changes_status", "review_status"),
        Index("idx_changes_jurisdiction", "jurisdiction_id"),
        Index("idx_changes_detected", "detected_at"),
    )
