"""Model routing service for intelligent Bedrock model selection."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from core_app.ai.bedrock_service import MODEL_PRICING, DEFAULT_MODELS
from core_app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ModelRoutingDecision:
    """Result of model routing logic."""
    model_id: str
    reason: str
    estimated_cost_per_1k_tokens: Decimal
    fallback_chain: list[str]
    routing_strategy: str


class ModelRoutingService:
    """
    Intelligent model selection based on task type, cost, quality, and latency requirements.

    Implements:
    - Task-type-based routing
    - Cost-aware routing
    - Quality-aware routing
    - Latency-aware routing
    - Module-specific overrides
    - Fallback chains
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._build_routing_rules()

    def _build_routing_rules(self) -> None:
        """Build routing rules from configuration."""
        # Task-type to model mapping
        self.task_rules: dict[str, str] = {
            # High-accuracy tasks (billing, compliance, medical)
            "claim_readiness_scoring": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "denial_risk_analysis": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "medical_necessity_summary": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "narrative_generation": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "coding_support": "anthropic.claude-3-5-sonnet-20241022-v2:0",

            # Balanced tasks (summaries, analysis)
            "incident_summary": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "executive_summary": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "operating_picture": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "transport_optimization": "anthropic.claude-3-5-sonnet-20241022-v2:0",

            # Fast tasks (classification, extraction, simple summaries)
            "scene_classification": "anthropic.claude-3-haiku-20240307-v1:0",
            "data_extraction": "anthropic.claude-3-haiku-20240307-v1:0",
            "simple_summary": "anthropic.claude-3-haiku-20240307-v1:0",
            "tag_generation": "anthropic.claude-3-haiku-20240307-v1:0",
        }

        # Module to model override mapping
        self.module_overrides: dict[str, str | None] = {
            "command": self.settings.bedrock_model_id_command,
            "field": self.settings.bedrock_model_id_field,
            "flow": self.settings.bedrock_model_id_flow,
            "pulse": self.settings.bedrock_model_id_pulse,
            "air": self.settings.bedrock_model_id_air,
            "interop": self.settings.bedrock_model_id_interop,
            "insight": self.settings.bedrock_model_id_insight,
            "billing": self.settings.bedrock_model_id_billing,
        }

        # Parse allowlist/denylist
        self.allowed_models: set[str] | None = None
        if self.settings.bedrock_allowed_models:
            self.allowed_models = {
                m.strip() for m in self.settings.bedrock_allowed_models.split(",") if m.strip()
            }

        self.denied_models: set[str] = set()
        if self.settings.bedrock_denied_models:
            self.denied_models = {
                m.strip() for m in self.settings.bedrock_denied_models.split(",") if m.strip()
            }

        # Fallback chain
        self.fallback_models: list[str] = []
        if self.settings.bedrock_fallback_models:
            self.fallback_models = [
                m.strip() for m in self.settings.bedrock_fallback_models.split(",") if m.strip()
            ]

    def route(
        self,
        *,
        module: str | None = None,
        task_type: str | None = None,
        priority: Literal["high_accuracy", "balanced", "fast"] = "balanced",
        max_cost_usd: float | None = None,
        max_latency_ms: int | None = None,
        min_quality_score: float | None = None,
    ) -> ModelRoutingDecision:
        """
        Route request to appropriate Bedrock model.

        Args:
            module: Module name (e.g., "billing", "command")
            task_type: Task type (e.g., "claim_readiness_scoring")
            priority: Priority level for default routing
            max_cost_usd: Maximum cost per request in USD
            max_latency_ms: Maximum acceptable latency in milliseconds
            min_quality_score: Minimum required quality score

        Returns:
            ModelRoutingDecision with selected model and metadata
        """
        # Strategy 1: Module-specific override
        if module and module in self.module_overrides:
            override = self.module_overrides[module]
            if override and self._is_model_allowed(override):
                return self._build_decision(
                    model_id=override,
                    reason=f"module_override:{module}",
                    strategy="module_override"
                )

        # Strategy 2: Task-type-based routing
        if task_type and task_type in self.task_rules:
            model_id = self.task_rules[task_type]
            if self._is_model_allowed(model_id):
                # Check cost constraint
                if max_cost_usd and not self._meets_cost_constraint(model_id, max_cost_usd):
                    # Fallback to cheaper model
                    cheaper_model = self._find_cheaper_model(model_id, max_cost_usd)
                    if cheaper_model:
                        return self._build_decision(
                            model_id=cheaper_model,
                            reason=f"cost_constraint:max_${max_cost_usd}",
                            strategy="cost_aware"
                        )

                return self._build_decision(
                    model_id=model_id,
                    reason=f"task_type:{task_type}",
                    strategy="task_type"
                )

        # Strategy 3: Priority-based routing
        default_model = DEFAULT_MODELS.get(priority, DEFAULT_MODELS["balanced"])
        if self._is_model_allowed(default_model):
            # Check cost constraint
            if max_cost_usd and not self._meets_cost_constraint(default_model, max_cost_usd):
                cheaper_model = self._find_cheaper_model(default_model, max_cost_usd)
                if cheaper_model:
                    return self._build_decision(
                        model_id=cheaper_model,
                        reason=f"cost_constraint:max_${max_cost_usd}",
                        strategy="cost_aware"
                    )

            return self._build_decision(
                model_id=default_model,
                reason=f"priority:{priority}",
                strategy="priority"
            )

        # Strategy 4: Global default
        default = self.settings.bedrock_model_id
        return self._build_decision(
            model_id=default,
            reason="global_default",
            strategy="default"
        )

    def _is_model_allowed(self, model_id: str) -> bool:
        """Check if model is allowed per allowlist/denylist."""
        if model_id in self.denied_models:
            return False
        if self.allowed_models is not None:
            return model_id in self.allowed_models
        return True

    def _meets_cost_constraint(self, model_id: str, max_cost_usd: float) -> bool:
        """Check if model meets cost constraint."""
        if model_id not in MODEL_PRICING:
            return True  # Unknown model, allow

        pricing = MODEL_PRICING[model_id]
        # Estimate cost for 1000 tokens (500 input, 500 output)
        estimated_cost = (
            (Decimal(500) / Decimal(1_000_000)) * pricing["input"] +
            (Decimal(500) / Decimal(1_000_000)) * pricing["output"]
        )
        return float(estimated_cost) <= max_cost_usd

    def _find_cheaper_model(self, current_model: str, max_cost_usd: float) -> str | None:
        """Find a cheaper alternative model."""
        # Try haiku first (cheapest)
        haiku = "anthropic.claude-3-haiku-20240307-v1:0"
        if self._is_model_allowed(haiku) and self._meets_cost_constraint(haiku, max_cost_usd):
            return haiku

        # Try other models in fallback chain
        for model in self.fallback_models:
            if self._is_model_allowed(model) and self._meets_cost_constraint(model, max_cost_usd):
                return model

        return None

    def _build_decision(
        self,
        model_id: str,
        reason: str,
        strategy: str
    ) -> ModelRoutingDecision:
        """Build routing decision with metadata."""
        # Calculate estimated cost
        if model_id in MODEL_PRICING:
            pricing = MODEL_PRICING[model_id]
            cost_per_1k = (
                (Decimal(500) / Decimal(1_000_000)) * pricing["input"] +
                (Decimal(500) / Decimal(1_000_000)) * pricing["output"]
            )
        else:
            cost_per_1k = Decimal("0.001")  # Unknown model estimate

        # Build fallback chain
        fallback_chain = [model_id]
        if self.settings.bedrock_fallback_enabled:
            for fallback in self.fallback_models:
                if fallback != model_id and self._is_model_allowed(fallback):
                    fallback_chain.append(fallback)

        return ModelRoutingDecision(
            model_id=model_id,
            reason=reason,
            estimated_cost_per_1k_tokens=cost_per_1k,
            fallback_chain=fallback_chain,
            routing_strategy=strategy
        )

    def get_fallback_chain(self, primary_model: str) -> list[str]:
        """Get fallback chain for a primary model."""
        chain = [primary_model]
        if self.settings.bedrock_fallback_enabled:
            for fallback in self.fallback_models:
                if fallback != primary_model and self._is_model_allowed(fallback):
                    chain.append(fallback)
        return chain
