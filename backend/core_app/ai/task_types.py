from __future__ import annotations

from enum import StrEnum


class AiModule(StrEnum):
    COMMAND = "command"
    FIELD = "field"
    FLOW = "flow"
    PULSE = "pulse"
    AIR = "air"
    INTEROP = "interop"
    INSIGHT = "insight"


class AiTaskType(StrEnum):
    INCIDENT_SUMMARY = "incident_summary"
    OPERATING_PICTURE = "operating_picture"
    DEPLOYMENT_RECOMMENDATION = "deployment_recommendation"
    NARRATIVE_GENERATION = "narrative_generation"
    SCENE_SUMMARY = "scene_summary"
    HANDOFF_SUMMARY = "handoff_summary"
    COVERAGE_ANALYSIS = "coverage_analysis"
    REDEPLOYMENT_RECOMMENDATION = "redeployment_recommendation"
    TRANSPORT_BOTTLENECK_ANALYSIS = "transport_bottleneck_analysis"
    FATIGUE_ANALYSIS = "fatigue_analysis"
    READINESS_SUMMARY = "readiness_summary"
    MISSION_BRIEF = "mission_brief"
    LAUNCH_CONTEXT = "launch_context"
    CROSS_SYSTEM_INTERPRETATION = "cross_system_interpretation"
    SOURCE_RECONCILIATION = "source_reconciliation"
    EXECUTIVE_SUMMARY = "executive_summary"
    PERFORMANCE_TREND_SUMMARY = "performance_trend_summary"
