"""Enhanced AI task types for all Adaptix domains."""
from __future__ import annotations

from enum import StrEnum


class AiModule(StrEnum):
    """Adaptix AI modules."""
    COMMAND = "command"
    FIELD = "field"
    FLOW = "flow"
    PULSE = "pulse"
    AIR = "air"
    INTEROP = "interop"
    INSIGHT = "insight"
    BILLING = "billing"
    TRANSPORT = "transport"
    CREW = "crew"
    WORKFORCE = "workforce"
    FIRE = "fire"


class AiTaskType(StrEnum):
    """Comprehensive AI task types across all domains."""

    # Command/Executive tasks
    INCIDENT_SUMMARY = "incident_summary"
    OPERATING_PICTURE = "operating_picture"
    DEPLOYMENT_RECOMMENDATION = "deployment_recommendation"
    EXECUTIVE_SUMMARY = "executive_summary"
    PERFORMANCE_TREND_SUMMARY = "performance_trend_summary"
    INVESTOR_SUMMARY = "investor_summary"
    ESCALATION_DIGEST = "escalation_digest"
    CROSS_DOMAIN_SYNTHESIS = "cross_domain_synthesis"

    # Field/ePCR tasks
    NARRATIVE_GENERATION = "narrative_generation"
    SCENE_SUMMARY = "scene_summary"
    HANDOFF_SUMMARY = "handoff_summary"
    CHART_QUALITY_SCORING = "chart_quality_scoring"
    MISSING_DATA_DETECTION = "missing_data_detection"
    CONTRADICTION_DETECTION = "contradiction_detection"
    NEMSIS_READINESS_HINTS = "nemsis_readiness_hints"
    OCR_CLEANUP = "ocr_cleanup"
    PRIOR_ENCOUNTER_SUMMARIZATION = "prior_encounter_summarization"
    TREATMENT_SUMMARY_DRAFTING = "treatment_summary_drafting"
    QA_COACHING = "qa_coaching"

    # Billing tasks
    CLAIM_READINESS_SCORING = "claim_readiness_scoring"
    DENIAL_RISK_ANALYSIS = "denial_risk_analysis"
    MEDICAL_NECESSITY_SUMMARY = "medical_necessity_summary"
    DOCUMENTATION_COMPLETENESS = "documentation_completeness"
    PAYER_RULE_EXPLANATION = "payer_rule_explanation"
    CODING_SUPPORT = "coding_support"
    BILLING_PRECHECK = "billing_precheck"
    CHARGE_CAPTURE_ASSIST = "charge_capture_assist"
    MISSING_SIGNATURE_DETECTION = "missing_signature_detection"
    BILLING_EXCEPTION_CLUSTERING = "billing_exception_clustering"
    DENIAL_PATTERN_DETECTION = "denial_pattern_detection"
    STATEMENT_LANGUAGE_SIMPLIFICATION = "statement_language_simplification"
    DOCUMENT_CLASSIFICATION = "document_classification"

    # Transport/Flow tasks
    TRANSPORT_OPTIMIZATION = "transport_optimization"
    TRANSPORT_BOTTLENECK_ANALYSIS = "transport_bottleneck_analysis"
    SCHEDULING_HINTS = "scheduling_hints"
    RECURRING_PATTERN_ANALYSIS = "recurring_pattern_analysis"
    MEDICAL_NECESSITY_TRANSPORT = "medical_necessity_transport"
    DOCUMENT_FLOW_STATUS = "document_flow_status"

    # Crew/Workforce tasks
    COVERAGE_ANALYSIS = "coverage_analysis"
    REDEPLOYMENT_RECOMMENDATION = "redeployment_recommendation"
    FATIGUE_ANALYSIS = "fatigue_analysis"
    READINESS_SUMMARY = "readiness_summary"
    STAFFING_SHORTFALL_EXPLANATION = "staffing_shortfall_explanation"
    COVERAGE_RISK_EXPLANATION = "coverage_risk_explanation"
    ESCALATION_SUGGESTION = "escalation_suggestion"

    # Air tasks
    MISSION_BRIEF = "mission_brief"
    LAUNCH_CONTEXT = "launch_context"
    WEATHER_SUMMARY = "weather_summary"
    CHECKLIST_ANOMALY_DETECTION = "checklist_anomaly_detection"
    FLIGHT_RISK_EXPLANATION = "flight_risk_explanation"
    POSTFLIGHT_DEBRIEF = "postflight_debrief"

    # Fire tasks
    FIRE_INCIDENT_SUMMARY = "fire_incident_summary"
    INSPECTION_DEFICIENCY_SUMMARY = "inspection_deficiency_summary"
    NERIS_READINESS_SCORING = "neris_readiness_scoring"
    PREPLAN_SUMMARIZATION = "preplan_summarization"

    # Interop/Integration tasks
    CROSS_SYSTEM_INTERPRETATION = "cross_system_interpretation"
    SOURCE_RECONCILIATION = "source_reconciliation"

    # Analytics/Insight tasks
    TREND_ANALYSIS = "trend_analysis"
    ANOMALY_EXPLANATION = "anomaly_explanation"
    PATTERN_DETECTION = "pattern_detection"

    # General AI patterns
    CLASSIFY = "classify"
    EXTRACT = "extract"
    SUMMARIZE = "summarize"
    COMPARE = "compare"
    EXPLAIN = "explain"
    SCORE = "score"
    RECOMMEND = "recommend"
    TRANSFORM = "transform"
    VALIDATE = "validate"


