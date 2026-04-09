from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from core_app.api.dependencies import CurrentUser, get_current_user

router = APIRouter(prefix='/api/v1/system-health', tags=['system-health'])

@router.get('/dashboard')
async def dashboard(_current_user: CurrentUser = Depends(get_current_user)) -> dict:
    return {
        'active_alerts': 0,
        'p95_latency_ms': 0,
        'healthy': 0,
        'degraded': 0,
        'down': 0,
        'overall_status': 'not_connected',
        'as_of': datetime.now(UTC).isoformat(),
    }
