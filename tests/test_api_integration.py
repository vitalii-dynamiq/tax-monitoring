"""
End-to-end integration tests for TaxLens FastAPI API endpoints.

Uses a real async SQLite in-memory database via the ``app_client`` fixture
from conftest.py.  Every test method is async and sends HTTP requests through
``httpx.AsyncClient``.
"""

import pytest


@pytest.fixture
def auth_headers():
    from app.config import settings
    return {"X-API-Key": settings.api_key}


# ── helpers ──────────────────────────────────────────────────────────


async def _create_country(client, headers, code="US", name="United States", currency="USD"):
    """Create a country jurisdiction and return the response JSON."""
    resp = await client.post(
        "/v1/jurisdictions",
        headers=headers,
        json={
            "code": code,
            "name": name,
            "jurisdiction_type": "country",
            "country_code": code,
            "currency_code": currency,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_state(client, headers, code="US-NY", name="New York",
                        parent_code="US", country_code="US", currency="USD"):
    """Create a state jurisdiction and return the response JSON."""
    resp = await client.post(
        "/v1/jurisdictions",
        headers=headers,
        json={
            "code": code,
            "name": name,
            "jurisdiction_type": "state",
            "parent_code": parent_code,
            "country_code": country_code,
            "currency_code": currency,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_city(client, headers, code="US-NY-NYC", name="New York City",
                       parent_code="US-NY", country_code="US", currency="USD"):
    """Create a city jurisdiction and return the response JSON."""
    resp = await client.post(
        "/v1/jurisdictions",
        headers=headers,
        json={
            "code": code,
            "name": name,
            "jurisdiction_type": "city",
            "parent_code": parent_code,
            "country_code": country_code,
            "currency_code": currency,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_hierarchy(client, headers):
    """Create a full US > NY > NYC hierarchy and return all three response dicts."""
    country = await _create_country(client, headers)
    state = await _create_state(client, headers)
    city = await _create_city(client, headers)
    return country, state, city


async def _create_tax_category(client, headers):
    """Insert a TaxCategory row directly via the DB (no API endpoint exists)."""
    # We need to insert directly since there is no tax-category API.
    # Access the ASGI app's dependency override to get a session.
    from sqlalchemy import text

    from app.db.session import get_db
    from app.main import app

    override = app.dependency_overrides.get(get_db)
    if override is None:
        pytest.skip("DB override not available")

    async for session in override():
        await session.execute(
            text(
                "INSERT INTO tax_categories "
                "(id, code, name, description, level_0, level_1, level_2, base_type, metadata) "
                "VALUES (:id, :code, :name, :desc, :l0, :l1, :l2, :bt, :meta)"
            ),
            {
                "id": 1,
                "code": "HOTEL_OCCUPANCY",
                "name": "Hotel Occupancy Tax",
                "desc": "Tax on hotel room stays",
                "l0": "accommodation",
                "l1": "hotel",
                "l2": "occupancy",
                "bt": "room_rate",
                "meta": "{}",
            },
        )
        await session.commit()
        break


async def _create_rate(client, headers, jurisdiction_code="US-NY-NYC",
                       rate_value=8.875, effective_start="2025-01-01"):
    """Create a percentage tax rate and return the response JSON."""
    resp = await client.post(
        "/v1/rates",
        headers=headers,
        json={
            "jurisdiction_code": jurisdiction_code,
            "tax_category_code": "HOTEL_OCCUPANCY",
            "rate_type": "percentage",
            "rate_value": rate_value,
            "effective_start": effective_start,
            "status": "active",
            "created_by": "test",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Test classes ─────────────────────────────────────────────────────


class TestJurisdictionsCRUD:
    """Jurisdiction CRUD and hierarchy operations."""

    @pytest.mark.asyncio
    async def test_create_country(self, app_client, auth_headers):
        country = await _create_country(app_client, auth_headers)
        assert country["code"] == "US"
        assert country["name"] == "United States"
        assert country["jurisdiction_type"] == "country"
        assert country["country_code"] == "US"
        assert country["currency_code"] == "USD"
        assert country["status"] == "active"
        assert country["parent_id"] is None
        assert "id" in country
        assert "created_at" in country

    @pytest.mark.asyncio
    async def test_create_hierarchy(self, app_client, auth_headers):
        country, state, city = await _create_hierarchy(app_client, auth_headers)

        assert state["parent_id"] == country["id"]
        assert city["parent_id"] == state["id"]

        # Paths should reflect the hierarchy
        assert country["path"] == "US"
        assert "NY" in state["path"]
        assert "NYC" in city["path"]

    @pytest.mark.asyncio
    async def test_list_jurisdictions(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)

        resp = await app_client.get("/v1/jurisdictions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 3

    @pytest.mark.asyncio
    async def test_list_filter_by_country_code(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)

        resp = await app_client.get(
            "/v1/jurisdictions", headers=auth_headers, params={"country_code": "US"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert all(j["country_code"] == "US" for j in data)

    @pytest.mark.asyncio
    async def test_list_filter_by_type(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)

        resp = await app_client.get(
            "/v1/jurisdictions",
            headers=auth_headers,
            params={"jurisdiction_type": "city"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["code"] == "US-NY-NYC"

    @pytest.mark.asyncio
    async def test_list_filter_by_status(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)

        resp = await app_client.get(
            "/v1/jurisdictions",
            headers=auth_headers,
            params={"status": "active"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    @pytest.mark.asyncio
    async def test_list_filter_by_parent_code(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)

        resp = await app_client.get(
            "/v1/jurisdictions",
            headers=auth_headers,
            params={"parent_code": "US"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["code"] == "US-NY"

    @pytest.mark.asyncio
    async def test_list_search_by_name(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)

        resp = await app_client.get(
            "/v1/jurisdictions",
            headers=auth_headers,
            params={"q": "York"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # "New York" and "New York City" match
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_get_by_code(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)

        resp = await app_client.get("/v1/jurisdictions/US-NY", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "US-NY"
        assert data["name"] == "New York"

    @pytest.mark.asyncio
    async def test_get_by_code_not_found(self, app_client, auth_headers):
        resp = await app_client.get("/v1/jurisdictions/XX-NOPE", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_children(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)

        resp = await app_client.get("/v1/jurisdictions/US/children", headers=auth_headers)
        assert resp.status_code == 200
        children = resp.json()
        assert len(children) == 1
        assert children[0]["code"] == "US-NY"

    @pytest.mark.asyncio
    async def test_get_children_of_state(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)

        resp = await app_client.get("/v1/jurisdictions/US-NY/children", headers=auth_headers)
        assert resp.status_code == 200
        children = resp.json()
        assert len(children) == 1
        assert children[0]["code"] == "US-NY-NYC"

    @pytest.mark.asyncio
    async def test_get_ancestors(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)

        resp = await app_client.get("/v1/jurisdictions/US-NY-NYC/ancestors", headers=auth_headers)
        assert resp.status_code == 200
        ancestors = resp.json()
        assert len(ancestors) == 2
        assert ancestors[0]["code"] == "US"
        assert ancestors[1]["code"] == "US-NY"

    @pytest.mark.asyncio
    async def test_get_ancestors_of_country(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers)

        resp = await app_client.get("/v1/jurisdictions/US/ancestors", headers=auth_headers)
        assert resp.status_code == 200
        ancestors = resp.json()
        assert len(ancestors) == 0

    @pytest.mark.asyncio
    async def test_update_jurisdiction(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers)

        resp = await app_client.put(
            "/v1/jurisdictions/US",
            headers=auth_headers,
            json={"name": "United States of America", "timezone": "America/New_York"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "United States of America"
        assert data["timezone"] == "America/New_York"

    @pytest.mark.asyncio
    async def test_update_jurisdiction_status(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers)

        resp = await app_client.put(
            "/v1/jurisdictions/US",
            headers=auth_headers,
            json={"status": "inactive"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "inactive"

    @pytest.mark.asyncio
    async def test_update_not_found(self, app_client, auth_headers):
        resp = await app_client.put(
            "/v1/jurisdictions/NOPE",
            headers=auth_headers,
            json={"name": "Nope"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_bulk_create(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers)

        resp = await app_client.post(
            "/v1/jurisdictions/bulk",
            headers=auth_headers,
            json={
                "parent_code": "US",
                "children": [
                    {
                        "code": "US-CA",
                        "name": "California",
                        "jurisdiction_type": "state",
                        "country_code": "US",
                        "currency_code": "USD",
                    },
                    {
                        "code": "US-TX",
                        "name": "Texas",
                        "jurisdiction_type": "state",
                        "country_code": "US",
                        "currency_code": "USD",
                    },
                ],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 2
        codes = {j["code"] for j in data}
        assert codes == {"US-CA", "US-TX"}
        # Both should have parent_id pointing to the country
        country_resp = await app_client.get("/v1/jurisdictions/US", headers=auth_headers)
        country_id = country_resp.json()["id"]
        assert all(j["parent_id"] == country_id for j in data)

    @pytest.mark.asyncio
    async def test_bulk_create_parent_not_found(self, app_client, auth_headers):
        resp = await app_client.post(
            "/v1/jurisdictions/bulk",
            headers=auth_headers,
            json={
                "parent_code": "NOPE",
                "children": [
                    {
                        "code": "NOPE-X",
                        "name": "X",
                        "jurisdiction_type": "state",
                        "country_code": "NO",
                        "currency_code": "NOK",
                    },
                ],
            },
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_duplicate_code_returns_409(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers)

        resp = await app_client.post(
            "/v1/jurisdictions",
            headers=auth_headers,
            json={
                "code": "US",
                "name": "Duplicate",
                "jurisdiction_type": "country",
                "country_code": "US",
                "currency_code": "USD",
            },
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_auth_required(self, app_client):
        """Requests without X-API-Key header are rejected."""
        resp = await app_client.get("/v1/jurisdictions")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_api_key(self, app_client):
        resp = await app_client.get(
            "/v1/jurisdictions", headers={"X-API-Key": "wrong-key"}
        )
        assert resp.status_code == 401


class TestTaxRatesCRUD:
    """Tax rate CRUD, lookup, approve, reject, and bulk operations."""

    @pytest.mark.asyncio
    async def test_create_rate(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)
        await _create_tax_category(app_client, auth_headers)

        rate = await _create_rate(app_client, auth_headers)
        assert rate["rate_type"] == "percentage"
        assert rate["rate_value"] == 8.875
        assert rate["status"] == "active"
        assert rate["jurisdiction_code"] == "US-NY-NYC"
        assert rate["tax_category_code"] == "HOTEL_OCCUPANCY"
        assert rate["effective_start"] == "2025-01-01"
        assert rate["version"] == 1
        assert "id" in rate

    @pytest.mark.asyncio
    async def test_list_rates(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)
        await _create_tax_category(app_client, auth_headers)
        await _create_rate(app_client, auth_headers)

        resp = await app_client.get("/v1/rates", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_list_rates_filter_by_jurisdiction(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)
        await _create_tax_category(app_client, auth_headers)
        await _create_rate(app_client, auth_headers)

        resp = await app_client.get(
            "/v1/rates",
            headers=auth_headers,
            params={"jurisdiction_code": "US-NY-NYC"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        resp = await app_client.get(
            "/v1/rates",
            headers=auth_headers,
            params={"jurisdiction_code": "US"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    @pytest.mark.asyncio
    async def test_list_rates_filter_by_category(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)
        await _create_tax_category(app_client, auth_headers)
        await _create_rate(app_client, auth_headers)

        resp = await app_client.get(
            "/v1/rates",
            headers=auth_headers,
            params={"category_code": "HOTEL_OCCUPANCY"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_get_rate_by_id(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)
        await _create_tax_category(app_client, auth_headers)
        rate = await _create_rate(app_client, auth_headers)

        resp = await app_client.get(
            f"/v1/rates/{rate['id']}", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == rate["id"]
        assert data["rate_value"] == 8.875

    @pytest.mark.asyncio
    async def test_get_rate_not_found(self, app_client, auth_headers):
        resp = await app_client.get("/v1/rates/99999", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_lookup_active_rates(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)
        await _create_tax_category(app_client, auth_headers)
        await _create_rate(app_client, auth_headers)

        resp = await app_client.get(
            "/v1/rates/lookup",
            headers=auth_headers,
            params={
                "jurisdiction_code": "US-NY-NYC",
                "effective_date": "2025-06-15",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "jurisdiction" in data
        assert data["jurisdiction"]["code"] == "US-NY-NYC"
        assert "rates" in data
        assert isinstance(data["rates"], list)
        assert len(data["rates"]) >= 1
        assert "combined_percentage_rate" in data
        assert data["combined_percentage_rate"] == pytest.approx(8.875)

    @pytest.mark.asyncio
    async def test_lookup_rates_not_found(self, app_client, auth_headers):
        resp = await app_client.get(
            "/v1/rates/lookup",
            headers=auth_headers,
            params={"jurisdiction_code": "XX-NOPE"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_approve_rate(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)
        await _create_tax_category(app_client, auth_headers)

        # Create a rate in draft status
        resp = await app_client.post(
            "/v1/rates",
            headers=auth_headers,
            json={
                "jurisdiction_code": "US-NY-NYC",
                "tax_category_code": "HOTEL_OCCUPANCY",
                "rate_type": "percentage",
                "rate_value": 5.0,
                "effective_start": "2025-01-01",
                "status": "draft",
                "created_by": "test",
            },
        )
        assert resp.status_code == 201
        rate_id = resp.json()["id"]

        # Approve
        resp = await app_client.post(
            f"/v1/rates/{rate_id}/approve",
            headers=auth_headers,
            params={"reviewed_by": "admin", "review_notes": "Looks good"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        assert data["reviewed_by"] == "admin"
        assert data["review_notes"] == "Looks good"

    @pytest.mark.asyncio
    async def test_reject_rate(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)
        await _create_tax_category(app_client, auth_headers)

        resp = await app_client.post(
            "/v1/rates",
            headers=auth_headers,
            json={
                "jurisdiction_code": "US-NY-NYC",
                "tax_category_code": "HOTEL_OCCUPANCY",
                "rate_type": "percentage",
                "rate_value": 99.0,
                "effective_start": "2025-01-01",
                "status": "draft",
                "created_by": "test",
            },
        )
        assert resp.status_code == 201
        rate_id = resp.json()["id"]

        resp = await app_client.post(
            f"/v1/rates/{rate_id}/reject",
            headers=auth_headers,
            params={"reviewed_by": "admin", "review_notes": "Rate too high"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
        assert data["reviewed_by"] == "admin"

    @pytest.mark.asyncio
    async def test_approve_rate_not_found(self, app_client, auth_headers):
        resp = await app_client.post(
            "/v1/rates/99999/approve", headers=auth_headers
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_bulk_create_rates(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)
        await _create_tax_category(app_client, auth_headers)

        resp = await app_client.post(
            "/v1/rates/bulk",
            headers=auth_headers,
            json={
                "rates": [
                    {
                        "jurisdiction_code": "US-NY-NYC",
                        "tax_category_code": "HOTEL_OCCUPANCY",
                        "rate_type": "percentage",
                        "rate_value": 4.5,
                        "effective_start": "2025-01-01",
                        "status": "active",
                        "created_by": "test",
                    },
                    {
                        "jurisdiction_code": "US-NY",
                        "tax_category_code": "HOTEL_OCCUPANCY",
                        "rate_type": "percentage",
                        "rate_value": 4.0,
                        "effective_start": "2025-01-01",
                        "status": "active",
                        "created_by": "test",
                    },
                ]
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 2
        values = {r["rate_value"] for r in data}
        assert values == {4.5, 4.0}

    @pytest.mark.asyncio
    async def test_create_rate_missing_jurisdiction(self, app_client, auth_headers):
        resp = await app_client.post(
            "/v1/rates",
            headers=auth_headers,
            json={
                "jurisdiction_code": "NOPE",
                "tax_category_code": "HOTEL_OCCUPANCY",
                "rate_type": "percentage",
                "rate_value": 5.0,
                "effective_start": "2025-01-01",
            },
        )
        assert resp.status_code == 400


class TestTaxRulesCRUD:
    """Tax rule CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_rule(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)

        resp = await app_client.post(
            "/v1/rules",
            headers=auth_headers,
            json={
                "jurisdiction_code": "US-NY-NYC",
                "rule_type": "exemption",
                "name": "Long-stay exemption",
                "description": "Stays over 180 nights are exempt",
                "priority": 10,
                "conditions": {"min_nights": 180},
                "action": {"exempt": True},
                "effective_start": "2025-01-01",
                "status": "active",
                "created_by": "test",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Long-stay exemption"
        assert data["rule_type"] == "exemption"
        assert data["priority"] == 10
        assert data["conditions"] == {"min_nights": 180}
        assert data["action"] == {"exempt": True}
        assert data["jurisdiction_code"] == "US-NY-NYC"
        assert data["status"] == "active"
        assert data["version"] == 1
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_rule_jurisdiction_not_found(self, app_client, auth_headers):
        resp = await app_client.post(
            "/v1/rules",
            headers=auth_headers,
            json={
                "jurisdiction_code": "NOPE",
                "rule_type": "exemption",
                "name": "Test",
                "effective_start": "2025-01-01",
            },
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_rules(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)

        # Create two rules
        for name in ["Rule A", "Rule B"]:
            await app_client.post(
                "/v1/rules",
                headers=auth_headers,
                json={
                    "jurisdiction_code": "US-NY-NYC",
                    "rule_type": "condition",
                    "name": name,
                    "effective_start": "2025-01-01",
                },
            )

        resp = await app_client.get("/v1/rules", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_list_rules_filter_by_jurisdiction(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)

        await app_client.post(
            "/v1/rules",
            headers=auth_headers,
            json={
                "jurisdiction_code": "US-NY-NYC",
                "rule_type": "exemption",
                "name": "NYC rule",
                "effective_start": "2025-01-01",
            },
        )
        await app_client.post(
            "/v1/rules",
            headers=auth_headers,
            json={
                "jurisdiction_code": "US-NY",
                "rule_type": "exemption",
                "name": "NY state rule",
                "effective_start": "2025-01-01",
            },
        )

        resp = await app_client.get(
            "/v1/rules",
            headers=auth_headers,
            params={"jurisdiction_code": "US-NY-NYC"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "NYC rule"

    @pytest.mark.asyncio
    async def test_list_rules_filter_by_type(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)

        await app_client.post(
            "/v1/rules",
            headers=auth_headers,
            json={
                "jurisdiction_code": "US-NY-NYC",
                "rule_type": "exemption",
                "name": "Exemption",
                "effective_start": "2025-01-01",
            },
        )
        await app_client.post(
            "/v1/rules",
            headers=auth_headers,
            json={
                "jurisdiction_code": "US-NY-NYC",
                "rule_type": "surcharge",
                "name": "Surcharge",
                "effective_start": "2025-01-01",
            },
        )

        resp = await app_client.get(
            "/v1/rules",
            headers=auth_headers,
            params={"rule_type": "exemption"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["rule_type"] == "exemption"

    @pytest.mark.asyncio
    async def test_get_rule_by_id(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)

        create_resp = await app_client.post(
            "/v1/rules",
            headers=auth_headers,
            json={
                "jurisdiction_code": "US-NY-NYC",
                "rule_type": "exemption",
                "name": "Test rule",
                "effective_start": "2025-01-01",
            },
        )
        rule_id = create_resp.json()["id"]

        resp = await app_client.get(f"/v1/rules/{rule_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == rule_id
        assert data["name"] == "Test rule"

    @pytest.mark.asyncio
    async def test_get_rule_not_found(self, app_client, auth_headers):
        resp = await app_client.get("/v1/rules/99999", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_rule_with_rate(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)
        await _create_tax_category(app_client, auth_headers)
        rate = await _create_rate(app_client, auth_headers)

        resp = await app_client.post(
            "/v1/rules",
            headers=auth_headers,
            json={
                "jurisdiction_code": "US-NY-NYC",
                "tax_rate_id": rate["id"],
                "rule_type": "reduction",
                "name": "Non-profit discount",
                "conditions": {"property_type": "nonprofit"},
                "action": {"reduce_by_percent": 50},
                "effective_start": "2025-01-01",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["tax_rate_id"] == rate["id"]
        assert data["rule_type"] == "reduction"


class TestTaxCalculation:
    """Tax calculation endpoint."""

    @pytest.mark.asyncio
    async def test_calculate_tax(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)
        await _create_tax_category(app_client, auth_headers)
        await _create_rate(app_client, auth_headers, rate_value=8.875)

        resp = await app_client.post(
            "/v1/tax/calculate",
            headers=auth_headers,
            json={
                "jurisdiction_code": "US-NY-NYC",
                "stay_date": "2025-06-15",
                "checkout_date": "2025-06-18",
                "nightly_rate": "200.00",
                "currency": "USD",
                "property_type": "hotel",
                "nights": 3,
                "number_of_guests": 2,
            },
        )
        assert resp.status_code == 200
        data = resp.json()

        # Verify response structure
        assert "calculation_id" in data
        assert "jurisdiction" in data
        assert "input" in data
        assert "tax_breakdown" in data
        assert "total_with_tax" in data
        assert "rules_applied" in data
        assert "calculated_at" in data

        breakdown = data["tax_breakdown"]
        assert "components" in breakdown
        assert "total_tax" in breakdown
        assert "effective_rate" in breakdown
        assert "currency" in breakdown
        assert isinstance(breakdown["components"], list)

        # The total_tax should be positive since we have an active rate
        total_tax = float(breakdown["total_tax"])
        assert total_tax > 0

        # total_with_tax should be greater than the nightly_rate * nights
        total_with_tax = float(data["total_with_tax"])
        assert total_with_tax > 200 * 3

    @pytest.mark.asyncio
    async def test_calculate_tax_unknown_jurisdiction(self, app_client, auth_headers):
        resp = await app_client.post(
            "/v1/tax/calculate",
            headers=auth_headers,
            json={
                "jurisdiction_code": "XX-NOPE",
                "stay_date": "2025-06-15",
                "nightly_rate": "100.00",
                "currency": "USD",
                "nights": 1,
            },
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_calculate_tax_response_components(self, app_client, auth_headers):
        """Verify individual tax component fields."""
        await _create_hierarchy(app_client, auth_headers)
        await _create_tax_category(app_client, auth_headers)
        await _create_rate(app_client, auth_headers)

        resp = await app_client.post(
            "/v1/tax/calculate",
            headers=auth_headers,
            json={
                "jurisdiction_code": "US-NY-NYC",
                "stay_date": "2025-06-15",
                "nightly_rate": "100.00",
                "currency": "USD",
                "nights": 1,
            },
        )
        assert resp.status_code == 200
        components = resp.json()["tax_breakdown"]["components"]
        assert len(components) >= 1
        comp = components[0]
        assert "name" in comp
        assert "category_code" in comp
        assert "jurisdiction_code" in comp
        assert "jurisdiction_level" in comp
        assert "rate" in comp
        assert "rate_type" in comp
        assert "tax_amount" in comp

    @pytest.mark.asyncio
    async def test_batch_calculate(self, app_client, auth_headers):
        await _create_hierarchy(app_client, auth_headers)
        await _create_tax_category(app_client, auth_headers)
        await _create_rate(app_client, auth_headers)

        resp = await app_client.post(
            "/v1/tax/calculate/batch",
            headers=auth_headers,
            json={
                "calculations": [
                    {
                        "jurisdiction_code": "US-NY-NYC",
                        "stay_date": "2025-06-15",
                        "nightly_rate": "200.00",
                        "currency": "USD",
                        "nights": 3,
                    },
                    {
                        "jurisdiction_code": "US-NY-NYC",
                        "stay_date": "2025-07-01",
                        "nightly_rate": "150.00",
                        "currency": "USD",
                        "nights": 2,
                    },
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) == 2


class TestMonitoringEndpoints:
    """Monitoring sources, schedules, jobs, and changes."""

    @pytest.mark.asyncio
    async def test_create_source(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers)

        resp = await app_client.post(
            "/v1/monitoring/sources",
            headers=auth_headers,
            json={
                "jurisdiction_code": "US",
                "url": "https://www.irs.gov",
                "source_type": "government_website",
                "language": "en",
                "check_frequency_days": 7,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["url"] == "https://www.irs.gov"
        assert data["source_type"] == "government_website"
        assert data["language"] == "en"
        assert data["check_frequency_days"] == 7
        assert data["status"] == "active"
        assert data["jurisdiction_code"] == "US"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_source_without_jurisdiction(self, app_client, auth_headers):
        resp = await app_client.post(
            "/v1/monitoring/sources",
            headers=auth_headers,
            json={
                "url": "https://taxnews.example.com",
                "source_type": "tax_authority",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["jurisdiction_code"] is None

    @pytest.mark.asyncio
    async def test_list_sources(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers)

        await app_client.post(
            "/v1/monitoring/sources",
            headers=auth_headers,
            json={
                "jurisdiction_code": "US",
                "url": "https://www.irs.gov",
                "source_type": "government_website",
            },
        )
        await app_client.post(
            "/v1/monitoring/sources",
            headers=auth_headers,
            json={
                "url": "https://tax.example.com",
                "source_type": "tax_authority",
            },
        )

        resp = await app_client.get("/v1/monitoring/sources", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_list_sources_filter_by_jurisdiction(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers)

        await app_client.post(
            "/v1/monitoring/sources",
            headers=auth_headers,
            json={
                "jurisdiction_code": "US",
                "url": "https://www.irs.gov",
                "source_type": "government_website",
            },
        )
        await app_client.post(
            "/v1/monitoring/sources",
            headers=auth_headers,
            json={
                "url": "https://tax.example.com",
                "source_type": "tax_authority",
            },
        )

        resp = await app_client.get(
            "/v1/monitoring/sources",
            headers=auth_headers,
            params={"jurisdiction_code": "US"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["jurisdiction_code"] == "US"

    @pytest.mark.asyncio
    async def test_get_source_by_id(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers)

        create_resp = await app_client.post(
            "/v1/monitoring/sources",
            headers=auth_headers,
            json={
                "jurisdiction_code": "US",
                "url": "https://www.irs.gov",
                "source_type": "government_website",
            },
        )
        source_id = create_resp.json()["id"]

        resp = await app_client.get(
            f"/v1/monitoring/sources/{source_id}", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == source_id

    @pytest.mark.asyncio
    async def test_create_schedule(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers)

        resp = await app_client.put(
            "/v1/monitoring/schedules/US",
            headers=auth_headers,
            json={
                "enabled": True,
                "cadence": "weekly",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True
        assert data["cadence"] == "weekly"
        assert data["jurisdiction_code"] == "US"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_schedule_custom_cron(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers)

        resp = await app_client.put(
            "/v1/monitoring/schedules/US",
            headers=auth_headers,
            json={
                "enabled": True,
                "cadence": "custom",
                "cron_expression": "0 8 * * 1",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["cadence"] == "custom"
        assert data["cron_expression"] == "0 8 * * 1"

    @pytest.mark.asyncio
    async def test_create_schedule_custom_without_cron_fails(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers)

        resp = await app_client.put(
            "/v1/monitoring/schedules/US",
            headers=auth_headers,
            json={
                "enabled": True,
                "cadence": "custom",
            },
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_create_schedule_not_found_jurisdiction(self, app_client, auth_headers):
        resp = await app_client.put(
            "/v1/monitoring/schedules/NOPE",
            headers=auth_headers,
            json={"enabled": True, "cadence": "daily"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_schedules(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers)

        await app_client.put(
            "/v1/monitoring/schedules/US",
            headers=auth_headers,
            json={"enabled": True, "cadence": "daily"},
        )

        resp = await app_client.get("/v1/monitoring/schedules", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_get_schedule(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers)

        await app_client.put(
            "/v1/monitoring/schedules/US",
            headers=auth_headers,
            json={"enabled": True, "cadence": "monthly"},
        )

        resp = await app_client.get(
            "/v1/monitoring/schedules/US", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["cadence"] == "monthly"
        assert data["jurisdiction_code"] == "US"

    @pytest.mark.asyncio
    async def test_get_schedule_not_found(self, app_client, auth_headers):
        resp = await app_client.get(
            "/v1/monitoring/schedules/NOPE", headers=auth_headers
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_jobs_empty(self, app_client, auth_headers):
        resp = await app_client.get("/v1/monitoring/jobs", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_list_changes_empty(self, app_client, auth_headers):
        resp = await app_client.get("/v1/monitoring/changes", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_create_change(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers)

        resp = await app_client.post(
            "/v1/monitoring/changes",
            headers=auth_headers,
            json={
                "jurisdiction_code": "US",
                "change_type": "rate_change",
                "extracted_data": {"old_rate": 5.0, "new_rate": 6.0},
                "confidence": 0.95,
                "source_quote": "Tax rate increased to 6%",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["change_type"] == "rate_change"
        assert data["confidence"] == 0.95
        assert data["jurisdiction_code"] == "US"
        assert data["review_status"] == "pending"
        assert data["extracted_data"] == {"old_rate": 5.0, "new_rate": 6.0}

    @pytest.mark.asyncio
    async def test_list_changes(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers)

        await app_client.post(
            "/v1/monitoring/changes",
            headers=auth_headers,
            json={
                "jurisdiction_code": "US",
                "change_type": "rate_change",
                "extracted_data": {"rate": 6.0},
                "confidence": 0.9,
            },
        )

        resp = await app_client.get("/v1/monitoring/changes", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_review_change(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers)

        create_resp = await app_client.post(
            "/v1/monitoring/changes",
            headers=auth_headers,
            json={
                "jurisdiction_code": "US",
                "change_type": "new_tax",
                "extracted_data": {"name": "New tourism tax"},
                "confidence": 0.85,
            },
        )
        change_id = create_resp.json()["id"]

        resp = await app_client.post(
            f"/v1/monitoring/changes/{change_id}/review",
            headers=auth_headers,
            json={
                "review_status": "approved",
                "reviewed_by": "analyst",
                "review_notes": "Verified against official gazette",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["review_status"] == "approved"
        assert data["reviewed_by"] == "analyst"
        assert data["review_notes"] == "Verified against official gazette"

    @pytest.mark.asyncio
    async def test_get_change_by_id(self, app_client, auth_headers):
        await _create_country(app_client, auth_headers)

        create_resp = await app_client.post(
            "/v1/monitoring/changes",
            headers=auth_headers,
            json={
                "jurisdiction_code": "US",
                "change_type": "exemption_change",
                "extracted_data": {},
                "confidence": 0.7,
            },
        )
        change_id = create_resp.json()["id"]

        resp = await app_client.get(
            f"/v1/monitoring/changes/{change_id}", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == change_id

    @pytest.mark.asyncio
    async def test_get_change_not_found(self, app_client, auth_headers):
        resp = await app_client.get(
            "/v1/monitoring/changes/99999", headers=auth_headers
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_schedule_upsert(self, app_client, auth_headers):
        """Calling PUT on the same jurisdiction twice should upsert."""
        await _create_country(app_client, auth_headers)

        # First call creates
        resp1 = await app_client.put(
            "/v1/monitoring/schedules/US",
            headers=auth_headers,
            json={"enabled": True, "cadence": "daily"},
        )
        assert resp1.status_code == 200
        schedule_id = resp1.json()["id"]

        # Second call updates
        resp2 = await app_client.put(
            "/v1/monitoring/schedules/US",
            headers=auth_headers,
            json={"enabled": False, "cadence": "weekly"},
        )
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["id"] == schedule_id  # same record
        assert data["enabled"] is False
        assert data["cadence"] == "weekly"


class TestAuditLog:
    """Audit log entries are created when entities are modified."""

    @pytest.mark.asyncio
    async def test_audit_entries_after_rate_creation(self, app_client, auth_headers):
        """Creating a tax rate should produce an audit log entry."""
        await _create_hierarchy(app_client, auth_headers)
        await _create_tax_category(app_client, auth_headers)
        rate = await _create_rate(app_client, auth_headers)

        resp = await app_client.get(
            "/v1/audit",
            headers=auth_headers,
            params={"entity_type": "tax_rate", "entity_id": rate["id"]},
        )
        assert resp.status_code == 200
        entries = resp.json()
        assert isinstance(entries, list)
        assert len(entries) >= 1

        entry = entries[0]
        assert entry["entity_type"] == "tax_rate"
        assert entry["entity_id"] == rate["id"]
        assert entry["action"] == "create"
        assert "new_values" in entry
        assert "created_at" in entry

    @pytest.mark.asyncio
    async def test_audit_entries_after_rate_approval(self, app_client, auth_headers):
        """Approving a rate should create a status_change audit entry."""
        await _create_hierarchy(app_client, auth_headers)
        await _create_tax_category(app_client, auth_headers)

        create_resp = await app_client.post(
            "/v1/rates",
            headers=auth_headers,
            json={
                "jurisdiction_code": "US-NY-NYC",
                "tax_category_code": "HOTEL_OCCUPANCY",
                "rate_type": "percentage",
                "rate_value": 10.0,
                "effective_start": "2025-01-01",
                "status": "draft",
                "created_by": "test",
            },
        )
        rate_id = create_resp.json()["id"]

        await app_client.post(
            f"/v1/rates/{rate_id}/approve",
            headers=auth_headers,
            params={"reviewed_by": "admin"},
        )

        resp = await app_client.get(
            "/v1/audit",
            headers=auth_headers,
            params={"entity_type": "tax_rate", "entity_id": rate_id},
        )
        assert resp.status_code == 200
        entries = resp.json()
        # Should have at least 2 entries: create + status_change
        assert len(entries) >= 2

        actions = {e["action"] for e in entries}
        assert "create" in actions
        assert "status_change" in actions

    @pytest.mark.asyncio
    async def test_audit_log_list(self, app_client, auth_headers):
        """List all audit entries without filters."""
        await _create_hierarchy(app_client, auth_headers)
        await _create_tax_category(app_client, auth_headers)
        await _create_rate(app_client, auth_headers)

        resp = await app_client.get("/v1/audit", headers=auth_headers)
        assert resp.status_code == 200
        entries = resp.json()
        assert isinstance(entries, list)
        assert len(entries) >= 1

    @pytest.mark.asyncio
    async def test_audit_log_empty_initially(self, app_client, auth_headers):
        """With no entities created, the audit log should be empty."""
        resp = await app_client.get("/v1/audit", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_audit_log_filter_by_entity_type(self, app_client, auth_headers):
        """Filtering by a non-existent entity type returns empty."""
        resp = await app_client.get(
            "/v1/audit",
            headers=auth_headers,
            params={"entity_type": "nonexistent"},
        )
        assert resp.status_code == 200
        assert resp.json() == []
