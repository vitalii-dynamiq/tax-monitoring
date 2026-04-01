"""
Tests for user-managed API keys: create, list, use, revoke lifecycle.
"""

from datetime import UTC, datetime

import pytest

from app.services.api_key_service import generate_api_key, hash_api_key
from app.services.auth_service import create_access_token, create_user


@pytest.fixture
async def admin_user(db):
    """Create an admin user and return it."""
    return await create_user(db, "admin@test.io", "password123", role="admin")


@pytest.fixture
async def regular_user(db):
    """Create a regular user and return it."""
    return await create_user(db, "reader@test.io", "password123", role="user")


@pytest.fixture
def admin_token(admin_user):
    return create_access_token({"sub": admin_user.email, "role": admin_user.role})


@pytest.fixture
def user_token(regular_user):
    return create_access_token({"sub": regular_user.email, "role": regular_user.role})


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestApiKeyGeneration:
    def test_generate_key_format(self):
        key = generate_api_key()
        assert key.startswith("txl_")
        assert len(key) == 36  # "txl_" + 32 hex chars

    def test_generate_key_uniqueness(self):
        keys = {generate_api_key() for _ in range(100)}
        assert len(keys) == 100

    def test_hash_is_deterministic(self):
        key = "txl_abcdef1234567890abcdef1234567890"
        assert hash_api_key(key) == hash_api_key(key)

    def test_hash_differs_for_different_keys(self):
        k1 = generate_api_key()
        k2 = generate_api_key()
        assert hash_api_key(k1) != hash_api_key(k2)


