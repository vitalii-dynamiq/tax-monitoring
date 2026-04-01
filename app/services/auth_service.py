import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with a random salt."""
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}${hashed}"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a salted SHA-256 hash."""
    try:
        salt, stored_hash = hashed.split("$", 1)
        computed = hashlib.sha256(f"{salt}{plain}".encode()).hexdigest()
        return secrets.compare_digest(computed, stored_hash)
    except (ValueError, AttributeError):
        return False


def create_access_token(data: dict) -> str:
    """Create a JWT access token with 24-hour expiry."""
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises JWTError on invalid/expired tokens."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Fetch a user by email address."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, email: str, password: str, role: str = "user") -> User:
    """Create a new user with a hashed password."""
    user = User(
        email=email,
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    """Authenticate a user by email and password. Returns the user or None.
    Implements account lockout after MAX_FAILED_ATTEMPTS failures."""
    user = await get_user_by_email(db, email)
    if user is None:
        return None
    if not user.is_active:
        return None
    # Check lockout
    if user.locked_until and user.locked_until > datetime.now(UTC):
        return None
    if not verify_password(password, user.password_hash):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.now(UTC) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        await db.commit()  # Must commit before endpoint raises HTTPException
        return None
    # Successful login — reset counters
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()
    return user
