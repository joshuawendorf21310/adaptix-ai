from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Production-ready configuration for Adaptix AI service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="adaptix-ai", alias="ADAPTIX_AI_APP_NAME")
    app_env: Literal["development", "staging", "production"] = Field(
        default="development",
        alias="ADAPTIX_AI_ENV"
    )
    app_version: str = Field(default="0.1.0", alias="ADAPTIX_AI_VERSION")
    debug: bool = Field(default=False, alias="ADAPTIX_AI_DEBUG")

    # CORS
    cors_origins: str = Field(default="*", alias="ADAPTIX_AI_CORS_ORIGINS")

    # Security & Authentication
    dev_secret: SecretStr = Field(
        default=SecretStr("adaptix-ai-dev-secret"),
        alias="ADAPTIX_AI_DEV_SECRET"
    )
    allow_dev_auth: bool = Field(default=True, alias="ADAPTIX_AI_ALLOW_DEV_AUTH")
    jwt_secret_key: SecretStr | None = Field(default=None, alias="ADAPTIX_AI_JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="ADAPTIX_AI_JWT_ALGORITHM")
    jwt_expiry_minutes: int = Field(default=60, alias="ADAPTIX_AI_JWT_EXPIRY_MINUTES")

    # Production auth (for future OAuth/OIDC integration)
    auth_provider_url: str | None = Field(default=None, alias="ADAPTIX_AI_AUTH_PROVIDER_URL")
    auth_client_id: str | None = Field(default=None, alias="ADAPTIX_AI_AUTH_CLIENT_ID")
    auth_client_secret: SecretStr | None = Field(default=None, alias="ADAPTIX_AI_AUTH_CLIENT_SECRET")

    # Multi-tenancy
    default_tenant_id: str = Field(
        default="00000000-0000-0000-0000-000000000001",
        alias="ADAPTIX_AI_DEFAULT_TENANT_ID"
    )

    # Database
    database_url: PostgresDsn | None = Field(
        default=None,
        alias="ADAPTIX_AI_DATABASE_URL"
    )
    database_echo: bool = Field(default=False, alias="ADAPTIX_AI_DATABASE_ECHO")
    database_pool_size: int = Field(default=20, alias="ADAPTIX_AI_DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=10, alias="ADAPTIX_AI_DATABASE_MAX_OVERFLOW")

    # AWS Configuration
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    aws_access_key_id: SecretStr | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: SecretStr | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")

    # AWS Bedrock
    bedrock_model_id: str = Field(
        default="claude-3-5-sonnet-20241022-v2:0",
        alias="ADAPTIX_AI_BEDROCK_MODEL_ID"
    )
    bedrock_max_tokens: int = Field(default=4096, alias="ADAPTIX_AI_BEDROCK_MAX_TOKENS")
    bedrock_temperature: float = Field(default=0.3, alias="ADAPTIX_AI_BEDROCK_TEMPERATURE")
    bedrock_timeout: int = Field(default=60, alias="ADAPTIX_AI_BEDROCK_TIMEOUT")
    bedrock_max_retries: int = Field(default=3, alias="ADAPTIX_AI_BEDROCK_MAX_RETRIES")

    # AWS EventBridge
    eventbridge_enabled: bool = Field(default=False, alias="ADAPTIX_AI_EVENTBRIDGE_ENABLED")
    eventbridge_bus_name: str = Field(
        default="adaptix-ai-events",
        alias="ADAPTIX_AI_EVENTBRIDGE_BUS_NAME"
    )

    # Rate Limiting & Budget
    rate_limit_per_minute: int = Field(default=100, alias="ADAPTIX_AI_RATE_LIMIT_PER_MINUTE")
    daily_token_budget: int = Field(default=1_000_000, alias="ADAPTIX_AI_DAILY_TOKEN_BUDGET")
    monthly_token_budget: int = Field(default=30_000_000, alias="ADAPTIX_AI_MONTHLY_TOKEN_BUDGET")

    # Guardrails & Policy
    guardrails_enabled: bool = Field(default=True, alias="ADAPTIX_AI_GUARDRAILS_ENABLED")
    pii_masking_enabled: bool = Field(default=True, alias="ADAPTIX_AI_PII_MASKING_ENABLED")
    require_manual_review: bool = Field(default=False, alias="ADAPTIX_AI_REQUIRE_MANUAL_REVIEW")

    # Audit & Retention
    audit_enabled: bool = Field(default=True, alias="ADAPTIX_AI_AUDIT_ENABLED")
    audit_retention_days: int = Field(default=90, alias="ADAPTIX_AI_AUDIT_RETENTION_DAYS")

    # Redis (for caching and rate limiting)
    redis_url: str | None = Field(default=None, alias="ADAPTIX_AI_REDIS_URL")
    redis_enabled: bool = Field(default=False, alias="ADAPTIX_AI_REDIS_ENABLED")

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        alias="ADAPTIX_AI_LOG_LEVEL"
    )

    # Feature Flags
    async_execution_enabled: bool = Field(default=False, alias="ADAPTIX_AI_ASYNC_EXECUTION")

    @field_validator("allow_dev_auth", mode="after")
    @classmethod
    def validate_dev_auth_production(cls, v: bool, info) -> bool:
        """Ensure dev auth is disabled in production."""
        app_env = info.data.get("app_env", "development")
        if app_env == "production" and v:
            raise ValueError(
                "Dev auth cannot be enabled in production environment. "
                "Set ADAPTIX_AI_ALLOW_DEV_AUTH=false for production."
            )
        return v

    @field_validator("database_url", mode="after")
    @classmethod
    def validate_database_production(cls, v: PostgresDsn | None, info) -> PostgresDsn | None:
        """Ensure database is configured in production."""
        app_env = info.data.get("app_env", "development")
        if app_env == "production" and not v:
            raise ValueError(
                "Database URL must be configured in production environment. "
                "Set ADAPTIX_AI_DATABASE_URL."
            )
        return v

    @field_validator("jwt_secret_key", mode="after")
    @classmethod
    def validate_jwt_secret_production(cls, v: SecretStr | None, info) -> SecretStr | None:
        """Ensure JWT secret is configured in production."""
        app_env = info.data.get("app_env", "development")
        if app_env == "production" and not v:
            raise ValueError(
                "JWT secret key must be configured in production environment. "
                "Set ADAPTIX_AI_JWT_SECRET to a strong random value."
            )
        return v

    def get_cors_origins_list(self) -> list[str]:
        """Parse CORS origins string into list."""
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return origins or ["*"]

    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_env == "production"

    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
