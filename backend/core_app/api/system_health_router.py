"""Real system health dashboard (replaces shell implementation)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core_app.api.dependencies import CurrentUser, get_current_user
from core_app.database import get_db
from core_app.services import SystemHealthService

router = APIRouter(prefix='/api/v1/system-health', tags=['system-health'])


@router.get('/dashboard')
async def dashboard(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get truthful system health dashboard.

    Returns real component health status, performance metrics, and incident counts.
    """
    health_service = SystemHealthService(db)

    # Get current health status (uses cached snapshot if recent, otherwise creates new)
    health_data = health_service.get_current_health_dashboard()

    return health_data
