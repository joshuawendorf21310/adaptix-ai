from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def log_ai_run(*, req: Any, result: Any) -> None:
    """Structured operational audit log for every AI orchestration run."""
    logger.info(
        "adaptix_ai_run module=%s task=%s tenant=%s actor=%s correlation_id=%s model=%s latency_ms=%s",
        getattr(req, "module", "unknown"),
        getattr(req, "task_type", "unknown"),
        getattr(req, "tenant_id", "unknown"),
        getattr(req, "actor_id", "unknown"),
        getattr(req, "correlation_id", "unknown"),
        getattr(result, "model_id", "unknown"),
        getattr(result, "latency_ms", "unknown"),
    )
