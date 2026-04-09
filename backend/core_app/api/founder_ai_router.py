from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from core_app.api.dependencies import CurrentUser, get_current_user

router = APIRouter(tags=['founder-ai'])

@router.get('/api/founder/system')
async def founder_system(_current_user: CurrentUser = Depends(get_current_user)) -> dict:
    return {
        'ai_healthy': False,
        'bedrock_latency_p95': 0,
        'daily_token_budget': 0,
        'tokens_used_today': 0,
        'error_rate': 0.0,
        'as_of': datetime.now(UTC).isoformat(),
        'mode': 'standalone-shell',
    }
