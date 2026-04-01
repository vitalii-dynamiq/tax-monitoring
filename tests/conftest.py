"""
Shared fixtures for TaxLens tests.

Provides:
- Async SQLite in-memory database for fast, isolated tests
- FastAPI test client with DB dependency override
- Booking context fixtures for rule engine tests
"""

from datetime import date
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import BigInteger, event
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.core.rule_engine import BookingContext
from app.models.base import Base

# ─── SQLite compatibility for PostgreSQL types ──────────────────────


@compiles(BigInteger, "sqlite")
def _compile_bigint_sqlite(type_, compiler, **kw):
    return "INTEGER"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(ARRAY, "sqlite")
def _compile_array_sqlite(type_, compiler, **kw):
    return "JSON"


# ─── Async database fixtures ────────────────────────────────────────


@pytest.fixture
async def async_engine():
    """Create a fresh async SQLite in-memory engine for each test."""
    import json as _json

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    # SQLite needs foreign key enforcement and JSON list serialization
    @event.listens_for(engine.sync_engine, "connect")
    def _setup_sqlite(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

        # Register adapter so Python lists serialize to JSON for ARRAY columns
        import sqlite3
        sqlite3.register_adapter(list, lambda val: _json.dumps(val))
        sqlite3.register_converter("JSON", lambda val: _json.loads(val))

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db(async_engine):
    """Provide an async session for a single test, rolled back after."""
    session_factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def app_client(async_engine):
    """FastAPI async test client with overridden DB dependency."""
    from app.db.session import get_db
    from app.main import app

    session_factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ─── Booking context fixtures ───────────────────────────────────────


@pytest.fixture
def nyc_context():
    """Standard NYC hotel booking context."""
    return BookingContext(
        jurisdiction_code="US-NY-NYC",
        stay_date=date(2025, 6, 15),
        checkout_date=date(2025, 6, 18),
        nightly_rate=Decimal("200"),
        nights=3,
        currency="USD",
        property_type="hotel",
        star_rating=4,
        number_of_guests=2,
    )


@pytest.fixture
def tokyo_context():
    """Standard Tokyo hotel booking context."""
    return BookingContext(
        jurisdiction_code="JP-13-TYO",
        stay_date=date(2025, 6, 15),
        checkout_date=date(2025, 6, 17),
        nightly_rate=Decimal("12000"),
        nights=2,
        currency="JPY",
        property_type="hotel",
    )


@pytest.fixture
def long_stay_context():
    """180+ night stay for permanent resident exemption testing."""
    return BookingContext(
        jurisdiction_code="US-NY-NYC",
        stay_date=date(2025, 1, 1),
        checkout_date=date(2025, 7, 1),
        nightly_rate=Decimal("150"),
        nights=181,
        currency="USD",
        property_type="hotel",
    )
