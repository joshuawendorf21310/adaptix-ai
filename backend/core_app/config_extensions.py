"""Extended configuration for advanced Bedrock routing and governance features."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import SettingsConfigDict


class BedrockRoutingConfig:
    """Bedrock model routing configuration extensions."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Module-specific model routing
    bedrock_model_id_command: str | None = Field(default=None, alias="ADAPTIX_AI_BEDROCK_MODEL_COMMAND")
    bedrock_model_id_field: str | None = Field(default=None, alias="ADAPTIX_AI_BEDROCK_MODEL_FIELD")
    bedrock_model_id_flow: str | None = Field(default=None, alias="ADAPTIX_AI_BEDROCK_MODEL_FLOW")
    bedrock_model_id_pulse: str | None = Field(default=None, alias="ADAPTIX_AI_BEDROCK_MODEL_PULSE")
    bedrock_model_id_air: str | None = Field(default=None, alias="ADAPTIX_AI_BEDROCK_MODEL_AIR")
    bedrock_model_id_interop: str | None = Field(default=None, alias="ADAPTIX_AI_BEDROCK_MODEL_INTEROP")
    bedrock_model_id_insight: str | None = Field(default=None, alias="ADAPTIX_AI_BEDROCK_MODEL_INSIGHT")
    bedrock_model_id_billing: str | None = Field(default=None, alias="ADAPTIX_AI_BEDROCK_MODEL_BILLING")

    # Region-aware execution
    bedrock_region: str = Field(default="us-east-1", alias="ADAPTIX_AI_BEDROCK_REGION")
    bedrock_region_fallbacks: str = Field(
        default="us-west-2,us-east-2",
        alias="ADAPTIX_AI_BEDROCK_REGION_FALLBACKS"
    )

    # Model allowlists and denylists
    bedrock_allowed_models: str | None = Field(default=None, alias="ADAPTIX_AI_BEDROCK_ALLOWED_MODELS")
    bedrock_denied_models: str | None = Field(default=None, alias="ADAPTIX_AI_BEDROCK_DENIED_MODELS")

    # Fallback configuration
    bedrock_fallback_enabled: bool = Field(default=True, alias="ADAPTIX_AI_BEDROCK_FALLBACK_ENABLED")
    bedrock_fallback_models: str = Field(
        default="anthropic.claude-3-haiku-20240307-v1:0",
        alias="ADAPTIX_AI_BEDROCK_FALLBACK_MODELS"
    )

    # Cost-aware routing
    bedrock_cost_routing_enabled: bool = Field(default=False, alias="ADAPTIX_AI_COST_ROUTING_ENABLED")
    bedrock_max_cost_per_request: float = Field(default=1.0, alias="ADAPTIX_AI_MAX_COST_PER_REQUEST")

    # Quality-aware routing
    bedrock_quality_routing_enabled: bool = Field(default=False, alias="ADAPTIX_AI_QUALITY_ROUTING_ENABLED")
    bedrock_min_quality_score: float = Field(default=0.8, alias="ADAPTIX_AI_MIN_QUALITY_SCORE")

    # Latency-aware routing
    bedrock_latency_routing_enabled: bool = Field(default=False, alias="ADAPTIX_AI_LATENCY_ROUTING_ENABLED")
    bedrock_max_latency_ms: int = Field(default=30000, alias="ADAPTIX_AI_MAX_LATENCY_MS")


class BudgetConfig:
    """Budget tracking and enforcement configuration."""

    # Tenant-level budgets
    tenant_daily_budget_usd: float = Field(default=1000.0, alias="ADAPTIX_AI_TENANT_DAILY_BUDGET_USD")
    tenant_monthly_budget_usd: float = Field(default=30000.0, alias="ADAPTIX_AI_TENANT_MONTHLY_BUDGET_USD")

    # Module-level budgets
    module_daily_budget_usd: float = Field(default=100.0, alias="ADAPTIX_AI_MODULE_DAILY_BUDGET_USD")

    # Budget enforcement
    budget_hard_cap_enabled: bool = Field(default=False, alias="ADAPTIX_AI_BUDGET_HARD_CAP_ENABLED")
    budget_soft_cap_threshold: float = Field(default=0.9, alias="ADAPTIX_AI_BUDGET_SOFT_CAP_THRESHOLD")
    budget_alert_enabled: bool = Field(default=True, alias="ADAPTIX_AI_BUDGET_ALERT_ENABLED")


class ReviewWorkflowConfig:
    """Review workflow configuration."""

    # Review requirements
    review_enabled: bool = Field(default=True, alias="ADAPTIX_AI_REVIEW_ENABLED")
    review_high_risk_required: bool = Field(default=True, alias="ADAPTIX_AI_REVIEW_HIGH_RISK_REQUIRED")
    review_billing_required: bool = Field(default=True, alias="ADAPTIX_AI_REVIEW_BILLING_REQUIRED")
    review_phi_required: bool = Field(default=True, alias="ADAPTIX_AI_REVIEW_PHI_REQUIRED")

    # Review thresholds
    review_confidence_threshold: float = Field(default=0.7, alias="ADAPTIX_AI_REVIEW_CONFIDENCE_THRESHOLD")
    review_cost_threshold_usd: float = Field(default=5.0, alias="ADAPTIX_AI_REVIEW_COST_THRESHOLD_USD")

    # Review escalation
    review_escalation_enabled: bool = Field(default=True, alias="ADAPTIX_AI_REVIEW_ESCALATION_ENABLED")
    review_escalation_hours: int = Field(default=24, alias="ADAPTIX_AI_REVIEW_ESCALATION_HOURS")
