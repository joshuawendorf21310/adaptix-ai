from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import boto3

from core_app.core.config import get_settings


def _events_client():
    settings = get_settings()
    return boto3.client("events", region_name=settings.aws_region or "us-east-1")


async def publish_ai_task_completed(*, result: Any) -> None:
    settings = get_settings()
    if not settings.eventbridge_enabled:
        return

    payload = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
    _events_client().put_events(
        Entries=[
            {
                "Source": "adaptix.ai",
                "DetailType": "adaptix.ai.task.completed",
                "EventBusName": settings.eventbridge_bus_name,
                "Time": datetime.now(UTC),
                "Detail": json.dumps(payload),
            }
        ]
    )


async def publish_ai_task_failed(*, req: Any, error_code: str, error_message: str) -> None:
    settings = get_settings()
    if not settings.eventbridge_enabled:
        return

    detail = {
        "event_type": "adaptix.ai.task.failed",
        "tenant_id": getattr(req, "tenant_id", "unknown"),
        "actor_id": getattr(req, "actor_id", "unknown"),
        "module": getattr(req, "module", "unknown"),
        "task_type": getattr(req, "task_type", "unknown"),
        "correlation_id": getattr(req, "correlation_id", "unknown"),
        "timestamp": datetime.now(UTC).isoformat(),
        "error_code": error_code,
        "error_message": error_message,
    }

    _events_client().put_events(
        Entries=[
            {
                "Source": "adaptix.ai",
                "DetailType": "adaptix.ai.task.failed",
                "EventBusName": settings.eventbridge_bus_name,
                "Time": datetime.now(UTC),
                "Detail": json.dumps(detail),
            }
        ]
    )
