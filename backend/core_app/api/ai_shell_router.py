from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from core_app.api.dependencies import CurrentUser, get_current_user

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

PROMPT_AUDIT = {
    "total_prompts": 0,
    "active_prompts": 0,
    "guardrails_enabled": False,
    "pii_masking_enabled": False,
    "rate_limit_per_minute": 0,
    "total_calls_today": 0,
    "avg_latency_ms": 0,
    "prompts": [],
    "mode": "standalone-shell",
}

@router.get('/prompts/audit')
async def prompt_audit(_current_user: CurrentUser = Depends(get_current_user)) -> dict:
    return PROMPT_AUDIT | {"as_of": datetime.now(UTC).isoformat()}

@router.get('/prompt-log')
async def prompt_log(limit: int = 20, _current_user: CurrentUser = Depends(get_current_user)) -> list[dict]:
    return []
