from datetime import date, datetime

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TaxRule(Base, TimestampMixin):
    __tablename__ = "tax_rules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tax_rate_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("tax_rates.id"))
    jurisdiction_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jurisdictions.id"), nullable=False
    )

    # LegalRuleML-inspired classification
    rule_type: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Conditions and actions (JSONB)
    conditions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    action: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Temporal
    effective_start: Mapped[date] = mapped_column(Date, nullable=False)
    effective_end: Mapped[date | None] = mapped_column(Date)
    enacted_date: Mapped[date | None] = mapped_column(Date)

    # Legal traceability
    legal_reference: Mapped[str | None] = mapped_column(Text)
    legal_uri: Mapped[str | None] = mapped_column(Text)
    authority_name: Mapped[str | None] = mapped_column(Text)

    # Lifecycle
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("tax_rules.id"))

    # Audit
    created_by: Mapped[str] = mapped_column(Text, nullable=False, default="system")
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column()

    # Relationships
    tax_rate: Mapped["TaxRate | None"] = relationship(back_populates="rules")  # noqa: F821
    jurisdiction: Mapped["Jurisdiction"] = relationship(back_populates="tax_rules")  # noqa: F821

    __table_args__ = (
        Index("idx_tax_rules_jurisdiction", "jurisdiction_id"),
        Index("idx_tax_rules_rate", "tax_rate_id"),
        Index("idx_tax_rules_type", "rule_type"),
        Index("idx_tax_rules_status", "status"),
    )
