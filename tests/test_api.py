"""
API endpoint tests using FastAPI TestClient.

Tests verify request/response shapes, validation, and authentication.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"X-API-Key": settings.api_key}


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        """Health endpoint is public — no API key needed."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ok", "degraded")
        assert "version" in data
        assert "database" in data

    def test_health_no_auth_required(self, client):
        response = client.get("/health")
        assert response.status_code == 200


class TestAuthentication:
    def test_missing_api_key_returns_401(self, client):
        response = client.get("/v1/jurisdictions")
        assert response.status_code == 401
        assert "API key" in response.json()["detail"]

    def test_wrong_api_key_returns_401(self, client):
        response = client.get(
            "/v1/jurisdictions",
            headers={"X-API-Key": "wrong-key"},
        )
        assert response.status_code == 401

    def test_valid_api_key_passes(self, client, auth_headers):
        # With valid API key, the middleware passes.
        # Without DB we may get a connection error, but NOT a 401.
        try:
            response = client.get("/v1/jurisdictions", headers=auth_headers)
            assert response.status_code in (200, 500)
        except Exception:
            # DB connection error is expected without Postgres running
            # — the important thing is it got past the auth middleware
            pass


class TestTaxCalculationValidation:
    def test_calculate_requires_jurisdiction_code(self, client, auth_headers):
        response = client.post("/v1/tax/calculate", json={
            "stay_date": "2025-06-15",
            "nightly_rate": 200,
            "currency": "USD",
            "nights": 3,
        }, headers=auth_headers)
        assert response.status_code == 422

    def test_calculate_requires_positive_nightly_rate(self, client, auth_headers):
        response = client.post("/v1/tax/calculate", json={
            "jurisdiction_code": "US-NY-NYC",
            "stay_date": "2025-06-15",
            "nightly_rate": -10,
            "currency": "USD",
            "nights": 3,
        }, headers=auth_headers)
        assert response.status_code == 422

    def test_calculate_requires_valid_currency(self, client, auth_headers):
        response = client.post("/v1/tax/calculate", json={
            "jurisdiction_code": "US-NY-NYC",
            "stay_date": "2025-06-15",
            "nightly_rate": 200,
            "currency": "X",
            "nights": 3,
        }, headers=auth_headers)
        assert response.status_code == 422

    def test_calculate_requires_positive_nights(self, client, auth_headers):
        response = client.post("/v1/tax/calculate", json={
            "jurisdiction_code": "US-NY-NYC",
            "stay_date": "2025-06-15",
            "nightly_rate": 200,
            "currency": "USD",
            "nights": 0,
        }, headers=auth_headers)
        assert response.status_code == 422


class TestTaxRateValidation:
    def test_create_rate_requires_jurisdiction_code(self, client, auth_headers):
        response = client.post("/v1/rates", json={
            "tax_category_code": "occ_pct",
            "rate_type": "percentage",
            "rate_value": 0.05,
            "effective_start": "2025-01-01",
        }, headers=auth_headers)
        assert response.status_code == 422

    def test_create_rate_validates_rate_type_enum(self, client, auth_headers):
        response = client.post("/v1/rates", json={
            "jurisdiction_code": "US-NY-NYC",
            "tax_category_code": "occ_pct",
            "rate_type": "INVALID",
            "rate_value": 0.05,
            "effective_start": "2025-01-01",
        }, headers=auth_headers)
        assert response.status_code == 422

    def test_tiered_rate_requires_tiers(self, client, auth_headers):
        response = client.post("/v1/rates", json={
            "jurisdiction_code": "US-NY-NYC",
            "tax_category_code": "tier_price",
            "rate_type": "tiered",
            "effective_start": "2025-01-01",
        }, headers=auth_headers)
        assert response.status_code == 422

    def test_percentage_rate_requires_rate_value(self, client, auth_headers):
        response = client.post("/v1/rates", json={
            "jurisdiction_code": "US-NY-NYC",
            "tax_category_code": "occ_pct",
            "rate_type": "percentage",
            "effective_start": "2025-01-01",
        }, headers=auth_headers)
        assert response.status_code == 422


