"""Billing intelligence service for claim readiness, denial risk, and medical necessity."""
from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core_app.ai.bedrock_service import BedrockClient
from core_app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class BillingIntelligenceService:
    """
    AI-powered billing intelligence for EMS operations.

    Features:
    - Claim readiness scoring
    - Denial risk flags
    - Documentation completeness hints
    - Medical necessity summaries
    - Payer rule explanations
    - Coding support summaries
    - Charge capture assistance
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.bedrock = BedrockClient()
        self.audit_service = AuditService(db)

    def score_claim_readiness(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        claim_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Score a claim for billing readiness.

        Returns:
            Readiness score (0-100) with specific issues identified
        """
        system_prompt = """You are a medical billing compliance expert for EMS services.
Analyze the provided claim data and assess billing readiness.

Return a JSON object with:
{
  "readiness_score": <0-100>,
  "status": "ready" | "needs_review" | "not_ready",
  "missing_required_fields": [<list of missing required fields>],
  "documentation_gaps": [<list of documentation issues>],
  "compliance_warnings": [<list of compliance concerns>],
  "recommendations": [<list of actions to improve readiness>]
}"""

        user_prompt = f"""Assess claim readiness for:

Patient Age: {claim_data.get('patient_age', 'Unknown')}
Service Date: {claim_data.get('service_date', 'Unknown')}
Transport Type: {claim_data.get('transport_type', 'Unknown')}
Chief Complaint: {claim_data.get('chief_complaint', 'Unknown')}
Diagnosis Codes: {', '.join(claim_data.get('diagnosis_codes', []))}
Procedure Codes: {', '.join(claim_data.get('procedure_codes', []))}
Mileage: {claim_data.get('mileage', 'Unknown')}
Origin: {claim_data.get('origin', 'Unknown')}
Destination: {claim_data.get('destination', 'Unknown')}
Medical Necessity Documented: {claim_data.get('necessity_documented', False)}
Physician Signature: {claim_data.get('physician_signature', False)}
Patient Signature: {claim_data.get('patient_signature', False)}
"""

        try:
            result = self.bedrock.invoke_json_task(
                module="billing",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=2000,
                temperature=0.2,
            )

            parsed = result["parsed"]

            # Audit the assessment
            self.audit_service.log_event(
                tenant_id=tenant_id,
                event_type="billing_readiness_assessment",
                actor_id=actor_id,
                resource_type="claim",
                resource_id=str(claim_data.get("claim_id", "unknown")),
                summary=f"Claim readiness scored: {parsed.get('readiness_score', 0)}/100",
                metadata={
                    "readiness_score": parsed.get("readiness_score"),
                    "status": parsed.get("status"),
                    "model_used": result["model_id"],
                    "cost_usd": result["usage"]["cost"],
                },
            )

            return {
                "success": True,
                "readiness_score": parsed.get("readiness_score", 0),
                "status": parsed.get("status", "unknown"),
                "missing_required_fields": parsed.get("missing_required_fields", []),
                "documentation_gaps": parsed.get("documentation_gaps", []),
                "compliance_warnings": parsed.get("compliance_warnings", []),
                "recommendations": parsed.get("recommendations", []),
                "usage": result["usage"],
            }

        except Exception as exc:
            logger.error(f"Claim readiness scoring failed: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "readiness_score": 0,
                "status": "error",
            }

    def assess_denial_risk(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        claim_data: dict[str, Any],
        payer_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Assess denial risk for a claim.

        Returns:
            Risk score with specific denial triggers
        """
        system_prompt = """You are a medical billing denial prevention expert for EMS.
Analyze the claim for potential denial risks.

Return a JSON object with:
{
  "denial_risk_score": <0-100, where 100 is highest risk>,
  "risk_level": "low" | "medium" | "high" | "critical",
  "denial_triggers": [<list of specific issues that could trigger denial>],
  "payer_specific_concerns": [<list of payer-specific issues>],
  "medical_necessity_concerns": [<list of medical necessity gaps>],
  "documentation_deficiencies": [<list of documentation issues>],
  "mitigation_actions": [<list of actions to reduce denial risk>]
}"""

        payer_info = f"Payer Type: {payer_type}" if payer_type else "Payer Type: Unknown"

        user_prompt = f"""Assess denial risk for:

{payer_info}
Transport Type: {claim_data.get('transport_type', 'Unknown')}
Level of Service: {claim_data.get('level_of_service', 'Unknown')}
Chief Complaint: {claim_data.get('chief_complaint', 'Unknown')}
Diagnosis Codes: {', '.join(claim_data.get('diagnosis_codes', []))}
Procedure Codes: {', '.join(claim_data.get('procedure_codes', []))}
Medical Necessity: {claim_data.get('medical_necessity_narrative', 'Not documented')}
Prior Authorization: {claim_data.get('prior_auth', 'None')}
Transport Destination: {claim_data.get('destination_type', 'Unknown')}
Mileage: {claim_data.get('mileage', 'Unknown')}
"""

        try:
            result = self.bedrock.invoke_json_task(
                module="billing",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=2000,
                temperature=0.2,
            )

            parsed = result["parsed"]

            # Audit the assessment
            self.audit_service.log_event(
                tenant_id=tenant_id,
                event_type="denial_risk_assessment",
                actor_id=actor_id,
                resource_type="claim",
                resource_id=str(claim_data.get("claim_id", "unknown")),
                summary=f"Denial risk assessed: {parsed.get('risk_level', 'unknown')} ({parsed.get('denial_risk_score', 0)})",
                metadata={
                    "denial_risk_score": parsed.get("denial_risk_score"),
                    "risk_level": parsed.get("risk_level"),
                    "model_used": result["model_id"],
                    "cost_usd": result["usage"]["cost"],
                },
            )

            return {
                "success": True,
                "denial_risk_score": parsed.get("denial_risk_score", 0),
                "risk_level": parsed.get("risk_level", "unknown"),
                "denial_triggers": parsed.get("denial_triggers", []),
                "payer_specific_concerns": parsed.get("payer_specific_concerns", []),
                "medical_necessity_concerns": parsed.get("medical_necessity_concerns", []),
                "documentation_deficiencies": parsed.get("documentation_deficiencies", []),
                "mitigation_actions": parsed.get("mitigation_actions", []),
                "usage": result["usage"],
            }

        except Exception as exc:
            logger.error(f"Denial risk assessment failed: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "denial_risk_score": 100,  # Assume high risk on error
                "risk_level": "error",
            }

    def generate_medical_necessity_summary(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        patient_data: dict[str, Any],
        transport_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate medical necessity justification summary.

        Returns:
            Structured medical necessity narrative
        """
        system_prompt = """You are an EMS medical necessity documentation expert.
Generate a clear, concise medical necessity justification for ambulance transport.

Return a JSON object with:
{
  "necessity_summary": "<2-3 sentence summary>",
  "key_clinical_factors": [<list of clinical factors supporting necessity>],
  "transport_justification": "<why ambulance was medically necessary>",
  "alternative_transport_considered": "<why alternatives were not suitable>",
  "suggested_narrative": "<complete necessity narrative for documentation>"
}"""

        user_prompt = f"""Generate medical necessity justification for:

Patient Age: {patient_data.get('age', 'Unknown')}
Chief Complaint: {patient_data.get('chief_complaint', 'Unknown')}
Vital Signs: HR {patient_data.get('heart_rate', '?')}, BP {patient_data.get('blood_pressure', '?')}, SpO2 {patient_data.get('spo2', '?')}%
Level of Consciousness: {patient_data.get('loc', 'Unknown')}
Mobility Status: {patient_data.get('mobility', 'Unknown')}
Interventions Provided: {', '.join(patient_data.get('interventions', []))}
Transport Type: {transport_data.get('transport_type', 'Unknown')}
Transport Distance: {transport_data.get('mileage', 'Unknown')} miles
Origin: {transport_data.get('origin', 'Unknown')}
Destination: {transport_data.get('destination', 'Unknown')}
"""

        try:
            result = self.bedrock.invoke_json_task(
                module="billing",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=1500,
                temperature=0.3,
            )

            parsed = result["parsed"]

            # Audit the generation
            self.audit_service.log_event(
                tenant_id=tenant_id,
                event_type="medical_necessity_generation",
                actor_id=actor_id,
                resource_type="transport",
                resource_id=str(transport_data.get("transport_id", "unknown")),
                summary="Medical necessity summary generated",
                metadata={
                    "model_used": result["model_id"],
                    "cost_usd": result["usage"]["cost"],
                },
            )

            return {
                "success": True,
                "necessity_summary": parsed.get("necessity_summary", ""),
                "key_clinical_factors": parsed.get("key_clinical_factors", []),
                "transport_justification": parsed.get("transport_justification", ""),
                "alternative_transport_considered": parsed.get("alternative_transport_considered", ""),
                "suggested_narrative": parsed.get("suggested_narrative", ""),
                "requires_human_review": True,  # Always require review for billing documentation
                "usage": result["usage"],
            }

        except Exception as exc:
            logger.error(f"Medical necessity generation failed: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "requires_human_review": True,
            }

    def analyze_documentation_completeness(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        pcr_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Analyze PCR documentation completeness for billing.

        Returns:
            Completeness score with gaps identified
        """
        system_prompt = """You are an EMS documentation compliance expert.
Analyze the PCR for billing documentation completeness.

Return a JSON object with:
{
  "completeness_score": <0-100>,
  "status": "complete" | "incomplete" | "critical_gaps",
  "missing_elements": [<list of missing documentation>],
  "weak_elements": [<list of weak or unclear documentation>],
  "signatures_needed": [<list of required signatures missing>],
  "recommendations": [<list of documentation improvements>]
}"""

        user_prompt = f"""Analyze documentation completeness:

Chief Complaint Documented: {bool(pcr_data.get('chief_complaint'))}
History Present Illness: {bool(pcr_data.get('hpi'))}
Physical Exam: {bool(pcr_data.get('physical_exam'))}
Vital Signs: {bool(pcr_data.get('vital_signs'))}
Treatments/Interventions: {bool(pcr_data.get('treatments'))}
Patient Response to Treatment: {bool(pcr_data.get('response_to_treatment'))}
Transport Decision Rationale: {bool(pcr_data.get('transport_rationale'))}
Medical Necessity Statement: {bool(pcr_data.get('medical_necessity'))}
Destination Choice Justification: {bool(pcr_data.get('destination_justification'))}
Patient Signature: {pcr_data.get('patient_signature', False)}
Crew Signature: {pcr_data.get('crew_signature', False)}
Times Documented (dispatch/enroute/arrival/etc): {bool(pcr_data.get('times_complete'))}
"""

        try:
            result = self.bedrock.invoke_json_task(
                module="billing",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=1500,
                temperature=0.2,
            )

            parsed = result["parsed"]

            # Audit the analysis
            self.audit_service.log_event(
                tenant_id=tenant_id,
                event_type="documentation_completeness_analysis",
                actor_id=actor_id,
                resource_type="pcr",
                resource_id=str(pcr_data.get("pcr_id", "unknown")),
                summary=f"Documentation completeness: {parsed.get('completeness_score', 0)}%",
                metadata={
                    "completeness_score": parsed.get("completeness_score"),
                    "status": parsed.get("status"),
                    "model_used": result["model_id"],
                    "cost_usd": result["usage"]["cost"],
                },
            )

            return {
                "success": True,
                "completeness_score": parsed.get("completeness_score", 0),
                "status": parsed.get("status", "unknown"),
                "missing_elements": parsed.get("missing_elements", []),
                "weak_elements": parsed.get("weak_elements", []),
                "signatures_needed": parsed.get("signatures_needed", []),
                "recommendations": parsed.get("recommendations", []),
                "usage": result["usage"],
            }

        except Exception as exc:
            logger.error(f"Documentation completeness analysis failed: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "completeness_score": 0,
            }

    def suggest_coding_improvements(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        diagnosis_codes: list[str],
        procedure_codes: list[str],
        clinical_narrative: str,
    ) -> dict[str, Any]:
        """
        Suggest ICD-10 and CPT coding improvements.

        Returns:
            Coding recommendations and alternatives
        """
        system_prompt = """You are a medical coding expert for EMS services.
Review the provided codes and clinical narrative for coding accuracy.

Return a JSON object with:
{
  "coding_accuracy_score": <0-100>,
  "diagnosis_code_issues": [<list of ICD-10 issues>],
  "procedure_code_issues": [<list of CPT issues>],
  "suggested_alternative_codes": [{"current": "...", "suggested": "...", "reason": "..."}],
  "specificity_improvements": [<list of ways to increase coding specificity>],
  "documentation_needed": [<list of additional documentation for better coding>]
}"""

        user_prompt = f"""Review coding:

Current Diagnosis Codes: {', '.join(diagnosis_codes)}
Current Procedure Codes: {', '.join(procedure_codes)}

Clinical Narrative:
{clinical_narrative[:1000]}
"""

        try:
            result = self.bedrock.invoke_json_task(
                module="billing",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=2000,
                temperature=0.2,
            )

            parsed = result["parsed"]

            # Audit the suggestion
            self.audit_service.log_event(
                tenant_id=tenant_id,
                event_type="coding_improvement_suggestion",
                actor_id=actor_id,
                resource_type="codes",
                resource_id="coding_analysis",
                summary=f"Coding accuracy: {parsed.get('coding_accuracy_score', 0)}%",
                metadata={
                    "coding_accuracy_score": parsed.get("coding_accuracy_score"),
                    "model_used": result["model_id"],
                    "cost_usd": result["usage"]["cost"],
                },
            )

            return {
                "success": True,
                "coding_accuracy_score": parsed.get("coding_accuracy_score", 0),
                "diagnosis_code_issues": parsed.get("diagnosis_code_issues", []),
                "procedure_code_issues": parsed.get("procedure_code_issues", []),
                "suggested_alternative_codes": parsed.get("suggested_alternative_codes", []),
                "specificity_improvements": parsed.get("specificity_improvements", []),
                "documentation_needed": parsed.get("documentation_needed", []),
                "requires_human_review": True,  # Always require review for coding changes
                "usage": result["usage"],
            }

        except Exception as exc:
            logger.error(f"Coding improvement suggestion failed: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "requires_human_review": True,
            }
