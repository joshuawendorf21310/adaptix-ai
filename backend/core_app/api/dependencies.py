from __future__ import annotations

from fastapi import Header, HTTPException, status
from pydantic import BaseModel, Field

from core_app.core.security import decode_access_token


class CurrentUser(BaseModel):
    user_id: str
    tenant_id: str
    role: str = "viewer"
    roles: list[str] = Field(default_factory=list)
    resolved_primary_role: str = "viewer"


async def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    payload = decode_access_token(authorization.split(" ", 1)[1])
    role = payload.get("role", "viewer")
    return CurrentUser(user_id=payload["sub"], tenant_id=payload["tenant_id"], role=role, roles=[role], resolved_primary_role=role)
