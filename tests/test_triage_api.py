"""Integration tests for POST /v1/triage/run."""

import pytest


@pytest.fixture
def auth_headers():
    from app.config import settings
    return {"X-API-Key": settings.api_key}


class TestTriageRunEndpoint:
    async def test_triage_run_202(self, app_client, auth_headers):
        from app.config import settings
        if not settings.anthropic_api_key:
            # In the test env, the static settings has no API key.
            # Set one for this test to bypass the 503 guard.
            settings.anthropic_api_key = "sk-test"

        resp = await app_client.post(
            "/v1/triage/run",
            headers=auth_headers,
            json={"max_items": 20},
        )
        assert resp.status_code == 202, resp.text
        data = resp.json()
        assert data["job_type"] == "triage"
        assert data["status"] == "pending"
        assert data["jurisdiction_id"] is None
        assert data["triggered_by"] == "api"

    async def test_triage_run_409_when_already_running(self, app_client, auth_headers):
        from app.config import settings
        if not settings.anthropic_api_key:
            settings.anthropic_api_key = "sk-test"

        # First run
        r1 = await app_client.post(
            "/v1/triage/run", headers=auth_headers, json={"max_items": 10}
        )
        assert r1.status_code == 202

        # Manually leave it "pending" — second attempt should 409
        r2 = await app_client.post(
            "/v1/triage/run", headers=auth_headers, json={"max_items": 10}
        )
        assert r2.status_code == 409
        assert "already running" in r2.json()["detail"].lower()

    async def test_triage_run_503_without_anthropic_key(self, app_client, auth_headers):
        from app.config import settings

        original_key = settings.anthropic_api_key
        settings.anthropic_api_key = ""
        try:
            resp = await app_client.post(
                "/v1/triage/run",
                headers=auth_headers,
                json={"max_items": 20},
            )
            assert resp.status_code == 503
            assert "anthropic_api_key" in resp.json()["detail"].lower()
        finally:
            settings.anthropic_api_key = original_key

    async def test_triage_run_validates_max_items(self, app_client, auth_headers):
        from app.config import settings
        if not settings.anthropic_api_key:
            settings.anthropic_api_key = "sk-test"

        resp = await app_client.post(
            "/v1/triage/run",
            headers=auth_headers,
            json={"max_items": 999},  # over 200 cap
        )
        assert resp.status_code == 422


class TestListTriageRuns:
    async def test_returns_jobs_in_reverse_chronological_order(self, app_client, auth_headers):
        from app.config import settings
        if not settings.anthropic_api_key:
            settings.anthropic_api_key = "sk-test"

        # Dispatch 2 triage runs back-to-back. The second-attempt 409 path
        # means we need to mark the first as completed before triggering the
        # second — easiest: just hit /runs after a single dispatch.
        r = await app_client.post(
            "/v1/triage/run", headers=auth_headers, json={"max_items": 10}
        )
        assert r.status_code == 202
        new_id = r.json()["id"]

        runs = await app_client.get("/v1/triage/runs", headers=auth_headers)
        assert runs.status_code == 200
        rows = runs.json()
        assert len(rows) >= 1
        # All returned rows are triage jobs
        assert all(row["job_type"] == "triage" for row in rows)
        # The new one is included
        assert any(row["id"] == new_id for row in rows)
        # Reverse-chrono ordering: ids monotonically decrease (BIGSERIAL)
        ids = [row["id"] for row in rows]
        assert ids == sorted(ids, reverse=True)