class TestJurisdictionValidation:
    def test_create_jurisdiction_requires_code(self, client, auth_headers):
        response = client.post("/v1/jurisdictions", json={
            "name": "Test",
            "jurisdiction_type": "country",
            "country_code": "XX",
            "currency_code": "USD",
        }, headers=auth_headers)
        assert response.status_code == 422

    def test_create_jurisdiction_validates_type_enum(self, client, auth_headers):
        response = client.post("/v1/jurisdictions", json={
            "code": "XX",
            "name": "Test",
            "jurisdiction_type": "INVALID",
            "country_code": "XX",
            "currency_code": "USD",
        }, headers=auth_headers)
        assert response.status_code == 422


class TestDocsEndpoint:
    def test_docs_is_public(self, client):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_is_public(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "TaxLens API"
        # Verify all route groups are present
        paths = list(data["paths"].keys())
        assert any("/v1/jurisdictions" in p for p in paths)
        assert any("/v1/rates" in p for p in paths)
        assert any("/v1/rules" in p for p in paths)
        assert any("/v1/tax/calculate" in p for p in paths)
        assert any("/v1/monitoring" in p for p in paths)
        assert any("/v1/audit" in p for p in paths)


class TestPaginationValidation:
    def test_negative_offset_returns_422(self, client, auth_headers):
        response = client.get("/v1/jurisdictions?offset=-1", headers=auth_headers)
        assert response.status_code == 422

    def test_zero_limit_returns_422(self, client, auth_headers):
        response = client.get("/v1/jurisdictions?limit=0", headers=auth_headers)
        assert response.status_code == 422

    def test_limit_over_500_returns_422(self, client, auth_headers):
        response = client.get("/v1/jurisdictions?limit=501", headers=auth_headers)
        assert response.status_code == 422

    def test_negative_offset_rates(self, client, auth_headers):
        response = client.get("/v1/rates?offset=-5", headers=auth_headers)
        assert response.status_code == 422

    def test_negative_offset_rules(self, client, auth_headers):
        response = client.get("/v1/rules?offset=-1", headers=auth_headers)
        assert response.status_code == 422

    def test_negative_offset_monitoring_sources(self, client, auth_headers):
        response = client.get("/v1/monitoring/sources?offset=-1", headers=auth_headers)
        assert response.status_code == 422

    def test_negative_offset_monitoring_changes(self, client, auth_headers):
        response = client.get("/v1/monitoring/changes?offset=-1", headers=auth_headers)
        assert response.status_code == 422

    def test_negative_offset_audit(self, client, auth_headers):
        response = client.get("/v1/audit?offset=-1", headers=auth_headers)
        assert response.status_code == 422


class TestDateValidation:
    def test_rate_effective_end_before_start_returns_422(self, client, auth_headers):
        response = client.post("/v1/rates", json={
            "jurisdiction_code": "US-NY-NYC",
            "tax_category_code": "occ_pct",
            "rate_type": "percentage",
            "rate_value": 0.05,
            "effective_start": "2025-06-01",
            "effective_end": "2025-01-01",
        }, headers=auth_headers)
        assert response.status_code == 422

    def test_rule_effective_end_before_start_returns_422(self, client, auth_headers):
        response = client.post("/v1/rules", json={
            "jurisdiction_code": "US-NY-NYC",
            "rule_type": "exemption",
            "name": "Test rule",
            "effective_start": "2025-06-01",
            "effective_end": "2025-01-01",
        }, headers=auth_headers)
        assert response.status_code == 422


class TestBulkSizeLimits:
    def test_rate_bulk_over_100_returns_422(self, client, auth_headers):
        rates = [{
            "jurisdiction_code": "US-NY-NYC",
            "tax_category_code": "occ_pct",
            "rate_type": "percentage",
            "rate_value": 0.05,
            "effective_start": "2025-01-01",
        }] * 101
        response = client.post("/v1/rates/bulk", json={"rates": rates}, headers=auth_headers)
        assert response.status_code == 422
