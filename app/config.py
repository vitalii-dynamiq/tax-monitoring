from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://taxlens:taxlens@localhost:5432/taxlens"
    database_url_sync: str = "postgresql://taxlens:taxlens@localhost:5432/taxlens"

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_async_url(cls, v: str) -> str:
        """Accept Railway's postgres:// or postgresql:// and convert to asyncpg driver."""
        v = v.replace("postgres://", "postgresql://", 1)
        if "+asyncpg" not in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v
    api_key: str = Field(default="dev-api-key-change-me")
    jwt_secret: str = "taxlens-jwt-secret-change-in-production"
    debug: bool = False
    cors_origins: str = "*"
    environment: str = "development"
    registration_enabled: bool = False

    # Anthropic API
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_max_tokens: int = 16384
    anthropic_timeout_seconds: int = 300
    anthropic_max_search_uses: int = 10
    anthropic_max_agent_turns: int = 20

    # Geocoding (optional — falls back to free Nominatim if not set)
    opencage_api_key: str = ""

    # Monitoring
    monitoring_max_concurrent_jobs: int = 5
    monitoring_job_timeout_seconds: int = 900
    monitoring_scheduler_interval_seconds: int = 60

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def _derive_sync_url(self):
        """Derive database_url_sync from database_url when not explicitly configured.

        Handles Railway deployments where only DATABASE_URL is injected.
        """
        default_sync = "postgresql://taxlens:taxlens@localhost:5432/taxlens"
        if self.database_url_sync == default_sync:
            self.database_url_sync = self.database_url.replace(
                "postgresql+asyncpg://", "postgresql://", 1
            )
        return self

    @model_validator(mode="after")
    def _validate_production(self):
        if self.is_production:
            if self.api_key == "dev-api-key-change-me":
                raise ValueError(
                    "API_KEY must be changed from the default value in production"
                )
            if self.jwt_secret == "taxlens-jwt-secret-change-in-production":
                raise ValueError(
                    "JWT_SECRET must be changed from the default value in production"
                )
            if self.cors_origins.strip() == "*":
                raise ValueError(
                    "CORS_ORIGINS must not be wildcard (*) in production"
                )
        return self


settings = Settings()
