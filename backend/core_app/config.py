from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("ADAPTIX_AI_APP_NAME", "adaptix-ai")
    app_env: str = os.getenv("ADAPTIX_AI_ENV", "development")
    dev_secret: str = os.getenv("ADAPTIX_AI_DEV_SECRET", "adaptix-ai-dev-secret")
    allow_dev_auth: bool = os.getenv("ADAPTIX_AI_ALLOW_DEV_AUTH", "true").lower() == "true"
    default_tenant_id: str = os.getenv("ADAPTIX_AI_DEFAULT_TENANT_ID", "00000000-0000-0000-0000-000000000001")
    cors_origins: str = os.getenv("ADAPTIX_AI_CORS_ORIGINS", "*")


settings = Settings()

def get_settings() -> Settings:
    return settings
