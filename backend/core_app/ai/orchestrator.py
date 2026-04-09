from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from core_app.ai.audit import log_ai_run
from core_app.ai.context.assembler import ContextAssembler
from core_app.ai.events import publish_ai_task_completed, publish_ai_task_failed
from core_app.ai.guardrails import validate_ai_output
from core_app.ai.prompt_registry import build_prompt
from core_app.ai.response_contracts import AiTaskResponse, normalize_result
from core_app.ai.service import AiService
from core_app.core.config import get_settings


@dataclass
class AiTaskRequest:
    tenant_id: str
    actor_id: str
    actor_role: str
    module: str
    task_type: str
    priority: str
    correlation_id: str
    context: dict[str, Any]
    max_tokens: int | None = None
    temperature: float | None = None
    require_structured_output: bool = True


class AiOrchestrator:
    def __init__(self, ai_service: AiService | None = None) -> None:
        self.settings = get_settings()
        self.ai_service = ai_service or AiService()
        self.context_assembler = ContextAssembler()

    async def run(self, req: AiTaskRequest) -> AiTaskResponse:
        started_at = datetime.now(UTC)
        try:
            assembled_context = await self.context_assembler.build(
                module=req.module,
                task_type=req.task_type,
                context=req.context,
                actor_role=req.actor_role,
            )

            system_prompt, user_prompt, prompt_version = build_prompt(
                module=req.module,
                task_type=req.task_type,
                context=assembled_context,
            )

            raw = await self.ai_service.generate_text(
                prompt=user_prompt,
                system=system_prompt,
                max_tokens=req.max_tokens or self.settings.ai_default_max_tokens,
                temperature=(
                    self.settings.ai_default_temperature
                    if req.temperature is None
                    else req.temperature
                ),
            )

            validated = validate_ai_output(
                task_type=req.task_type,
                raw_text=str(raw.get("text") or ""),
                require_structured_output=req.require_structured_output,
            )

            response = normalize_result(
                module=req.module,
                task_type=req.task_type,
                correlation_id=req.correlation_id,
                model_id=str(raw.get("model") or self.ai_service.model_name),
                parsed_output=validated,
                usage={
                    "input_tokens": raw.get("input_tokens", 0),
                    "output_tokens": raw.get("output_tokens", 0),
                    "total_tokens": raw.get("total_tokens", 0),
                    "cost": raw.get("cost", 0),
                },
                prompt_version=prompt_version,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

            if self.settings.ai_audit_enabled:
                await log_ai_run(req=req, result=response)
            if self.settings.eventbridge_enabled:
                await publish_ai_task_completed(result=response)
            return response
        except Exception as exc:  # noqa: BLE001
            if self.settings.eventbridge_enabled:
                await publish_ai_task_failed(
                    req=req,
                    error_code="ai_orchestration_error",
                    error_message=str(exc),
                )
            raise
