"""Tests for POST /v1/jurisdictions/{code}/approve|reject."""

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.jurisdiction import Jurisdiction


@pytest.fixture
def auth_headers():
    from app.config import settings
    return {"X-API-Key": settings.api_key}


async def _create_pending_country(client, headers, code, name):
    resp = await client.post(
        "/v1/jurisdictions",
        headers=headers,
        json={
            "code": code, "name": name, "jurisdiction_type": "country",
            "country_code": code, "currency_code": "USD",
            "status": "pending",
        },
    )
    assert resp.status_code == 201, resp.text


class TestJurisdictionApprovalEndpoints:
    async def test_approve_flips_status_and_writes_audit_log(
        self, app_client, auth_headers, async_engine
    ):
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        await _create_pending_country(app_client, auth_headers, "TR", "Türkiye")

        resp = await app_client.post(
            "/v1/jurisdictions/TR/approve",
            headers=auth_headers,
            json={"reviewed_by": "alice", "review_notes": "verified"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "active"

        # Audit log entry written
        async with async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)() as db:
            target = (await db.execute(
                select(Jurisdiction).where(Jurisdiction.code == "TR")
            )).scalar_one()
            log = (await db.execute(
                select(AuditLog).where(
                    AuditLog.entity_type == "jurisdiction",
                    AuditLog.entity_id == target.id,
                )
            )).scalar_one()
            assert log.action == "status_change"
            assert log.new_values == {"status": "active"}
            assert log.changed_by == "alice"

    async def test_reject_flips_to_rejected(self, app_client, auth_headers):
        await _create_pending_country(app_client, auth_headers, "TT", "Trinidad and Tobago")
        resp = await app_client.post(
            "/v1/jurisdictions/TT/reject", headers=auth_headers, json={}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    async def test_approve_404_for_unknown(self, app_client, auth_headers):
        resp = await app_client.post(
            "/v1/jurisdictions/ZZ-NOPE/approve", headers=auth_headers, json={}
        )
        assert resp.status_code == 404
