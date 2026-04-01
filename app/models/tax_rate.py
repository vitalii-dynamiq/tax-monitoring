from datetime import date, datetime

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TaxRate(Base, TimestampMixin):
    __tablename__ = "tax_rates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    jurisdiction_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jurisdictions.id"), nullable=False
    )
    tax_category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tax_categories.id"), nullable=False
    )

    # Rate definition
    rate_type: Mapped[str] = mapped_column(Text, nullable=False)  # percentage, flat, tiered
    rate_value: Mapped[float | None] = mapped_column(Numeric(12, 6))
    currency_code: Mapped[str | None] = mapped_column(Text)

    # Tiered rates
    tiers: Mapped[dict | None] = mapped_column(JSONB)
    tier_type: Mapped[str | None] = mapped_column(Text)  # single_amount, marginal_rate, threshold

    # Temporal validity (three dimensions from LegalRuleML)
    enacted_date: Mapped[date | None] = mapped_column(Date)
    effective_start: Mapped[date] = mapped_column(Date, nullable=False)
    effective_end: Mapped[date | None] = mapped_column(Date)  # null = infinity
    applicability_start: Mapped[date | None] = mapped_column(Date)
    announcement_date: Mapped[date | None] = mapped_column(Date)

    # Calculation ordering (for cascading taxes)
    calculation_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    base_includes: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=["base_amount"]
    )

    # Legal reference
    legal_reference: Mapped[str | None] = mapped_column(Text)
    legal_uri: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    authority_name: Mapped[str | None] = mapped_column(Text)

    # Versioning & Lifecycle
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("tax_rates.id"))
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")

    # Collection & tax base
    collection_model: Mapped[str | None] = mapped_column(Text)  # property, platform, both, guest
    taxable_amount_rule: Mapped[str | None] = mapped_column(Text)  # room_rate, total_consideration, net_rate

    # Audit
    created_by: Mapped[str] = mapped_column(Text, nullable=False, default="system")
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column()
    review_notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    jurisdiction: Mapped["Jurisdiction"] = relationship(back_populates="tax_rates")  # noqa: F821
    tax_category: Mapped["TaxCategory"] = relationship(lazy="joined")  # noqa: F821
    rules: Mapped[list["TaxRule"]] = relationship(back_populates="tax_rate", lazy="selectin")  # noqa: F821

    __table_args__ = (
        Index("idx_tax_rates_jurisdiction", "jurisdiction_id"),
        Index("idx_tax_rates_status", "status"),
    )
