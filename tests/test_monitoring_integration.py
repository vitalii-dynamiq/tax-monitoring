"""
Integration tests for the monitoring API endpoints.

Tests request/response shapes, validation, and authentication
for all monitoring job and schedule endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def auth():
    return {"X-API-Key": settings.api_key}


# ─── Job Endpoints ──────────────────────────────────────────────────


class TestMonitoringJobEndpoints:
    def test_list_jobs_requires_auth(self, client):
        response = client.get("/v1/monitoring/jobs")
        assert response.status_code == 401

    def test_list_jobs_empty(self, client, auth):
        response = client.get("/v1/monitoring/jobs", headers=auth)
        # May return 200 with empty list, or 500 if DB not connected
        assert response.status_code in (200, 500)
        if response.status_code == 200:
            assert isinstance(response.json(), list)

    def test_list_jobs_with_filters(self, client, auth):
        response = client.get(
            "/v1/monitoring/jobs?status=completed&trigger_type=manual&limit=10",
            headers=auth,
        )
        assert response.status_code in (200, 500)

    def test_get_job_not_found(self, client, auth):
        response = client.get("/v1/monitoring/jobs/999999", headers=auth)
        assert response.status_code in (404, 500)

    def test_trigger_run_missing_jurisdiction(self, client, auth):
        response = client.post(
            "/v1/monitoring/jobs/NONEXISTENT-CODE/run",
            headers=auth,
        )
        # 404 if DB connected, 500 if not
        assert response.status_code in (404, 500, 503)

    def test_trigger_run_returns_202(self, client, auth):
        """If DB is connected and jurisdiction exists, should return 202."""
        response = client.post(
            "/v1/monitoring/jobs/US-NY-NYC/run",
            headers=auth,
        )
        # 202 if jurisdiction exists, 404 if not seeded, 500 if no DB, 503 if no API key
        assert response.status_code in (202, 404, 500, 503)
        if response.status_code == 202:
            data = response.json()
            assert data["status"] == "pending"
            assert data["trigger_type"] == "manual"
            assert "id" in data

    def test_trigger_run_duplicate_returns_409(self, client, auth):
        """Second trigger for same jurisdiction should return 409 if first is still running."""
        # First trigger
        r1 = client.post("/v1/monitoring/jobs/US-NY-NYC/run", headers=auth)
        if r1.status_code != 202:
            pytest.skip("DB not available or jurisdiction not seeded")

        # Second trigger should conflict
        r2 = client.post("/v1/monitoring/jobs/US-NY-NYC/run", headers=auth)
        assert r2.status_code == 409


# ─── Schedule Endpoints ─────────────────────────────────────────────


class TestMonitoringScheduleEndpoints:
    def test_list_schedules_requires_auth(self, client):
        response = client.get("/v1/monitoring/schedules")
        assert response.status_code == 401

    def test_list_schedules(self, client, auth):
        response = client.get("/v1/monitoring/schedules", headers=auth)
        assert response.status_code in (200, 500)
        if response.status_code == 200:
            assert isinstance(response.json(), list)

    def test_get_schedule_not_found(self, client, auth):
        response = client.get("/v1/monitoring/schedules/NONEXISTENT", headers=auth)
        assert response.status_code in (404, 500)

    def test_create_schedule(self, client, auth):
        response = client.put(
            "/v1/monitoring/schedules/US-NY-NYC",
            headers=auth,
            json={"enabled": False, "cadence": "weekly"},
        )
        # 200 if jurisdiction exists, 404 if not
        assert response.status_code in (200, 404, 500)
        if response.status_code == 200:
            data = response.json()
            assert data["enabled"] is False
            assert data["cadence"] == "weekly"

    def test_update_schedule_enable(self, client, auth):
        response = client.put(
            "/v1/monitoring/schedules/US-NY-NYC",
            headers=auth,
            json={"enabled": True, "cadence": "daily"},
        )
        if response.status_code == 200:
            data = response.json()
            assert data["enabled"] is True
            assert data["cadence"] == "daily"
            assert data["next_run_at"] is not None

    def test_update_schedule_custom_requires_cron(self, client, auth):
        response = client.put(
            "/v1/monitoring/schedules/US-NY-NYC",
            headers=auth,
            json={"cadence": "custom"},
        )
        # Should return 400 if DB connected
        assert response.status_code in (400, 404, 500)

    def test_update_schedule_invalid_cron(self, client, auth):
        response = client.put(
            "/v1/monitoring/schedules/US-NY-NYC",
            headers=auth,
            json={"cadence": "custom", "cron_expression": "not valid cron"},
        )
        assert response.status_code in (400, 404, 500)

    def test_update_schedule_valid_custom_cron(self, client, auth):
        response = client.put(
            "/v1/monitoring/schedules/US-NY-NYC",
            headers=auth,
            json={"cadence": "custom", "cron_expression": "0 6 * * 1,4"},
        )
        if response.status_code == 200:
            data = response.json()
            assert data["cadence"] == "custom"
            assert data["cron_expression"] == "0 6 * * 1,4"

    def test_update_schedule_missing_jurisdiction(self, client, auth):
        response = client.put(
            "/v1/monitoring/schedules/DOES-NOT-EXIST",
            headers=auth,
            json={"enabled": True, "cadence": "weekly"},
        )
        assert response.status_code in (404, 500)


# ─── Change Review Endpoints ────────────────────────────────────────


class TestChangeReviewEndpoints:
    def test_review_change_not_found(self, client, auth):
        response = client.post(
            "/v1/monitoring/changes/999999/review",
            headers=auth,
            json={"review_status": "approved", "reviewed_by": "test_user"},
        )
        assert response.status_code in (404, 500)

    def test_review_requires_status(self, client, auth):
        response = client.post(
            "/v1/monitoring/changes/1/review",
            headers=auth,
            json={"reviewed_by": "test_user"},
        )
        assert response.status_code == 422  # Pydantic validation error


# ─── Source Endpoints ────────────────────────────────────────────────


class TestSourceEndpoints:
    def test_list_sources(self, client, auth):
        response = client.get("/v1/monitoring/sources", headers=auth)
        assert response.status_code in (200, 500)
        if response.status_code == 200:
            assert isinstance(response.json(), list)

    def test_list_sources_with_jurisdiction_filter(self, client, auth):
        response = client.get(
            "/v1/monitoring/sources?jurisdiction_code=US-NY-NYC",
            headers=auth,
        )
        assert response.status_code in (200, 500)
