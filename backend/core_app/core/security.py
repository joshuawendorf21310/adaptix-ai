from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from core_app.config import settings


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_access_token(*, user_id: str, tenant_id: str, role: str, expires_in: int = 3600) -> str:
    payload = {"sub": user_id, "tenant_id": tenant_id, "role": role, "iat": int(time.time()), "exp": int(time.time()) + expires_in}
    encoded = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(settings.dev_secret.encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).digest()
    return f"{encoded}.{_b64url_encode(signature)}"


def decode_access_token(token: str) -> dict[str, Any]:
    encoded_payload, encoded_sig = token.split(".", 1)
    expected_sig = hmac.new(settings.dev_secret.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).digest()
    actual_sig = _b64url_decode(encoded_sig)
    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("Invalid token signature")
    payload = json.loads(_b64url_decode(encoded_payload).decode("utf-8"))
    if payload.get("exp", 0) < int(time.time()):
        raise ValueError("Token expired")
    return payload
