from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from core_app.config import settings
from core_app.core.security import create_access_token

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

class DevLoginRequest(BaseModel):
    user_id: str = Field(default="00000000-0000-0000-0000-000000000401")
    tenant_id: str = Field(default=settings.default_tenant_id)
    role: str = Field(default="founder")

@router.post("/dev-login")
async def dev_login(payload: DevLoginRequest) -> dict[str, str]:
    if not settings.allow_dev_auth:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Developer login is disabled")
    token = create_access_token(user_id=payload.user_id, tenant_id=payload.tenant_id, role=payload.role)
    return {"access_token": token, "token_type": "bearer", "role": payload.role, "tenant_id": payload.tenant_id, "user_id": payload.user_id}
