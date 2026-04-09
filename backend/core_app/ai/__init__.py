"""Adaptix AI package for embedded intelligence inside Adaptix Core.

This package exposes the canonical orchestration boundary for AI behavior while
preserving compatibility with existing Bedrock and legacy AI service interfaces.
"""

from core_app.ai.bedrock_service import BedrockClient, get_bedrock_client
from core_app.ai.context.assembler import ContextAssembler
from core_app.ai.guardrails import (
    AiBillingDraftOutput,
    AiNarrativeOutput,
    AiOutput,
    check_medical_accuracy,
    contains_phi,
    detect_hallucination_risk,
    enforce_compliance_rules,
    redact_phi,
    validate_ai_output,
    validate_medical_codes,
)
from core_app.ai.orchestrator import AiOrchestrator, AiTaskRequest
from core_app.ai.prompt_registry import build_prompt
from core_app.ai.service import AiService
from core_app.ai.task_types import AiModule, AiTaskType

__all__ = [
    "BedrockClient",
    "get_bedrock_client",
    "AiOrchestrator",
    "AiTaskRequest",
    "build_prompt",
    "ContextAssembler",
    "AiModule",
    "AiTaskType",
    "AiService",
    "AiOutput",
    "AiNarrativeOutput",
    "AiBillingDraftOutput",
    "contains_phi",
    "redact_phi",
    "detect_hallucination_risk",
    "check_medical_accuracy",
    "enforce_compliance_rules",
    "validate_medical_codes",
    "validate_ai_output",
]
