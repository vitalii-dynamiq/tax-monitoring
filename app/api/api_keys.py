from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.services.api_key_service import (
    create_api_key,
    list_user_api_keys,
    revoke_api_key,
)

router = APIRouter(prefix="/v1/api-keys", tags=["API Keys"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


MAX_KEYS_PER_USER = 10


class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    expires_at: datetime | None = None


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    is_active: bool
    last_used_at: datetime | None
    expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateApiKeyResponse(ApiKeyResponse):
    raw_key: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=CreateApiKeyResponse, status_code=201)
async def create_key(
    body: CreateApiKeyRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key. The raw key is returned only in this response."""
    count_result = await db.execute(
        select(func.count(ApiKey.id)).where(
            ApiKey.user_id == user.id, ApiKey.is_active.is_(True)
        )
    )
    if count_result.scalar() >= MAX_KEYS_PER_USER:
        raise HTTPException(
            status_code=429,
            detail=f"Maximum {MAX_KEYS_PER_USER} active API keys per user",
        )
    api_key, raw_key = await create_api_key(
        db, user_id=user.id, name=body.name, expires_at=body.expires_at
    )
    return CreateApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        is_active=api_key.is_active,
        last_used_at=api_key.last_used_at,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
        raw_key=raw_key,
    )


@router.get("", response_model=list[ApiKeyResponse])
async def list_keys(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all API keys for the current user."""
    keys = await list_user_api_keys(db, user.id)
    return [ApiKeyResponse.model_validate(k) for k in keys]


@router.delete("/{key_id}", status_code=204)
async def revoke_key(
    key_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API key. Owners can revoke their own keys; admins can revoke any key."""
    revoked = await revoke_api_key(
        db, key_id=key_id, user_id=user.id, is_admin=user.role == "admin"
    )
    if not revoked:
        raise HTTPException(status_code=404, detail="API key not found")
