"""ePCR (Electronic Patient Care Report) domain-specific execution module."""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core_app.ai.bedrock_service import BedrockClient
from core_app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class EPCRExecutionModule:
    """
    Domain-specific execution module for ePCR tasks.

    Features:
    - Narrative generation from structured data
    - Clinical documentation validation
    - ICD-10 code suggestions
    - Medical necessity justification
    - Protocol compliance checking
    - Quality assurance scoring
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.bedrock = BedrockClient()
        self.audit_service = AuditService(db)

    def generate_narrative(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        patient_data: dict[str, Any],
        assessment_data: dict[str, Any],
        treatment_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate clinical narrative from structured ePCR data.

        Args:
            tenant_id: Tenant ID
            actor_id: User ID
            patient_data: Patient demographics and chief complaint
            assessment_data: Assessment findings
            treatment_data: Treatments and interventions

        Returns:
            Generated narrative with quality score
        """
        system_prompt = """You are an expert EMS paramedic documentation specialist.
Generate a clear, concise, professional patient care narrative from the provided structured data.

The narrative should:
- Follow chronological order (dispatch → scene → assessment → treatment → transport → transfer)
- Use proper medical terminology
- Include relevant negatives
- Document medical decision-making
- Support medical necessity for transport

Return a JSON object with:
{
  "narrative": "<complete patient care narrative>",
  "quality_score": <0-100, based on completeness and clarity>,
  "missing_elements": [<list of recommended additions>],
  "compliance_notes": [<list of compliance considerations>]
}"""

        user_prompt = f"""Generate narrative for:

DISPATCH INFO:
- Chief Complaint: {patient_data.get('chief_complaint', 'Unknown')}
- Dispatch Code: {patient_data.get('dispatch_code', 'Unknown')}
- Response Priority: {patient_data.get('priority', 'Unknown')}

PATIENT INFO:
- Age: {patient_data.get('age', 'Unknown')} years
- Sex: {patient_data.get('sex', 'Unknown')}
- Weight: {patient_data.get('weight', 'Unknown')} kg

SCENE ASSESSMENT:
- Scene Safety: {assessment_data.get('scene_safety', 'Unknown')}
- Mechanism of Injury: {assessment_data.get('moi', 'N/A')}

PRIMARY ASSESSMENT:
- Level of Consciousness: {assessment_data.get('loc', 'Unknown')}
- Airway: {assessment_data.get('airway', 'Unknown')}
- Breathing: {assessment_data.get('breathing', 'Unknown')}
- Circulation: {assessment_data.get('circulation', 'Unknown')}

VITAL SIGNS:
- BP: {assessment_data.get('blood_pressure', '?')}
- HR: {assessment_data.get('heart_rate', '?')} bpm
- RR: {assessment_data.get('respiratory_rate', '?')} breaths/min
- SpO2: {assessment_data.get('spo2', '?')}%
- Temp: {assessment_data.get('temperature', '?')}°F
- Blood Glucose: {assessment_data.get('glucose', '?')} mg/dL

TREATMENTS PROVIDED:
{', '.join(treatment_data.get('interventions', ['None documented']))}

MEDICATIONS ADMINISTERED:
{', '.join(treatment_data.get('medications', ['None documented']))}

PATIENT RESPONSE:
{treatment_data.get('response_to_treatment', 'Not documented')}

TRANSPORT:
- Destination: {treatment_data.get('destination', 'Unknown')}
- Transport Mode: {treatment_data.get('transport_mode', 'Unknown')}
- Patient Position: {treatment_data.get('patient_position', 'Unknown')}
"""

        try:
            result = self.bedrock.invoke_json_task(
                module="epcr",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=2000,
                temperature=0.3,
            )

            parsed = result["parsed"]

            # Audit the generation
            self.audit_service.log_event(
                tenant_id=tenant_id,
                event_type="epcr_narrative_generation",
                actor_id=actor_id,
                resource_type="epcr",
                resource_id=str(patient_data.get("incident_id", "unknown")),
                summary=f"ePCR narrative generated (quality: {parsed.get('quality_score', 0)}/100)",
                metadata={
                    "quality_score": parsed.get("quality_score"),
                    "model_used": result["model_id"],
                    "cost_usd": result["usage"]["cost"],
                },
            )

            return {
                "success": True,
                "narrative": parsed.get("narrative", ""),
                "quality_score": parsed.get("quality_score", 0),
                "missing_elements": parsed.get("missing_elements", []),
                "compliance_notes": parsed.get("compliance_notes", []),
                "requires_human_review": True,
                "usage": result["usage"],
            }

        except Exception as exc:
            logger.error(f"ePCR narrative generation failed: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "requires_human_review": True,
            }

    def validate_clinical_documentation(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        epcr_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate clinical documentation completeness and quality.

        Args:
            tenant_id: Tenant ID
            actor_id: User ID
            epcr_data: Complete ePCR data

        Returns:
            Validation results with gaps identified
        """
        system_prompt = """You are an EMS quality assurance specialist.
Review the ePCR for clinical documentation completeness and quality.

Evaluate:
- Completeness of assessment documentation
- Treatment rationale and medical decision-making
- Vital signs trending
- Protocol adherence
- Medical necessity documentation
- Patient outcome documentation

Return a JSON object with:
{
  "validation_score": <0-100>,
  "status": "excellent" | "acceptable" | "needs_improvement" | "critical_deficiencies",
  "critical_issues": [<list of critical documentation gaps>],
  "recommendations": [<list of improvement suggestions>],
  "protocol_compliance": <true/false>,
  "billing_readiness": <true/false>
}"""

        user_prompt = f"""Validate ePCR documentation:

Chief Complaint: {epcr_data.get('chief_complaint', 'Missing')}
Narrative Quality: {epcr_data.get('narrative_length', 0)} characters
Assessment Documented: {bool(epcr_data.get('assessment'))}
Treatments Documented: {len(epcr_data.get('treatments', []))} interventions
Vital Signs Sets: {len(epcr_data.get('vital_signs_sets', []))}
Patient Response to Treatment: {bool(epcr_data.get('response_to_treatment'))}
Medical Necessity Statement: {bool(epcr_data.get('medical_necessity'))}
Signatures Complete: {epcr_data.get('signatures_complete', False)}
Protocol Reference: {epcr_data.get('protocol_reference', 'None')}
"""

        try:
            result = self.bedrock.invoke_json_task(
                module="epcr",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=1500,
                temperature=0.2,
            )

            parsed = result["parsed"]

            # Audit the validation
            self.audit_service.log_event(
                tenant_id=tenant_id,
                event_type="epcr_validation",
                actor_id=actor_id,
                resource_type="epcr",
                resource_id=str(epcr_data.get("epcr_id", "unknown")),
                summary=f"ePCR validated: {parsed.get('status', 'unknown')} ({parsed.get('validation_score', 0)}/100)",
                metadata={
                    "validation_score": parsed.get("validation_score"),
                    "status": parsed.get("status"),
                    "model_used": result["model_id"],
                    "cost_usd": result["usage"]["cost"],
                },
            )

            return {
                "success": True,
                "validation_score": parsed.get("validation_score", 0),
                "status": parsed.get("status", "unknown"),
                "critical_issues": parsed.get("critical_issues", []),
                "recommendations": parsed.get("recommendations", []),
                "protocol_compliance": parsed.get("protocol_compliance", False),
                "billing_readiness": parsed.get("billing_readiness", False),
                "usage": result["usage"],
            }

        except Exception as exc:
            logger.error(f"ePCR validation failed: {exc}")
            return {
                "success": False,
                "error": str(exc),
            }

    def suggest_icd10_codes(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        chief_complaint: str,
        assessment_findings: str,
        final_impression: str | None = None,
    ) -> dict[str, Any]:
        """
        Suggest ICD-10 codes based on clinical findings.

        Args:
            tenant_id: Tenant ID
            actor_id: User ID
            chief_complaint: Chief complaint
            assessment_findings: Clinical assessment
            final_impression: Provider's final impression

        Returns:
            Suggested ICD-10 codes with justifications
        """
        system_prompt = """You are an expert medical coder specializing in EMS services.
Suggest appropriate ICD-10 diagnosis codes based on the clinical presentation.

Guidelines:
- Suggest the most specific codes available
- Include both primary and secondary diagnoses
- Code to the highest level of specificity documented
- Consider signs/symptoms if definitive diagnosis not documented

Return a JSON object with:
{
  "suggested_codes": [
    {
      "code": "<ICD-10 code>",
      "description": "<code description>",
      "type": "primary" | "secondary",
      "justification": "<why this code applies>",
      "specificity_level": "specific" | "unspecified"
    }
  ],
  "documentation_needed": [<list of additional documentation for more specific coding>],
  "coding_confidence": <0-100>
}"""

        user_prompt = f"""Suggest ICD-10 codes for:

Chief Complaint: {chief_complaint}

Assessment Findings:
{assessment_findings}

{f'Final Impression: {final_impression}' if final_impression else 'Final Impression: Not documented'}
"""

        try:
            result = self.bedrock.invoke_json_task(
                module="epcr",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=1500,
                temperature=0.2,
            )

            parsed = result["parsed"]

            # Audit the suggestion
            self.audit_service.log_event(
                tenant_id=tenant_id,
                event_type="epcr_icd10_suggestion",
                actor_id=actor_id,
                resource_type="coding",
                resource_id="icd10_suggestion",
                summary=f"Suggested {len(parsed.get('suggested_codes', []))} ICD-10 codes",
                metadata={
                    "codes_suggested": len(parsed.get("suggested_codes", [])),
                    "confidence": parsed.get("coding_confidence"),
                    "model_used": result["model_id"],
                    "cost_usd": result["usage"]["cost"],
                },
            )

            return {
                "success": True,
                "suggested_codes": parsed.get("suggested_codes", []),
                "documentation_needed": parsed.get("documentation_needed", []),
                "coding_confidence": parsed.get("coding_confidence", 0),
                "requires_human_review": True,
                "usage": result["usage"],
            }

        except Exception as exc:
            logger.error(f"ICD-10 code suggestion failed: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "requires_human_review": True,
            }
