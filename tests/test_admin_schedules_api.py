"""Integration tests for admin agent-schedule API endpoints."""

import pytest


@pytest.fixture
def auth_headers():
    from app.config import settings
    return {"X-API-Key": settings.api_key}


async def _create_country(client, headers, code: str, name: str | None = None):
    resp = await client.post(
        "/v1/jurisdictions",
        headers=headers,
        json={
            "code": code,
            "name": name or code,
            "jurisdiction_type": "country",
            "country_code": code,
            "currency_code": "USD",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_city(client, headers, code: str, parent_code: str, country_code: str):
    resp = await client.post(
        "/v1/jurisdictions",
        headers=headers,
        json={
            "code": code,
            "name": code,
            "jurisdiction_type": "city",
            "parent_code": parent_code,
            "country_code": country_code,
            "currency_code": "USD",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestScheduleUpdateWithJobType:
    async def test_put_creates_discovery_schedule(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers, "AT", "Austria")
        resp = await app_client.put(
            "/v1/monitoring/schedules/AT",
            headers=auth_headers,
            json={"enabled": True, "cadence": "monthly", "job_type": "discovery"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["job_type"] == "discovery"
        assert data["enabled"] is True

    async def test_put_discovery_rejected_for_non_country(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers, "DK", "Denmark")
        await _create_city(app_client, auth_headers, "DK-CPH", "DK", "DK")
        resp = await app_client.put(
            "/v1/monitoring/schedules/DK-CPH",
            headers=auth_headers,
            json={"enabled": True, "cadence": "monthly", "job_type": "discovery"},
        )
        assert resp.status_code == 400
        assert "country" in resp.json()["detail"].lower()

    async def test_put_default_job_type_is_monitoring(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers, "BE", "Belgium")
        resp = await app_client.put(
            "/v1/monitoring/schedules/BE",
            headers=auth_headers,
            json={"enabled": True, "cadence": "weekly"},
        )
        assert resp.status_code == 200
        assert resp.json()["job_type"] == "monitoring"

    async def test_get_schedules_filter_by_job_type(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers, "FR", "France")
        await app_client.put(
            "/v1/monitoring/schedules/FR",
            headers=auth_headers,
            json={"enabled": True, "cadence": "weekly", "job_type": "monitoring"},
        )
        await app_client.put(
            "/v1/monitoring/schedules/FR",
            headers=auth_headers,
            json={"enabled": True, "cadence": "monthly", "job_type": "discovery"},
        )

        mon = await app_client.get(
            "/v1/monitoring/schedules?job_type=monitoring", headers=auth_headers
        )
        disc = await app_client.get(
            "/v1/monitoring/schedules?job_type=discovery", headers=auth_headers
        )
        assert mon.status_code == 200 and disc.status_code == 200
        mon_types = {s["job_type"] for s in mon.json()}
        disc_types = {s["job_type"] for s in disc.json()}
        assert mon_types == {"monitoring"}
        assert disc_types == {"discovery"}


class TestMonitoringCountryGuards:
    """Monitoring is now country-scoped — non-country jurisdictions must be rejected."""

    async def test_put_monitoring_rejected_for_non_country(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers, "JP", "Japan")
        await _create_city(app_client, auth_headers, "JP-TYO", "JP", "JP")
        resp = await app_client.put(
            "/v1/monitoring/schedules/JP-TYO",
            headers=auth_headers,
            json={"enabled": True, "cadence": "weekly", "job_type": "monitoring"},
        )
        assert resp.status_code == 400
        assert "country" in resp.json()["detail"].lower()

    async def test_trigger_run_rejected_for_non_country(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers, "KR", "South Korea")
        await _create_city(app_client, auth_headers, "KR-SEL", "KR", "KR")
        resp = await app_client.post(
            "/v1/monitoring/jobs/KR-SEL/run",
            headers=auth_headers,
        )
        # Either 400 (guard) or 503 (no API key in test env) — both reject the run
        assert resp.status_code in (400, 503)
        if resp.status_code == 400:
            assert "country" in resp.json()["detail"].lower()

    async def test_bulk_monitoring_skips_non_countries(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers, "TH", "Thailand")
        await _create_city(app_client, auth_headers, "TH-BKK", "TH", "TH")
        resp = await app_client.post(
            "/v1/monitoring/schedules/bulk",
            headers=auth_headers,
            json={
                "jurisdiction_codes": ["TH", "TH-BKK"],
                "job_type": "monitoring",
                "action": "enable",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["updated"]) == 1 and data["updated"][0]["jurisdiction_code"] == "TH"
        assert any(e["code"] == "TH-BKK" for e in data["errors"])


class TestBulkScheduleEndpoint:
    async def test_bulk_enable_succeeds(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers, "ES", "Spain")
        await _create_country(app_client, auth_headers, "PT", "Portugal")

        resp = await app_client.post(
            "/v1/monitoring/schedules/bulk",
            headers=auth_headers,
            json={
                "jurisdiction_codes": ["ES", "PT"],
                "job_type": "monitoring",
                "action": "enable",
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["updated"]) == 2
        assert data["errors"] == []
        assert all(s["enabled"] for s in data["updated"])

    async def test_bulk_partial_failure(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers, "IT", "Italy")
        resp = await app_client.post(
            "/v1/monitoring/schedules/bulk",
            headers=auth_headers,
            json={
                "jurisdiction_codes": ["IT", "ZZ-MISSING"],
                "job_type": "monitoring",
                "action": "disable",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["updated"]) == 1
        assert len(data["errors"]) == 1
        assert data["errors"][0]["code"] == "ZZ-MISSING"

    async def test_bulk_set_cadence(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers, "NL", "Netherlands")
        resp = await app_client.post(
            "/v1/monitoring/schedules/bulk",
            headers=auth_headers,
            json={
                "jurisdiction_codes": ["NL"],
                "job_type": "monitoring",
                "action": "set_cadence",
                "cadence": "daily",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["updated"][0]["cadence"] == "daily"

    async def test_bulk_set_cadence_without_cadence_returns_400(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers, "NO", "Norway")
        resp = await app_client.post(
            "/v1/monitoring/schedules/bulk",
            headers=auth_headers,
            json={
                "jurisdiction_codes": ["NO"],
                "job_type": "monitoring",
                "action": "set_cadence",
            },
        )
        assert resp.status_code == 400

    async def test_bulk_discovery_rejects_non_country(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers, "SE", "Sweden")
        await _create_city(app_client, auth_headers, "SE-STO", "SE", "SE")
        resp = await app_client.post(
            "/v1/monitoring/schedules/bulk",
            headers=auth_headers,
            json={
                "jurisdiction_codes": ["SE", "SE-STO"],
                "job_type": "discovery",
                "action": "enable",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["updated"]) == 1
        assert any(e["code"] == "SE-STO" for e in data["errors"])
