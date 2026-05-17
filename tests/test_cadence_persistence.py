"""Regression test: PUT /v1/monitoring/schedules/{code} actually persists cadence.

User reported cadence changes weren't saving. Code review showed the path was
correct, but locking in a focused round-trip test catches any future regression.
"""

import pytest


@pytest.fixture
def auth_headers():
    from app.config import settings
    return {"X-API-Key": settings.api_key}


async def _create_country(client, headers, code: str):
    resp = await client.post(
        "/v1/jurisdictions",
        headers=headers,
        json={
            "code": code, "name": code, "jurisdiction_type": "country",
            "country_code": code, "currency_code": "USD",
        },
    )
    assert resp.status_code == 201, resp.text


class TestCadencePersistence:
    async def test_cadence_change_round_trips(self, app_client, auth_headers):
        """Set a schedule's cadence, then GET it and verify the DB returned it."""
        await _create_country(app_client, auth_headers, "PL")

        # Initial: enable with weekly cadence
        r1 = await app_client.put(
            "/v1/monitoring/schedules/PL",
            headers=auth_headers,
            json={"enabled": True, "cadence": "weekly", "job_type": "monitoring"},
        )
        assert r1.status_code == 200
        assert r1.json()["cadence"] == "weekly"

        # Change to daily
        r2 = await app_client.put(
            "/v1/monitoring/schedules/PL",
            headers=auth_headers,
            json={"cadence": "daily", "job_type": "monitoring"},
        )
        assert r2.status_code == 200
        assert r2.json()["cadence"] == "daily"

        # GET should report the persisted value
        r3 = await app_client.get(
            "/v1/monitoring/schedules/PL?job_type=monitoring",
            headers=auth_headers,
        )
        assert r3.status_code == 200
        assert r3.json()["cadence"] == "daily"

    async def test_cadence_change_recomputes_next_run(self, app_client, auth_headers):
        """When cadence changes on an enabled schedule, next_run_at is recomputed."""
        await _create_country(app_client, auth_headers, "FI")

        # daily vs monthly always land on different dates regardless of today's weekday
        r1 = await app_client.put(
            "/v1/monitoring/schedules/FI",
            headers=auth_headers,
            json={"enabled": True, "cadence": "monthly", "job_type": "monitoring"},
        )
        next_monthly = r1.json()["next_run_at"]
        assert next_monthly is not None

        r2 = await app_client.put(
            "/v1/monitoring/schedules/FI",
            headers=auth_headers,
            json={"cadence": "daily", "job_type": "monitoring"},
        )
        next_daily = r2.json()["next_run_at"]
        assert next_daily is not None
        # The two ISO timestamps must differ (daily fires sooner than monthly)
        assert next_daily != next_monthly

    async def test_disabling_clears_next_run(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers, "RO")
        r1 = await app_client.put(
            "/v1/monitoring/schedules/RO",
            headers=auth_headers,
            json={"enabled": True, "cadence": "daily", "job_type": "monitoring"},
        )
        assert r1.json()["next_run_at"] is not None

        r2 = await app_client.put(
            "/v1/monitoring/schedules/RO",
            headers=auth_headers,
            json={"enabled": False, "job_type": "monitoring"},
        )
        assert r2.json()["next_run_at"] is None

    async def test_custom_cron_requires_expression(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers, "NO")
        resp = await app_client.put(
            "/v1/monitoring/schedules/NO",
            headers=auth_headers,
            json={"enabled": True, "cadence": "custom", "job_type": "monitoring"},
        )
        assert resp.status_code == 400
        assert "cron_expression" in resp.json()["detail"].lower()
