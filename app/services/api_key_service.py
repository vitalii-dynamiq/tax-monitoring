import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey
from app.models.user import User

KEY_PREFIX_LEN = 8  # "txl_a1b2" = 8 chars


def generate_api_key() -> str:
    """Generate a raw API key: txl_ + 32 random hex chars."""
    return f"txl_{secrets.token_hex(16)}"


def hash_api_key(raw_key: str) -> str:
    """SHA-256 hash of the raw API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def create_api_key(
    db: AsyncSession,
    user_id: int,
    name: str,
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    """Create a new API key. Returns (ApiKey record, raw_key)."""
    raw_key = generate_api_key()
    api_key = ApiKey(
        user_id=user_id,
        name=name,
        key_hash=hash_api_key(raw_key),
        key_prefix=raw_key[:KEY_PREFIX_LEN],
        expires_at=expires_at,
    )
    db.add(api_key)
    await db.flush()
    await db.refresh(api_key)
    return api_key, raw_key


async def validate_api_key(db: AsyncSession, raw_key: str) -> tuple[str, str] | None:
    """
    Validate a raw API key against the database.
    Returns (user_email, user_role) if valid, None otherwise.
    Also updates last_used_at on the matching key.
    """
    prefix = raw_key[:KEY_PREFIX_LEN]
    key_hash = hash_api_key(raw_key)

    result = await db.execute(
        select(ApiKey, User)
        .join(User, ApiKey.user_id == User.id)
        .where(
            ApiKey.key_prefix == prefix,
            ApiKey.is_active.is_(True),
            User.is_active.is_(True),
        )
    )
    rows = result.all()

    for api_key, user in rows:
        if not secrets.compare_digest(api_key.key_hash, key_hash):
            continue
        # Check expiry (handle both tz-aware and tz-naive datetimes for test compat)
        if api_key.expires_at:
            exp = api_key.expires_at
            now = datetime.now(UTC)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=UTC)
            if exp < now:
                return None
        # Update last_used_at
        await db.execute(
            update(ApiKey)
            .where(ApiKey.id == api_key.id)
            .values(last_used_at=datetime.now(UTC))
        )
        await db.commit()
        return user.email, user.role

    return None


async def list_user_api_keys(db: AsyncSession, user_id: int) -> list[ApiKey]:
    """List all API keys for a user (active and inactive)."""
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user_id)
        .order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def revoke_api_key(db: AsyncSession, key_id: int, user_id: int, is_admin: bool = False) -> bool:
    """Revoke an API key. Returns True if found and revoked."""
    query = select(ApiKey).where(ApiKey.id == key_id)
    if not is_admin:
        query = query.where(ApiKey.user_id == user_id)

    result = await db.execute(query)
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return False

    api_key.is_active = False
    await db.flush()
    return True
