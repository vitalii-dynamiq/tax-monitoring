from sqlalchemy import BigInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TaxCategory(Base):
    __tablename__ = "tax_categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    level_0: Mapped[str] = mapped_column(Text, nullable=False)
    level_1: Mapped[str] = mapped_column(Text, nullable=False)
    level_2: Mapped[str] = mapped_column(Text, nullable=False)
    base_type: Mapped[str] = mapped_column(Text, nullable=False, default="room_rate")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
