
from sqlalchemy import BigInteger, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Jurisdiction(Base, TimestampMixin):
    __tablename__ = "jurisdictions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    local_name: Mapped[str | None] = mapped_column(Text)
    jurisdiction_type: Mapped[str] = mapped_column(Text, nullable=False)
    # ltree stored as text — we use raw SQL for ltree operations
    path: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("jurisdictions.id"), index=True
    )
    country_code: Mapped[str] = mapped_column(Text, nullable=False)
    subdivision_code: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str | None] = mapped_column(Text)
    currency_code: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_by: Mapped[str] = mapped_column(Text, nullable=False, default="system")

    # Relationships
    parent: Mapped["Jurisdiction | None"] = relationship(
        "Jurisdiction", remote_side="Jurisdiction.id", lazy="selectin"
    )
    tax_rates: Mapped[list["TaxRate"]] = relationship(  # noqa: F821
        back_populates="jurisdiction", lazy="selectin"
    )
    tax_rules: Mapped[list["TaxRule"]] = relationship(  # noqa: F821
        back_populates="jurisdiction", lazy="selectin"
    )
    monitored_sources: Mapped[list["MonitoredSource"]] = relationship(  # noqa: F821
        back_populates="jurisdiction", lazy="selectin"
    )
    monitoring_jobs: Mapped[list["MonitoringJob"]] = relationship(  # noqa: F821
        back_populates="jurisdiction", lazy="noload"
    )
    monitoring_schedule: Mapped["MonitoringSchedule | None"] = relationship(  # noqa: F821
        back_populates="jurisdiction", lazy="noload", uselist=False
    )

    __table_args__ = (
        Index("idx_jurisdictions_country", "country_code"),
        Index("idx_jurisdictions_type", "jurisdiction_type"),
    )
