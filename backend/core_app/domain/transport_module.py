"""Transport domain-specific execution module."""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core_app.ai.bedrock_service import BedrockClient
from core_app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class TransportExecutionModule:
    """
    Domain-specific execution module for transport operations.

    Features:
    - Medical necessity justification generation
    - Transport level determination (BLS vs ALS)
    - Destination appropriateness validation
    - Mileage validation and route optimization
    - Specialty transport criteria assessment
    - Inter-facility transfer documentation
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.bedrock = BedrockClient()
        self.audit_service = AuditService(db)

    def determine_transport_level(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        patient_data: dict[str, Any],
        clinical_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Determine appropriate transport level (BLS, ALS, CCT, etc.).

        Args:
            tenant_id: Tenant ID
            actor_id: User ID
            patient_data: Patient demographics
            clinical_data: Clinical assessment data

        Returns:
            Recommended transport level with justification
        """
        system_prompt = """You are an EMS clinical operations expert.
Determine the appropriate level of transport based on patient acuity and clinical needs.

Transport Levels:
- BLS (Basic Life Support): Stable patients, basic medical needs
- ALS (Advanced Life Support): Unstable patients, advanced interventions required
- CCT (Critical Care Transport): ICU-level care, critical patients
- SCT (Specialty Care Transport): Specialty equipment/staff (NICU, bariatric, etc.)

Return a JSON object with:
{
  "recommended_level": "BLS" | "ALS" | "CCT" | "SCT",
  "confidence": <0-100>,
  "clinical_justification": "<why this level is appropriate>",
  "required_equipment": [<list of required equipment>],
  "required_interventions": [<list of required interventions>],
  "upgrade_triggers": [<list of conditions that would require upgrade>],
  "downgrade_safe": <true if downgrade would be safe, false otherwise>
}"""

        user_prompt = f"""Determine transport level for:

PATIENT INFO:
- Age: {patient_data.get('age', 'Unknown')}
- Chief Complaint: {patient_data.get('chief_complaint', 'Unknown')}

VITAL SIGNS:
- BP: {clinical_data.get('blood_pressure', '?')}
- HR: {clinical_data.get('heart_rate', '?')} bpm
- RR: {clinical_data.get('respiratory_rate', '?')}
- SpO2: {clinical_data.get('spo2', '?')}%
- Level of Consciousness: {clinical_data.get('loc', 'Unknown')}
- GCS: {clinical_data.get('gcs', 'Unknown')}

CURRENT CONDITIONS:
- Airway Status: {clinical_data.get('airway', 'Unknown')}
- Breathing Status: {clinical_data.get('breathing', 'Unknown')}
- Circulatory Status: {clinical_data.get('circulation', 'Unknown')}

INTERVENTIONS NEEDED:
{', '.join(clinical_data.get('interventions_needed', ['None identified']))}

MEDICATIONS NEEDED:
{', '.join(clinical_data.get('medications_needed', ['None identified']))}

SPECIAL CONSIDERATIONS:
{clinical_data.get('special_considerations', 'None')}
"""

        try:
            result = self.bedrock.invoke_json_task(
                module="transport",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=1500,
                temperature=0.2,
            )

            parsed = result["parsed"]

            # Audit the determination
            self.audit_service.log_event(
                tenant_id=tenant_id,
                event_type="transport_level_determination",
                actor_id=actor_id,
                resource_type="transport",
                resource_id=str(patient_data.get("incident_id", "unknown")),
                summary=f"Transport level determined: {parsed.get('recommended_level', 'unknown')}",
                metadata={
                    "recommended_level": parsed.get("recommended_level"),
                    "confidence": parsed.get("confidence"),
                    "model_used": result["model_id"],
                    "cost_usd": result["usage"]["cost"],
                },
            )

            return {
                "success": True,
                "recommended_level": parsed.get("recommended_level", "ALS"),  # Default to ALS for safety
                "confidence": parsed.get("confidence", 0),
                "clinical_justification": parsed.get("clinical_justification", ""),
                "required_equipment": parsed.get("required_equipment", []),
                "required_interventions": parsed.get("required_interventions", []),
                "upgrade_triggers": parsed.get("upgrade_triggers", []),
                "downgrade_safe": parsed.get("downgrade_safe", False),
                "requires_human_review": True,
                "usage": result["usage"],
            }

        except Exception as exc:
            logger.error(f"Transport level determination failed: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "recommended_level": "ALS",  # Default to ALS for safety on error
                "requires_human_review": True,
            }

    def validate_destination_appropriateness(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        patient_data: dict[str, Any],
        clinical_data: dict[str, Any],
        proposed_destination: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate destination facility is appropriate for patient needs.

        Args:
            tenant_id: Tenant ID
            actor_id: User ID
            patient_data: Patient data
            clinical_data: Clinical data
            proposed_destination: Destination facility info

        Returns:
            Validation result with alternatives if inappropriate
        """
        system_prompt = """You are an EMS destination determination expert.
Validate whether the proposed destination facility is appropriate for the patient's clinical needs.

Consider:
- Facility capabilities vs patient acuity
- Specialty services required
- Time-critical conditions (stroke, STEMI, trauma)
- Closest appropriate facility principle
- Patient preference when clinically safe

Return a JSON object with:
{
  "is_appropriate": <true/false>,
  "appropriateness_score": <0-100>,
  "justification": "<why destination is or isn't appropriate>",
  "concerns": [<list of concerns about this destination>],
  "alternative_destinations": [
    {
      "facility": "<facility name>",
      "reason": "<why this is more appropriate>",
      "capabilities": [<list of relevant capabilities>]
    }
  ],
  "transport_time_acceptable": <true/false>
}"""

        user_prompt = f"""Validate destination for:

PATIENT:
- Age: {patient_data.get('age', 'Unknown')}
- Chief Complaint: {patient_data.get('chief_complaint', 'Unknown')}
- Working Diagnosis: {clinical_data.get('working_diagnosis', 'Unknown')}
- Acuity: {clinical_data.get('acuity', 'Unknown')}

TIME-CRITICAL CONDITIONS:
- Stroke Alert: {clinical_data.get('stroke_alert', False)}
- STEMI: {clinical_data.get('stemi', False)}
- Trauma Alert: {clinical_data.get('trauma_alert', False)}
- Sepsis: {clinical_data.get('sepsis', False)}

PROPOSED DESTINATION:
- Facility: {proposed_destination.get('name', 'Unknown')}
- Type: {proposed_destination.get('facility_type', 'Unknown')}
- Capabilities: {', '.join(proposed_destination.get('capabilities', ['Unknown']))}
- Distance: {proposed_destination.get('distance_miles', '?')} miles
- Estimated Time: {proposed_destination.get('estimated_time_min', '?')} minutes

PATIENT PREFERENCE:
{patient_data.get('patient_preference', 'None expressed')}
"""

        try:
            result = self.bedrock.invoke_json_task(
                module="transport",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=1500,
                temperature=0.2,
            )

            parsed = result["parsed"]

            # Audit the validation
            self.audit_service.log_event(
                tenant_id=tenant_id,
                event_type="destination_validation",
                actor_id=actor_id,
                resource_type="transport",
                resource_id=str(patient_data.get("incident_id", "unknown")),
                summary=f"Destination validated: {parsed.get('is_appropriate', False)}",
                metadata={
                    "is_appropriate": parsed.get("is_appropriate"),
                    "appropriateness_score": parsed.get("appropriateness_score"),
                    "destination": proposed_destination.get("name"),
                    "model_used": result["model_id"],
                    "cost_usd": result["usage"]["cost"],
                },
            )

            return {
                "success": True,
                "is_appropriate": parsed.get("is_appropriate", False),
                "appropriateness_score": parsed.get("appropriateness_score", 0),
                "justification": parsed.get("justification", ""),
                "concerns": parsed.get("concerns", []),
                "alternative_destinations": parsed.get("alternative_destinations", []),
                "transport_time_acceptable": parsed.get("transport_time_acceptable", True),
                "requires_human_review": not parsed.get("is_appropriate", False),  # Require review if not appropriate
                "usage": result["usage"],
            }

        except Exception as exc:
            logger.error(f"Destination validation failed: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "is_appropriate": False,
                "requires_human_review": True,
            }

    def validate_mileage_and_route(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        origin: dict[str, Any],
        destination: dict[str, Any],
        reported_mileage: float,
        route_taken: str | None = None,
    ) -> dict[str, Any]:
        """
        Validate reported mileage and route reasonableness.

        Args:
            tenant_id: Tenant ID
            actor_id: User ID
            origin: Origin location data
            destination: Destination location data
            reported_mileage: Reported mileage
            route_taken: Optional route description

        Returns:
            Validation result with expected mileage
        """
        system_prompt = """You are an EMS billing compliance expert for transport mileage.
Validate reported mileage against typical routes and identify potential issues.

Consider:
- Direct route distance
- Reasonable variations (traffic, road closures, hospital access)
- Specialty transport routing (NICU, bypass centers)
- Round trip vs one-way

Return a JSON object with:
{
  "is_reasonable": <true/false>,
  "variance_percentage": <percentage difference from expected>,
  "expected_mileage_range": {"min": <float>, "max": <float>},
  "concerns": [<list of concerns>],
  "justification_needed": <true if variance requires justification>,
  "audit_flag": <true if variance suggests audit risk>
}"""

        user_prompt = f"""Validate mileage for:

ORIGIN:
- Type: {origin.get('type', 'Unknown')}
- Address: {origin.get('address', 'Unknown')}
- Coordinates: {origin.get('coordinates', 'Unknown')}

DESTINATION:
- Type: {destination.get('type', 'Unknown')}
- Address: {destination.get('address', 'Unknown')}
- Coordinates: {destination.get('coordinates', 'Unknown')}

REPORTED MILEAGE: {reported_mileage} miles

ROUTE TAKEN: {route_taken or 'Not specified'}

TRANSPORT TYPE: {origin.get('transport_type', 'Emergency')}
"""

        try:
            result = self.bedrock.invoke_json_task(
                module="transport",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=1000,
                temperature=0.2,
            )

            parsed = result["parsed"]

            # Audit the validation
            self.audit_service.log_event(
                tenant_id=tenant_id,
                event_type="mileage_validation",
                actor_id=actor_id,
                resource_type="transport",
                resource_id=str(origin.get("incident_id", "unknown")),
                summary=f"Mileage validated: {parsed.get('is_reasonable', False)} (variance: {parsed.get('variance_percentage', 0):.1f}%)",
                metadata={
                    "is_reasonable": parsed.get("is_reasonable"),
                    "variance_percentage": parsed.get("variance_percentage"),
                    "reported_mileage": reported_mileage,
                    "model_used": result["model_id"],
                    "cost_usd": result["usage"]["cost"],
                },
            )

            return {
                "success": True,
                "is_reasonable": parsed.get("is_reasonable", True),
                "variance_percentage": parsed.get("variance_percentage", 0.0),
                "expected_mileage_range": parsed.get("expected_mileage_range", {"min": 0, "max": 0}),
                "concerns": parsed.get("concerns", []),
                "justification_needed": parsed.get("justification_needed", False),
                "audit_flag": parsed.get("audit_flag", False),
                "usage": result["usage"],
            }

        except Exception as exc:
            logger.error(f"Mileage validation failed: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "is_reasonable": True,  # Default to reasonable on error
            }
