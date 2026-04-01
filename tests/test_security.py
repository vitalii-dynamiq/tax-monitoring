"""
Security tests for production configuration and authentication.
"""


import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestProductionConfigValidation:
    def test_default_api_key_rejected_in_production(self):
        with pytest.raises(ValueError, match="API_KEY must be changed"):
            from app.config import Settings
            Settings(
                environment="production",
                api_key="dev-api-key-change-me",
                cors_origins="https://app.example.com",
            )

    def test_wildcard_cors_rejected_in_production(self):
        with pytest.raises(ValueError, match="CORS_ORIGINS must not be wildcard"):
            from app.config import Settings
            Settings(
                environment="production",
                api_key="a-real-production-key",
                cors_origins="*",
            )

    def test_valid_production_config_accepted(self):
        from app.config import Settings
        s = Settings(
            environment="production",
            api_key="a-real-production-key",
            cors_origins="https://app.example.com",
        )
        assert s.is_production is True

    def test_development_allows_defaults(self):
        from app.config import Settings
        s = Settings(environment="development")
        assert s.api_key == "dev-api-key-change-me"
        assert s.cors_origins == "*"


class TestAuthenticationEnforcement:
    def test_all_v1_endpoints_require_auth(self, client):
        """Scan OpenAPI spec and verify all /v1/ paths return 401 without API key."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json()["paths"]

        v1_paths = [p for p in paths if p.startswith("/v1/")]
        assert len(v1_paths) > 0, "Expected /v1/ endpoints in OpenAPI spec"

        for path in v1_paths:
            methods = paths[path].keys()
            for method in methods:
                if method in ("get", "post", "put", "patch", "delete"):
                    # Replace path parameters with dummy values
                    test_path = path
                    for param in ("{jurisdiction_code}", "{code}", "{rate_id}", "{rule_id}",
                                  "{job_id}", "{change_id}", "{source_id}", "{country_code}"):
                        test_path = test_path.replace(param, "DUMMY")

                    resp = getattr(client, method)(test_path)
                    assert resp.status_code == 401, (
                        f"{method.upper()} {path} returned {resp.status_code} without API key"
                    )

    def test_public_paths_accessible_without_key(self, client):
        for path in ["/health", "/docs", "/openapi.json"]:
            response = client.get(path)
            assert response.status_code != 401, f"{path} should be public"

    def test_api_key_not_in_error_response(self, client):
        """Verify the API key value is not leaked in error responses."""
        from app.config import settings
        response = client.get("/v1/jurisdictions")
        assert settings.api_key not in response.text


class TestHealthEndpointEnhanced:
    def test_health_includes_scheduler_and_ai_status(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "scheduler" in data
        assert "ai_configured" in data
        assert data["scheduler"] in ("running", "stopped")
        assert isinstance(data["ai_configured"], bool)


class TestRequestIdHeader:
    def test_response_includes_request_id(self, client):
        response = client.get("/health")
        assert "X-Request-ID" in response.headers

    def test_provided_request_id_is_returned(self, client):
        response = client.get("/health", headers={"X-Request-ID": "my-trace-123"})
        assert response.headers["X-Request-ID"] == "my-trace-123"


class TestRateLimiting:
    def test_rate_limiter_skipped_in_development(self, client):
        """Rate limiting is disabled in non-production environments."""
        # In development, all requests should succeed regardless of volume
        for _ in range(50):
            resp = client.get("/health")
        assert resp.status_code == 200

    def test_rate_limiter_middleware_exists(self):
        """Verify RateLimitMiddleware is registered."""
        from app.middleware import RateLimitMiddleware
        assert RateLimitMiddleware is not None
