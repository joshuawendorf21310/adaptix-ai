from __future__ import annotations

from core_app.ai.orchestrator import AiOrchestrator, AiTaskRequest


class AiJobWorker:
    def __init__(self) -> None:
        self.orchestrator = AiOrchestrator()

    async def handle(self, job_payload: dict) -> dict:
        req = AiTaskRequest(**job_payload)
        result = await self.orchestrator.run(req)
        return result.model_dump(mode="json") if hasattr(result, "model_dump") else dict(result)
