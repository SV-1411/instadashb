"""Application settings, loaded once from the environment (never hardcoded).

All configuration flows through :class:`Settings`. Secrets are read from env vars
and are intentionally excluded from ``repr``/logging so they cannot leak.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application configuration sourced from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App
    app_env: str = "local"
    app_name: str = "CivicPulse"
    log_level: str = "INFO"
    timezone: str = "Asia/Kolkata"

    # Database
    database_url: str = "postgresql+psycopg://civicpulse:civicpulse@localhost:5433/civicpulse"
    alembic_database_url: str | None = None

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Encryption (Fernet key) — SecretStr so it never prints in logs/repr.
    fernet_key: SecretStr = Field(default=SecretStr(""))

    # Cadence
    ingestion_interval_minutes: int = 30
    dummy_task_interval_seconds: int = 30

    # When true, all external clients use their Fake implementation (offline demo mode).
    # Flip to false once real Meta/FCM/etc. credentials are configured.
    use_fake_clients: bool = True

    # Read-path cache TTL (seconds) for dashboard aggregates in Redis.
    dashboard_cache_ttl_seconds: int = 60

    # Spike rule knobs (constitution: current > 7day_hourly_avg_negative * 2.5).
    spike_multiplier: float = 2.5
    spike_min_absolute: int = 5  # floor so tiny accounts don't false-trip

    # External services (filled in later WPs; SecretStr where sensitive).
    meta_app_id: str = ""
    meta_app_secret: SecretStr = Field(default=SecretStr(""))
    meta_oauth_redirect_uri: str = "http://localhost:8000/api/auth/meta/callback"
    meta_graph_api_version: str = "v19.0"
    # Which Meta data path to use: "facebook" (Page + Graph API) or
    # "instagram_login" (graph.instagram.com, no Facebook Page required).
    meta_source: str = "facebook"
    # Comma-separated OAuth scopes (verify against the current Meta App dashboard).
    meta_scopes: str = (
        "instagram_basic,instagram_manage_insights,pages_show_list,"
        "pages_read_engagement,business_management"
    )

    # Scraper supplement (broad public chatter the official API can't see).
    scraper_provider: str = "fake"  # fake | apify | socialdata
    scraper_api_key: SecretStr = Field(default=SecretStr(""))
    scraper_queries: str = ""  # comma-separated handles/hashtags/phrases

    fcm_service_account_json: str = "./firebase-service-account.json"
    google_nl_api_key: SecretStr = Field(default=SecretStr(""))
    nlp_sample_rate: float = 0.5
    socialdata_api_key: SecretStr = Field(default=SecretStr(""))
    manychat_webhook_secret: SecretStr = Field(default=SecretStr(""))
    openai_api_key: SecretStr = Field(default=SecretStr(""))
    ai_brief_model: str = "gpt-4o-mini"

    # OpenRouter (OpenAI-compatible) — used for topic extraction + AI Brief.
    # Pick any current free model from https://openrouter.ai/models (they have a :free suffix).
    openrouter_api_key: SecretStr = Field(default=SecretStr(""))
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"

    # X (Twitter) via SocialData.tools
    x_queries: str = ""  # comma-separated handles/keywords to pull from X

    @property
    def sync_alembic_url(self) -> str:
        """URL Alembic uses; defaults to the main DATABASE_URL."""
        return self.alembic_database_url or self.database_url


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached Settings instance."""
    return Settings()
