"""Air medical transport domain-specific execution module."""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core_app.ai.bedrock_service import BedrockClient
from core_app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class AirMedicalExecutionModule:
    """
    Domain-specific execution module for air medical transport.

    Features:
    - Flight criteria validation
    - Weather safety assessment
    - Landing zone safety evaluation
    - Air medical necessity justification
    - Rotor vs fixed-wing determination
    - Critical care capability assessment
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.bedrock = BedrockClient()
        self.audit_service = AuditService(db)

    def validate_flight_criteria(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        patient_data: dict[str, Any],
        clinical_data: dict[str, Any],
        scene_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate that patient meets air medical transport criteria.

        Returns:
            Validation result with justification
        """
        system_prompt = """You are an air medical operations expert.
Validate whether air medical transport is clinically justified and appropriate.

Air Medical Indications:
- Time-critical conditions (trauma, STEMI, stroke)
- Remote/difficult access locations
- Extended ground transport time
- Need for specialized critical care
- Scene safety concerns precluding ground access

Return a JSON object with:
{
  "criteria_met": <true/false>,
  "justification": "<clinical and operational justification>",
  "primary_indication": "<primary reason for air transport>",
  "time_savings_minutes": <estimated minutes saved>,
  "clinical_benefits": [<list of clinical benefits>],
  "risks": [<list of risks to consider>]
}"""

        user_prompt = f"""Validate air medical criteria for:

PATIENT:
- Age: {patient_data.get('age', 'Unknown')}
- Chief Complaint: {patient_data.get('chief_complaint', 'Unknown')}
- Trauma Alert Level: {clinical_data.get('trauma_level', 'N/A')}
- Vital Signs: BP {clinical_data.get('blood_pressure', '?')}, HR {clinical_data.get('heart_rate', '?')}, SpO2 {clinical_data.get('spo2', '?')}%

SCENE:
- Location Type: {scene_data.get('location_type', 'Unknown')}
- Distance to Trauma Center: {scene_data.get('distance_to_trauma_center', '?')} miles
- Ground Transport Time: {scene_data.get('ground_transport_time', '?')} minutes
- Scene Access Difficulty: {scene_data.get('access_difficulty', 'Unknown')}

TIME-CRITICAL CONDITIONS:
- Stroke: {clinical_data.get('stroke', False)}
- STEMI: {clinical_data.get('stemi', False)}
- Major Trauma: {clinical_data.get('major_trauma', False)}
"""

        try:
            result = self.bedrock.invoke_json_task(
                module="air_medical",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=1200,
                temperature=0.2,
            )

            parsed = result["parsed"]

            self.audit_service.log_event(
                tenant_id=tenant_id,
                event_type="air_medical_criteria_validation",
                actor_id=actor_id,
                resource_type="air_transport",
                resource_id=str(patient_data.get("incident_id", "unknown")),
                summary=f"Air medical criteria: {parsed.get('criteria_met', False)}",
                metadata={
                    "criteria_met": parsed.get("criteria_met"),
                    "model_used": result["model_id"],
                    "cost_usd": result["usage"]["cost"],
                },
            )

            return {
                "success": True,
                "criteria_met": parsed.get("criteria_met", False),
                "justification": parsed.get("justification", ""),
                "primary_indication": parsed.get("primary_indication", ""),
                "time_savings_minutes": parsed.get("time_savings_minutes", 0),
                "clinical_benefits": parsed.get("clinical_benefits", []),
                "risks": parsed.get("risks", []),
                "requires_human_review": True,
                "usage": result["usage"],
            }

        except Exception as exc:
            logger.error(f"Flight criteria validation failed: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "criteria_met": False,
                "requires_human_review": True,
            }

    def assess_landing_zone_safety(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        lz_data: dict[str, Any],
        weather_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Assess landing zone safety for helicopter operations.

        Returns:
            Safety assessment with recommendations
        """
        system_prompt = """You are a helicopter landing zone safety officer.
Assess landing zone safety based on size, obstacles, weather, and hazards.

LZ Requirements:
- Minimum size: 100x100 feet (day), 125x125 feet (night)
- Clear of obstacles (wires, poles, trees)
- Firm, level surface
- No debris or loose materials
- Safe approach/departure paths
- Adequate weather conditions

Return a JSON object with:
{
  "is_safe": <true/false>,
  "safety_score": <0-100>,
  "hazards": [<list of identified hazards>],
  "recommendations": [<list of safety recommendations>],
  "approval_status": "approved" | "conditional" | "not_approved"
}"""

        user_prompt = f"""Assess landing zone safety:

LZ SPECIFICATIONS:
- Size: {lz_data.get('size_feet', 'Unknown')} x {lz_data.get('size_feet', 'Unknown')} feet
- Surface Type: {lz_data.get('surface_type', 'Unknown')}
- Slope: {lz_data.get('slope', 'Unknown')}
- Obstacles: {', '.join(lz_data.get('obstacles', ['None reported']))}
- Lighting: {lz_data.get('lighting', 'Unknown')}

WEATHER:
- Visibility: {weather_data.get('visibility_miles', '?')} miles
- Ceiling: {weather_data.get('ceiling_feet', '?')} feet
- Winds: {weather_data.get('wind_speed_kts', '?')} knots from {weather_data.get('wind_direction', '?')}
- Precipitation: {weather_data.get('precipitation', 'None')}
"""

        try:
            result = self.bedrock.invoke_json_task(
                module="air_medical",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=1000,
                temperature=0.2,
            )

            parsed = result["parsed"]

            self.audit_service.log_event(
                tenant_id=tenant_id,
                event_type="landing_zone_assessment",
                actor_id=actor_id,
                resource_type="air_transport",
                resource_id=str(lz_data.get("lz_id", "unknown")),
                summary=f"LZ safety: {parsed.get('approval_status', 'unknown')}",
                metadata={
                    "is_safe": parsed.get("is_safe"),
                    "safety_score": parsed.get("safety_score"),
                    "model_used": result["model_id"],
                    "cost_usd": result["usage"]["cost"],
                },
            )

            return {
                "success": True,
                "is_safe": parsed.get("is_safe", False),
                "safety_score": parsed.get("safety_score", 0),
                "hazards": parsed.get("hazards", []),
                "recommendations": parsed.get("recommendations", []),
                "approval_status": parsed.get("approval_status", "not_approved"),
                "requires_human_review": True,
                "usage": result["usage"],
            }

        except Exception as exc:
            logger.error(f"LZ safety assessment failed: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "is_safe": False,
                "approval_status": "not_approved",
                "requires_human_review": True,
            }