class TaskPriority(StrEnum):
    """Task priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class TaskRiskLevel(StrEnum):
    """Task risk classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Task-specific configuration mapping
TASK_CONFIG = {
    # High-risk tasks requiring human review
    "high_risk_tasks": {
        AiTaskType.NARRATIVE_GENERATION,
        AiTaskType.MEDICAL_NECESSITY_SUMMARY,
        AiTaskType.CODING_SUPPORT,
        AiTaskType.CLAIM_READINESS_SCORING,
        AiTaskType.DENIAL_RISK_ANALYSIS,
        AiTaskType.BILLING_PRECHECK,
        AiTaskType.INVESTOR_SUMMARY,
    },

    # PHI-sensitive tasks requiring extra guardrails
    "phi_sensitive_tasks": {
        AiTaskType.NARRATIVE_GENERATION,
        AiTaskType.CHART_QUALITY_SCORING,
        AiTaskType.MEDICAL_NECESSITY_SUMMARY,
        AiTaskType.PRIOR_ENCOUNTER_SUMMARIZATION,
        AiTaskType.BILLING_PRECHECK,
    },

    # Billing-specific tasks
    "billing_tasks": {
        AiTaskType.CLAIM_READINESS_SCORING,
        AiTaskType.DENIAL_RISK_ANALYSIS,
        AiTaskType.MEDICAL_NECESSITY_SUMMARY,
        AiTaskType.DOCUMENTATION_COMPLETENESS,
        AiTaskType.PAYER_RULE_EXPLANATION,
        AiTaskType.CODING_SUPPORT,
        AiTaskType.BILLING_PRECHECK,
        AiTaskType.CHARGE_CAPTURE_ASSIST,
        AiTaskType.MISSING_SIGNATURE_DETECTION,
        AiTaskType.BILLING_EXCEPTION_CLUSTERING,
        AiTaskType.DENIAL_PATTERN_DETECTION,
    },

    # Executive/Founder tasks
    "executive_tasks": {
        AiTaskType.EXECUTIVE_SUMMARY,
        AiTaskType.INVESTOR_SUMMARY,
        AiTaskType.ESCALATION_DIGEST,
        AiTaskType.CROSS_DOMAIN_SYNTHESIS,
        AiTaskType.PERFORMANCE_TREND_SUMMARY,
    },

    # Fast tasks suitable for haiku model
    "fast_tasks": {
        AiTaskType.CLASSIFY,
        AiTaskType.EXTRACT,
        AiTaskType.SCENE_SUMMARY,
        AiTaskType.MISSING_DATA_DETECTION,
        AiTaskType.DOCUMENT_CLASSIFICATION,
        AiTaskType.PATTERN_DETECTION,
    },
}


def is_high_risk_task(task_type: str) -> bool:
    """Check if task type is high risk."""
    return task_type in TASK_CONFIG["high_risk_tasks"]


def is_phi_sensitive_task(task_type: str) -> bool:
    """Check if task type is PHI-sensitive."""
    return task_type in TASK_CONFIG["phi_sensitive_tasks"]


def is_billing_task(task_type: str) -> bool:
    """Check if task type is billing-related."""
    return task_type in TASK_CONFIG["billing_tasks"]


def is_executive_task(task_type: str) -> bool:
    """Check if task type is executive-level."""
    return task_type in TASK_CONFIG["executive_tasks"]


def requires_review(task_type: str) -> bool:
    """Determine if task requires human review."""
    return is_high_risk_task(task_type) or is_billing_task(task_type)


def get_recommended_model_tier(task_type: str) -> str:
    """Get recommended model tier for task type."""
    if task_type in TASK_CONFIG["fast_tasks"]:
        return "fast"
    elif is_billing_task(task_type) or is_executive_task(task_type):
        return "high_accuracy"
    else:
        return "balanced"
