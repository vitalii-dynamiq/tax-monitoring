"""Integration tests for telemetry API endpoints.

GET /v1/monitoring/jobs/{id}/turns
GET /v1/monitoring/jobs/{id}/produced
GET /v1/monitoring/jobs/{id} (extended fields)
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.agent_run_turn import AgentRunTurn
from app.models.detected_change import DetectedChange


@pytest.fixture
def auth_headers():
    from app.config import settings
    return {"X-API-Key": settings.api_key}


async def _seed_job_with_telemetry(db, *, with_turns: bool = True):
    """Create a country + monitoring job + a couple of turns + produced entities."""
    from tests.factories import (
        create_jurisdiction,
        create_monitoring_job,
        create_tax_category,
        create_tax_rate,
    )

    country = await create_jurisdiction(db, code="AT", path="AT", country_code="AT")
    job = await create_monitoring_job(db, jurisdiction_id=country.id, status="completed")
    cat = await create_tax_category(db, code="occ_pct_at", name="AT occupancy")

    # Produced rate linked back to the job
    rate = await create_tax_rate(
        db,
        jurisdiction_id=country.id,
        tax_category_id=cat.id,
        rate_value=0.10,
    )
    rate.monitoring_job_id = job.id

    # Produced detected change
    change = DetectedChange(
        jurisdiction_id=country.id,
        change_type="new_tax",
        extracted_data={"foo": 1},
        confidence=Decimal("0.9"),
        applied_rate_id=rate.id,
        monitoring_job_id=job.id,
    )
    db.add(change)

    # Telemetry on the job itself
    job.model = "claude-sonnet-4-6"
    job.system_prompt = "SYS"
    job.initial_user_prompt = "PROMPT"
    job.total_input_tokens = 5000
    job.total_output_tokens = 1000
    job.total_web_search_count = 3
    job.estimated_cost_usd = Decimal("0.1234")

    if with_turns:
        now = datetime.now(UTC)
        for i in range(2):
            db.add(
                AgentRunTurn(
                    monitoring_job_id=job.id,
                    turn_index=i,
                    model="claude-sonnet-4-6",
                    stop_reason="tool_use" if i == 0 else "end_turn",
                    request_messages=[{"role": "user", "content": f"turn {i}"}],
                    response_content=[{"type": "text", "text": f"hi {i}"}],
                    input_tokens=2500,
                    output_tokens=500,
                    cache_creation_input_tokens=0,
                    cache_read_input_tokens=0,
                    web_search_count=1 if i == 0 else 2,
                    latency_ms=1000 + i * 100,
                    started_at=now + timedelta(seconds=i),
                    completed_at=now + timedelta(seconds=i + 1),
                )
            )

    await db.flush()
    return country, job, rate


class TestExtendedJobResponse:
    async def test_get_job_includes_telemetry(self, app_client, auth_headers, async_engine):
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        async with async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)() as db:
            _, job, _ = await _seed_job_with_telemetry(db)
            await db.commit()
            job_id = job.id

        resp = await app_client.get(f"/v1/monitoring/jobs/{job_id}", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["model"] == "claude-sonnet-4-6"
        assert data["system_prompt"] == "SYS"
        assert data["initial_user_prompt"] == "PROMPT"
        assert data["total_input_tokens"] == 5000
        assert data["total_output_tokens"] == 1000
        assert data["total_web_search_count"] == 3
        # Decimal serialised as string
        assert data["estimated_cost_usd"] == "0.1234"


class TestTurnsEndpoint:
    async def test_returns_turns_in_order(self, app_client, auth_headers, async_engine):
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        async with async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)() as db:
            _, job, _ = await _seed_job_with_telemetry(db)
            await db.commit()
            job_id = job.id

        resp = await app_client.get(
            f"/v1/monitoring/jobs/{job_id}/turns", headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        rows = resp.json()
        assert len(rows) == 2
        assert [r["turn_index"] for r in rows] == [0, 1]
        assert rows[0]["response_content"][0]["text"] == "hi 0"
        assert rows[0]["web_search_count"] == 1
        assert rows[1]["web_search_count"] == 2

    async def test_404_for_unknown_job(self, app_client, auth_headers):
        resp = await app_client.get(
            "/v1/monitoring/jobs/9999999/turns", headers=auth_headers
        )
        assert resp.status_code == 404


class TestProducedEndpoint:
    async def test_lists_only_entities_from_this_job(
        self, app_client, auth_headers, async_engine
    ):
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        async with async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)() as db:
            _, job, _ = await _seed_job_with_telemetry(db, with_turns=False)
            await db.commit()
            job_id = job.id

        resp = await app_client.get(
            f"/v1/monitoring/jobs/{job_id}/produced", headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["tax_rates"]) == 1
        assert data["tax_rates"][0]["jurisdiction_code"] == "AT"
        assert data["tax_rates"][0]["tax_category_code"] == "occ_pct_at"
        assert len(data["detected_changes"]) == 1
        assert data["detected_changes"][0]["change_type"] == "new_tax"
        assert data["tax_rules"] == []
        assert data["jurisdictions"] == []


class TestProducedTriageBranch:
    async def test_produced_for_triage_returns_audit_log_entities(
        self, app_client, auth_headers, async_engine
    ):
        """Triage runs don't create entities — Produced should query audit_log
        for the [via triage job #N] marker and return the rows the run touched."""
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from app.models.audit_log import AuditLog
        from tests.factories import (
            create_jurisdiction,
            create_monitoring_job,
            create_tax_category,
            create_tax_rate,
        )

        async with async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)() as db:
            country = await create_jurisdiction(db, code="LU", path="LU", country_code="LU")
            triage_job = await create_monitoring_job(
                db, jurisdiction_id=country.id, status="completed", job_type="triage",
            )
            cat = await create_tax_category(db, code="lu_cat", name="LU cat")
            rate = await create_tax_rate(
                db, jurisdiction_id=country.id, tax_category_id=cat.id, rate_value=0.05,
            )
            db.add(AuditLog(
                entity_type="tax_rate",
                entity_id=rate.id,
                action="status_change",
                changed_by="ai_triage",
                change_source="ai_triage",
                old_values={"status": "draft"},
                new_values={"status": "active"},
                change_reason=f"Source verified. [via triage job #{triage_job.id}]",
            ))
            await db.commit()
            triage_id = triage_job.id
            rate_id = rate.id

        resp = await app_client.get(
            f"/v1/monitoring/jobs/{triage_id}/produced",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["tax_rates"]) == 1
        assert data["tax_rates"][0]["id"] == rate_id
        assert data["jurisdictions"] == []
        assert data["tax_rules"] == []
        assert data["detected_changes"] == []
