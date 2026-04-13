"""Billing intelligence API router."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Any
from uuid import UUID

from core_app.api.dependencies import get_db, get_current_user
from core_app.services.billing_intelligence_service import BillingIntelligenceService

router = APIRouter(prefix="/api/v1/billing-intelligence", tags=["billing-intelligence"])


class ClaimReadinessRequest(BaseModel):
    """Request to score claim readiness."""
    claim_data: dict[str, Any] = Field(..., description="Complete claim data")


class DenialRiskRequest(BaseModel):
    """Request to assess denial risk."""
    claim_data: dict[str, Any] = Field(..., description="Complete claim data")
    payer_type: str | None = Field(None, description="Payer type (Medicare, Medicaid, Commercial)")


class MedicalNecessityRequest(BaseModel):
    """Request to generate medical necessity summary."""
    patient_data: dict[str, Any] = Field(..., description="Patient clinical data")
    transport_data: dict[str, Any] = Field(..., description="Transport data")


class DocumentationCompletenessRequest(BaseModel):
    """Request to analyze documentation completeness."""
    pcr_data: dict[str, Any] = Field(..., description="PCR documentation data")


class CodingImprovementRequest(BaseModel):
    """Request for coding improvement suggestions."""
    diagnosis_codes: list[str] = Field(..., description="Current ICD-10 diagnosis codes")
    procedure_codes: list[str] = Field(..., description="Current CPT procedure codes")
    clinical_narrative: str = Field(..., description="Clinical narrative from PCR")


@router.post("/claim-readiness")
def score_claim_readiness(
    request: ClaimReadinessRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Score a claim for billing readiness."""
    service = BillingIntelligenceService(db)
    tenant_id = UUID(current_user["tenant_id"])
    user_id = UUID(current_user["user_id"])

    result = service.score_claim_readiness(
        tenant_id=tenant_id,
        actor_id=user_id,
        claim_data=request.claim_data,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Assessment failed"))

    return result


@router.post("/denial-risk")
def assess_denial_risk(
    request: DenialRiskRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Assess denial risk for a claim."""
    service = BillingIntelligenceService(db)
    tenant_id = UUID(current_user["tenant_id"])
    user_id = UUID(current_user["user_id"])

    result = service.assess_denial_risk(
        tenant_id=tenant_id,
        actor_id=user_id,
        claim_data=request.claim_data,
        payer_type=request.payer_type,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Assessment failed"))

    return result


@router.post("/medical-necessity")
def generate_medical_necessity(
    request: MedicalNecessityRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Generate medical necessity justification summary."""
    service = BillingIntelligenceService(db)
    tenant_id = UUID(current_user["tenant_id"])
    user_id = UUID(current_user["user_id"])

    result = service.generate_medical_necessity_summary(
        tenant_id=tenant_id,
        actor_id=user_id,
        patient_data=request.patient_data,
        transport_data=request.transport_data,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Generation failed"))

    return result


@router.post("/documentation-completeness")
def analyze_documentation_completeness(
    request: DocumentationCompletenessRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Analyze PCR documentation completeness for billing."""
    service = BillingIntelligenceService(db)
    tenant_id = UUID(current_user["tenant_id"])
    user_id = UUID(current_user["user_id"])

    result = service.analyze_documentation_completeness(
        tenant_id=tenant_id,
        actor_id=user_id,
        pcr_data=request.pcr_data,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Analysis failed"))

    return result


@router.post("/coding-improvements")
def suggest_coding_improvements(
    request: CodingImprovementRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Suggest ICD-10 and CPT coding improvements."""
    service = BillingIntelligenceService(db)
    tenant_id = UUID(current_user["tenant_id"])
    user_id = UUID(current_user["user_id"])

    result = service.suggest_coding_improvements(
        tenant_id=tenant_id,
        actor_id=user_id,
        diagnosis_codes=request.diagnosis_codes,
        procedure_codes=request.procedure_codes,
        clinical_narrative=request.clinical_narrative,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Suggestion failed"))

    return result
