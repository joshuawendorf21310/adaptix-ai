from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from core_app.config import settings

router = APIRouter(tags=["health"])

@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "timestamp": datetime.now(UTC).isoformat(), "version": "0.1.0", "service": settings.app_name, "environment": settings.app_env}