class TestApiKeyCreateEndpoint:
    async def test_create_key(self, app_client, admin_token):
        resp = await app_client.post(
            "/v1/api-keys",
            json={"name": "Test Key"},
            headers=auth_header(admin_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Key"
        assert data["raw_key"].startswith("txl_")
        assert data["key_prefix"] == data["raw_key"][:8]
        assert data["is_active"] is True

    async def test_create_key_requires_auth(self, app_client):
        resp = await app_client.post("/v1/api-keys", json={"name": "No Auth"})
        assert resp.status_code == 401

    async def test_create_key_requires_name(self, app_client, admin_token):
        resp = await app_client.post(
            "/v1/api-keys",
            json={},
            headers=auth_header(admin_token),
        )
        assert resp.status_code == 422


class TestApiKeyListEndpoint:
    async def test_list_keys(self, app_client, admin_token):
        # Create two keys
        await app_client.post(
            "/v1/api-keys",
            json={"name": "Key 1"},
            headers=auth_header(admin_token),
        )
        await app_client.post(
            "/v1/api-keys",
            json={"name": "Key 2"},
            headers=auth_header(admin_token),
        )
        resp = await app_client.get("/v1/api-keys", headers=auth_header(admin_token))
        assert resp.status_code == 200
        keys = resp.json()
        assert len(keys) == 2
        # raw_key should NOT be in list response
        assert "raw_key" not in keys[0]

    async def test_list_only_own_keys(self, app_client, admin_token, user_token):
        await app_client.post(
            "/v1/api-keys",
            json={"name": "Admin Key"},
            headers=auth_header(admin_token),
        )
        await app_client.post(
            "/v1/api-keys",
            json={"name": "User Key"},
            headers=auth_header(user_token),
        )
        # User only sees their own key
        resp = await app_client.get("/v1/api-keys", headers=auth_header(user_token))
        keys = resp.json()
        assert len(keys) == 1
        assert keys[0]["name"] == "User Key"


class TestApiKeyRevokeEndpoint:
    async def test_revoke_own_key(self, app_client, admin_token):
        create_resp = await app_client.post(
            "/v1/api-keys",
            json={"name": "To Revoke"},
            headers=auth_header(admin_token),
        )
        key_id = create_resp.json()["id"]
        resp = await app_client.delete(
            f"/v1/api-keys/{key_id}", headers=auth_header(admin_token)
        )
        assert resp.status_code == 204

        # Key should now be inactive
        list_resp = await app_client.get(
            "/v1/api-keys", headers=auth_header(admin_token)
        )
        keys = list_resp.json()
        revoked = [k for k in keys if k["id"] == key_id]
        assert revoked[0]["is_active"] is False

    async def test_cannot_revoke_others_key(self, app_client, admin_token, user_token):
        create_resp = await app_client.post(
            "/v1/api-keys",
            json={"name": "Admin Key"},
            headers=auth_header(admin_token),
        )
        key_id = create_resp.json()["id"]
        # Regular user cannot revoke admin's key
        resp = await app_client.delete(
            f"/v1/api-keys/{key_id}", headers=auth_header(user_token)
        )
        assert resp.status_code == 404

    async def test_admin_can_revoke_any_key(self, app_client, admin_token, user_token):
        create_resp = await app_client.post(
            "/v1/api-keys",
            json={"name": "User Key"},
            headers=auth_header(user_token),
        )
        key_id = create_resp.json()["id"]
        # Admin can revoke user's key
        resp = await app_client.delete(
            f"/v1/api-keys/{key_id}", headers=auth_header(admin_token)
        )
        assert resp.status_code == 204

    async def test_revoke_nonexistent_key(self, app_client, admin_token):
        resp = await app_client.delete(
            "/v1/api-keys/99999", headers=auth_header(admin_token)
        )
        assert resp.status_code == 404


class TestApiKeyValidationUnit:
    """Unit tests for API key validation logic (not middleware integration)."""

    async def test_validate_returns_user_info(self, db, admin_user):
        """validate_api_key returns (email, role) for a valid key."""
        from app.services.api_key_service import create_api_key, validate_api_key

        _, raw_key = await create_api_key(db, admin_user.id, "unit test key")
        await db.commit()

        result = await validate_api_key(db, raw_key)
        assert result is not None
        assert result[0] == admin_user.email
        assert result[1] == admin_user.role

    async def test_validate_returns_none_for_invalid_key(self, db):
        from app.services.api_key_service import validate_api_key

        result = await validate_api_key(db, "txl_0000000000000000000000000000000")
        assert result is None

    async def test_validate_returns_none_for_revoked_key(self, db, admin_user):
        from app.services.api_key_service import create_api_key, revoke_api_key, validate_api_key

        api_key, raw_key = await create_api_key(db, admin_user.id, "revoke test")
        await db.commit()
        await revoke_api_key(db, api_key.id, admin_user.id)
        await db.commit()

        result = await validate_api_key(db, raw_key)
        assert result is None

    async def test_validate_returns_none_for_expired_key(self, db, admin_user):
        from datetime import timedelta

        from app.services.api_key_service import create_api_key, validate_api_key

        past = datetime.now(UTC) - timedelta(hours=1)
        _, raw_key = await create_api_key(db, admin_user.id, "expired key", expires_at=past)
        await db.commit()

        result = await validate_api_key(db, raw_key)
        assert result is None

    async def test_validate_returns_none_for_inactive_user(self, db, admin_user):
        from app.services.api_key_service import create_api_key, validate_api_key

        _, raw_key = await create_api_key(db, admin_user.id, "inactive user key")
        admin_user.is_active = False
        await db.commit()

        result = await validate_api_key(db, raw_key)
        assert result is None


class TestApiKeyMiddlewareIntegration:
    """Middleware-level tests for X-API-Key header handling."""

    async def test_invalid_key_rejected(self, app_client):
        resp = await app_client.get(
            "/v1/jurisdictions", headers={"X-API-Key": "txl_invalid000000000000000000000000"}
        )
        assert resp.status_code == 401

    async def test_static_api_key_still_works(self, app_client):
        """Backward-compatible static API key should still work."""
        from app.config import settings

        resp = await app_client.get(
            "/v1/jurisdictions", headers={"X-API-Key": settings.api_key}
        )
        # May get 200 or 500 (no DB data), but not 401
        assert resp.status_code != 401
