"""Fire/rescue domain-specific execution module."""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core_app.ai.bedrock_service import BedrockClient
from core_app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class FireRescueExecutionModule:
    """
    Domain-specific execution module for fire/rescue operations.

    Features:
    - Incident size-up analysis
    - Resource allocation recommendations
    - Hazmat identification and response
    - Technical rescue planning
    - Incident action plan generation
    - After-action report assistance
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.bedrock = BedrockClient()
        self.audit_service = AuditService(db)

    def generate_incident_size_up(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        incident_data: dict[str, Any],
        scene_observations: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate incident size-up analysis and recommendations.

        Returns:
            Size-up analysis with tactical priorities
        """
        system_prompt = """You are a fire service incident commander.
Provide incident size-up analysis and tactical recommendations.

Size-up Components:
- Facts (what you know)
- Probabilities (what will likely happen)
- Situation (current conditions)
- Decision (strategy and tactics)

Return a JSON object with:
{
  "incident_type": "<type of incident>",
  "priority_actions": [<ordered list of priority actions>],
  "resource_needs": [<list of additional resources needed>],
  "safety_concerns": [<list of safety hazards>],
  "strategy": "offensive" | "defensive" | "transitional",
  "tactical_objectives": [<list of tactical objectives>]
}"""

        user_prompt = f"""Provide size-up for:

INCIDENT:
- Type: {incident_data.get('incident_type', 'Unknown')}
- Location: {incident_data.get('location_type', 'Unknown')}
- Occupancy: {incident_data.get('occupancy', 'Unknown')}
- Construction: {incident_data.get('construction_type', 'Unknown')}

OBSERVATIONS:
- Smoke Showing: {scene_observations.get('smoke_showing', False)}
- Fire Showing: {scene_observations.get('fire_showing', False)}
- Location of Fire: {scene_observations.get('fire_location', 'Unknown')}
- Victims Reported: {scene_observations.get('victims_reported', False)}
- Exposures: {scene_observations.get('exposures', 'None')}

RESOURCES ON SCENE:
- Apparatus: {', '.join(incident_data.get('apparatus', ['Unknown']))}
- Personnel: {incident_data.get('personnel_count', 'Unknown')}
"""

        try:
            result = self.bedrock.invoke_json_task(
                module="fire_rescue",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=1500,
                temperature=0.3,
            )

            parsed = result["parsed"]

            self.audit_service.log_event(
                tenant_id=tenant_id,
                event_type="fire_incident_size_up",
                actor_id=actor_id,
                resource_type="fire_incident",
                resource_id=str(incident_data.get("incident_id", "unknown")),
                summary=f"Size-up generated: {parsed.get('strategy', 'unknown')} strategy",
                metadata={
                    "incident_type": parsed.get("incident_type"),
                    "strategy": parsed.get("strategy"),
                    "model_used": result["model_id"],
                    "cost_usd": result["usage"]["cost"],
                },
            )

            return {
                "success": True,
                "incident_type": parsed.get("incident_type", ""),
                "priority_actions": parsed.get("priority_actions", []),
                "resource_needs": parsed.get("resource_needs", []),
                "safety_concerns": parsed.get("safety_concerns", []),
                "strategy": parsed.get("strategy", "defensive"),
                "tactical_objectives": parsed.get("tactical_objectives", []),
                "requires_human_review": True,
                "usage": result["usage"],
            }

        except Exception as exc:
            logger.error(f"Incident size-up generation failed: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "requires_human_review": True,
            }

    def identify_hazmat(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        material_info: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Identify hazardous materials and provide response guidance.

        Returns:
            Hazmat identification with safety recommendations
        """
        system_prompt = """You are a hazardous materials specialist.
Identify the hazardous material and provide initial response guidance.

Return a JSON object with:
{
  "material_identified": "<name of material>",
  "un_number": "<UN/NA number if applicable>",
  "hazard_class": "<DOT hazard class>",
  "immediate_hazards": [<list of immediate hazards>],
  "ppe_required": [<list of required PPE>],
  "isolation_distance": "<recommended isolation distance>",
  "decontamination_needed": <true/false>,
  "evacuation_recommended": <true/false>,
  "emergency_actions": [<ordered list of emergency actions>]
}"""

        user_prompt = f"""Identify hazmat and provide guidance:

MATERIAL INFORMATION:
- Placard/Label: {material_info.get('placard', 'Unknown')}
- Container Type: {material_info.get('container_type', 'Unknown')}
- Markings: {material_info.get('markings', 'Unknown')}
- Physical State: {material_info.get('physical_state', 'Unknown')}
- Color/Odor: {material_info.get('appearance', 'Unknown')}

INCIDENT CONDITIONS:
- Material Released: {material_info.get('released', False)}
- Fire Involved: {material_info.get('fire_involved', False)}
- Victims Exposed: {material_info.get('victims_exposed', False)}
"""

        try:
            result = self.bedrock.invoke_json_task(
                module="fire_rescue",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=1500,
                temperature=0.2,
            )

            parsed = result["parsed"]

            self.audit_service.log_event(
                tenant_id=tenant_id,
                event_type="hazmat_identification",
                actor_id=actor_id,
                resource_type="hazmat_incident",
                resource_id=str(material_info.get("incident_id", "unknown")),
                summary=f"Hazmat identified: {parsed.get('material_identified', 'unknown')}",
                metadata={
                    "material": parsed.get("material_identified"),
                    "hazard_class": parsed.get("hazard_class"),
                    "model_used": result["model_id"],
                    "cost_usd": result["usage"]["cost"],
                },
            )

            return {
                "success": True,
                "material_identified": parsed.get("material_identified", ""),
                "un_number": parsed.get("un_number", ""),
                "hazard_class": parsed.get("hazard_class", ""),
                "immediate_hazards": parsed.get("immediate_hazards", []),
                "ppe_required": parsed.get("ppe_required", []),
                "isolation_distance": parsed.get("isolation_distance", ""),
                "decontamination_needed": parsed.get("decontamination_needed", False),
                "evacuation_recommended": parsed.get("evacuation_recommended", False),
                "emergency_actions": parsed.get("emergency_actions", []),
                "requires_human_review": True,
                "usage": result["usage"],
            }

        except Exception as exc:
            logger.error(f"Hazmat identification failed: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "requires_human_review": True,
            }

    def generate_incident_action_plan(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        incident_data: dict[str, Any],
        objectives: list[str],
    ) -> dict[str, Any]:
        """
        Generate incident action plan (IAP) for extended operations.

        Returns:
            Structured IAP components
        """
        system_prompt = """You are a fire service planning section chief.
Generate an incident action plan for the operational period.

IAP Components:
- Incident objectives
- Organization chart
- Assignment list
- Communications plan
- Safety message

Return a JSON object with:
{
  "operational_period": "<time period>",
  "incident_objectives": [<list of SMART objectives>],
  "organization": {<key positions and assignments>},
  "tactical_assignments": [<list of tactical assignments>],
  "safety_message": "<primary safety concerns>",
  "communications": {<radio frequencies and protocols>}
}"""

        user_prompt = f"""Generate IAP for:

INCIDENT:
- Type: {incident_data.get('incident_type', 'Unknown')}
- Complexity: {incident_data.get('complexity', 'Unknown')}
- Resources Assigned: {incident_data.get('resources_assigned', 'Unknown')}

OBJECTIVES:
{', '.join(objectives)}

SPECIAL CONSIDERATIONS:
{incident_data.get('special_considerations', 'None')}
"""

        try:
            result = self.bedrock.invoke_json_task(
                module="fire_rescue",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=2000,
                temperature=0.3,
            )

            parsed = result["parsed"]

            self.audit_service.log_event(
                tenant_id=tenant_id,
                event_type="incident_action_plan_generation",
                actor_id=actor_id,
                resource_type="fire_incident",
                resource_id=str(incident_data.get("incident_id", "unknown")),
                summary="Incident Action Plan generated",
                metadata={
                    "operational_period": parsed.get("operational_period"),
                    "objectives_count": len(parsed.get("incident_objectives", [])),
                    "model_used": result["model_id"],
                    "cost_usd": result["usage"]["cost"],
                },
            )

            return {
                "success": True,
                "operational_period": parsed.get("operational_period", ""),
                "incident_objectives": parsed.get("incident_objectives", []),
                "organization": parsed.get("organization", {}),
                "tactical_assignments": parsed.get("tactical_assignments", []),
                "safety_message": parsed.get("safety_message", ""),
                "communications": parsed.get("communications", {}),
                "requires_human_review": True,
                "usage": result["usage"],
            }

        except Exception as exc:
            logger.error(f"IAP generation failed: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "requires_human_review": True,
            }
