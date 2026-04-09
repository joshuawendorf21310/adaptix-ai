"""High-level AI service wrapper for Bedrock-backed narrative and analysis tasks."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_app.ai.bedrock_service import BedrockClient, get_bedrock_client
from core_app.ai.guardrails import (
    AiBillingDraftOutput,
    AiNarrativeOutput,
    contains_phi,
)
from core_app.core.config import get_settings
from core_app.models.ai import (
    AiBudgetLimit,
    AiPromptTemplate,
    AiRun,
    AiRunStatus,
    AiRunType,
)


class AiService:
    """
    Enhanced AI service with AWS Bedrock integration.

    Provides high-level AI operations for Adaptix:
    - ePCR narrative generation
    - Documentation quality checking
    - Billing risk analysis
    - Medical code suggestions
    - Appeal drafting
    - Incident classification
    - Medical necessity assessment
    - Data extraction from free text
    """

    def __init__(self, bedrock_client: BedrockClient | None = None) -> None:
        """
        Initialize AI service.

        Args:
            bedrock_client: Optional Bedrock client (for testing/DI)
        """
        self.settings = get_settings()
        if bedrock_client is None and not self.settings.enable_ai_features:
            self.bedrock_client = None
        else:
            self.bedrock_client = bedrock_client or get_bedrock_client()

    @property
    def model_name(self) -> str:
        """Return the configured Bedrock model name for downstream service metadata."""
        return self.bedrock_client.model_id if self.bedrock_client is not None else "disabled"

    async def generate_text(
        self,
        *,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.2,
        system: str | None = None,
    ) -> dict[str, Any]:
        """Async-friendly text generation wrapper over the shared Bedrock client."""
        if self.bedrock_client is None:
            raise RuntimeError("AI features are disabled")
        response = self.bedrock_client.invoke(
            prompt=prompt,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return {
            "text": response.get("content", ""),
            "model": response.get("model", self.model_name),
            "input_tokens": response.get("input_tokens", 0),
            "output_tokens": response.get("output_tokens", 0),
            "total_tokens": response.get("total_tokens", 0),
            "cost": response.get("cost", 0.0),
            "latency_ms": response.get("latency_ms", 0),
            "confidence": 0.8,
        }

    def chat(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 1000,
    ) -> tuple[str, dict[str, Any]]:
        """Compatibility chat helper for worker code that expects a simple sync interface."""
        if self.bedrock_client is None:
            raise RuntimeError("AI features are disabled")
        response = self.bedrock_client.invoke(
            prompt=user,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.get("content", "")
        meta = {
            "model": response.get("model"),
            "input_tokens": response.get("input_tokens"),
            "output_tokens": response.get("output_tokens"),
            "total_tokens": response.get("total_tokens"),
            "cost": response.get("cost"),
            "latency_ms": response.get("latency_ms"),
        }
        return content, meta

    async def _get_active_prompt_template(
        self,
        db: AsyncSession,
        run_type: AiRunType,
    ) -> AiPromptTemplate | None:
        """Get active prompt template for a run type."""
        result = await db.execute(
            select(AiPromptTemplate)
            .where(AiPromptTemplate.run_type == run_type, AiPromptTemplate.active.is_(True))
            .order_by(AiPromptTemplate.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _check_budget_limits(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        estimated_cost: Decimal,
    ) -> bool:
        """
        Check if request would exceed budget limits.

        Args:
            db: Database session
            tenant_id: Tenant ID
            estimated_cost: Estimated cost for this request

        Returns:
            True if within limits, False if would exceed
        """
        result = await db.execute(
            select(AiBudgetLimit).where(
                AiBudgetLimit.tenant_id == tenant_id,
                AiBudgetLimit.enabled.is_(True),
            )
        )
        budget = result.scalar_one_or_none()

        if not budget:
            return True  # No limits set

        # Check daily limit
        if budget.daily_limit_usd:
            if budget.current_day_spend + estimated_cost > budget.daily_limit_usd:
                return False

        # Check monthly limit
        if budget.monthly_limit_usd:
            if budget.current_month_spend + estimated_cost > budget.monthly_limit_usd:
                return False

        return True

    async def _create_ai_run(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        run_type: AiRunType,
        model_name: str,
        input_text: str,
        output_data: dict[str, Any],
        tokens_used: int,
        input_tokens: int,
        output_tokens: int,
        cost: Decimal,
        latency_ms: int,
        incident_id: uuid.UUID | None = None,
        claim_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        prompt_version: str | None = None,
        confidence_score: float | None = None,
        phi_detected: bool = False,
        hallucination_risk: str | None = None,
        guardrail_violations: list[str] | None = None,
    ) -> AiRun:
        """Create and persist an AI run record."""
        input_hash = hashlib.sha256(input_text.encode("utf-8")).hexdigest()

        ai_run = AiRun(
            tenant_id=tenant_id,
            run_type=run_type,
            model_name=model_name,
            prompt_version=prompt_version,
            input_hash=input_hash,
            output_json=output_data,
            confidence_score=confidence_score,
            tokens_used=tokens_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            status=AiRunStatus.COMPLETED,
            latency_ms=latency_ms,
            completed_at=datetime.utcnow(),
            incident_id=incident_id,
            claim_id=claim_id,
            user_id=user_id,
            phi_detected=phi_detected,
            hallucination_risk=hallucination_risk,
            guardrail_violations=guardrail_violations or [],
        )

        db.add(ai_run)
        await db.flush()
        return ai_run

    async def _update_budget_spend(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        cost: Decimal,
    ) -> None:
        """Update budget spend counters."""
        result = await db.execute(
            select(AiBudgetLimit).where(
                AiBudgetLimit.tenant_id == tenant_id,
                AiBudgetLimit.enabled.is_(True),
            )
        )
        budget = result.scalar_one_or_none()

        if budget:
            budget.current_day_spend += cost
            budget.current_month_spend += cost
            await db.flush()

    async def generate_narrative(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        clinical_data: dict[str, Any],
        user_id: uuid.UUID | None = None,
        incident_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Generate ePCR narrative from clinical data.

        Args:
            db: Database session
            tenant_id: Tenant ID
            clinical_data: Clinical data dict (chief_complaint, vitals, treatments, etc.)
            user_id: User requesting generation
            incident_id: Related incident ID

        Returns:
            Dict with:
                - narrative_text: Generated narrative
                - confidence: Confidence score
                - requires_review: Always True
                - run_id: AI run ID for auditing
        """
        # Get prompt template
        template = await self._get_active_prompt_template(db, AiRunType.NARRATIVE_GENERATION)

        if template:
            system_prompt = template.system_prompt or ""
            prompt_text = template.prompt_text.format(**clinical_data)
            model_config = template.model_config
            prompt_version = template.template_version
        else:
            # Fallback default prompt
            system_prompt = (
                "You are a medical documentation assistant for EMS. "
                "Generate a clear, chronological ePCR narrative based on the provided clinical data. "
                "Use medical terminology appropriately. Be concise but thorough. "
                "Do not include any PHI in your response."
            )
            prompt_text = f"""Generate an ePCR narrative for the following incident:

Chief Complaint: {clinical_data.get('chief_complaint', 'Not specified')}
Patient Age: {clinical_data.get('age', 'Unknown')}
Gender: {clinical_data.get('gender', 'Unknown')}

Initial Vitals:
{json.dumps(clinical_data.get('initial_vitals', {}), indent=2)}

Treatments Provided:
{json.dumps(clinical_data.get('treatments', []), indent=2)}

Assessment: {clinical_data.get('assessment', 'Not documented')}

Transport Destination: {clinical_data.get('destination', 'Not specified')}

Generate a professional narrative suitable for an electronic patient care report."""
            model_config = {"temperature": 0.3, "max_tokens": 2048}
            prompt_version = None

        # Check budget
        estimated_cost = Decimal("0.05")  # Rough estimate
        if not await self._check_budget_limits(db, tenant_id, estimated_cost):
            raise ValueError("AI budget limit exceeded for this tenant")

        # Invoke Bedrock
        start_time = time.time()
        response = self.bedrock_client.invoke(
            prompt=prompt_text,
            system=system_prompt,
            temperature=model_config.get("temperature", 0.3),
            max_tokens=model_config.get("max_tokens", 2048),
        )
        latency_ms = int((time.time() - start_time) * 1000)

        # Validate output with guardrails
        narrative = response["content"]

        # Check for PHI
        phi_detected = contains_phi(narrative)
        if phi_detected:
            raise ValueError("Generated narrative contains PHI - blocked by guardrail")

        # Validate with Pydantic model
        validated_output = AiNarrativeOutput(
            narrative_text=narrative,
            confidence=0.85,  # Could be derived from model response
            requires_review=True,
        )

        # Create AI run record
        output_data = {
            "narrative_text": validated_output.narrative_text,
            "confidence": validated_output.confidence,
            "requires_review": validated_output.requires_review,
        }

        ai_run = await self._create_ai_run(
            db=db,
            tenant_id=tenant_id,
            run_type=AiRunType.NARRATIVE_GENERATION,
            model_name=response["model"],
            input_text=prompt_text,
            output_data=output_data,
            tokens_used=response["total_tokens"],
            input_tokens=response["input_tokens"],
            output_tokens=response["output_tokens"],
            cost=Decimal(str(response["cost"])),
            latency_ms=latency_ms,
            incident_id=incident_id,
            user_id=user_id,
            prompt_version=prompt_version,
            confidence_score=validated_output.confidence,
            phi_detected=phi_detected,
        )

        # Update budget
        await self._update_budget_spend(db, tenant_id, Decimal(str(response["cost"])))

        return {
            "narrative_text": validated_output.narrative_text,
            "confidence": validated_output.confidence,
            "requires_review": validated_output.requires_review,
            "run_id": str(ai_run.id),
        }

    async def suggest_documentation_improvements(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        chart_data: dict[str, Any],
        user_id: uuid.UUID | None = None,
        incident_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Analyze chart and suggest documentation improvements.

        Args:
            db: Database session
            tenant_id: Tenant ID
            chart_data: Chart data to analyze
            user_id: User requesting analysis
            incident_id: Related incident

        Returns:
            Dict with suggestions list and completeness score
        """
        system_prompt = (
            "You are a documentation quality analyst for EMS. "
            "Review the provided chart data and identify missing or incomplete documentation. "
            "Provide specific, actionable suggestions to improve completeness and quality. "
            "Focus on regulatory compliance and billing optimization."
        )

        prompt_text = f"""Analyze this EMS chart for documentation completeness:

{json.dumps(chart_data, indent=2)}

Provide:
1. List of missing required fields
2. Incomplete sections that need more detail
3. Suggestions to improve medical necessity documentation
4. Billing optimization opportunities

Format as JSON with keys: missing_fields, incomplete_sections, suggestions, completeness_score (0-100)"""

        response = self.bedrock_client.invoke(
            prompt=prompt_text,
            system=system_prompt,
            temperature=0.2,
            max_tokens=1500,
            model_id=self.bedrock_client.get_model_for_use_case("balanced"),
        )

        # Parse JSON response
        try:
            result = json.loads(response["content"])
        except json.JSONDecodeError:
            # Fallback if model doesn't return valid JSON
            result = {
                "missing_fields": [],
                "incomplete_sections": [],
                "suggestions": [response["content"]],
                "completeness_score": 50,
            }

        output_data = {
            "missing_fields": result.get("missing_fields", []),
            "incomplete_sections": result.get("incomplete_sections", []),
            "suggestions": result.get("suggestions", []),
            "completeness_score": result.get("completeness_score", 50),
        }

        ai_run = await self._create_ai_run(
            db=db,
            tenant_id=tenant_id,
            run_type=AiRunType.DOCUMENTATION_CHECK,
            model_name=response["model"],
            input_text=prompt_text,
            output_data=output_data,
            tokens_used=response["total_tokens"],
            input_tokens=response["input_tokens"],
            output_tokens=response["output_tokens"],
            cost=Decimal(str(response["cost"])),
            latency_ms=response["latency_ms"],
            incident_id=incident_id,
            user_id=user_id,
        )

        await self._update_budget_spend(db, tenant_id, Decimal(str(response["cost"])))

        return {**output_data, "run_id": str(ai_run.id)}

    async def analyze_billing_risk(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        incident_data: dict[str, Any],
        user_id: uuid.UUID | None = None,
        incident_id: uuid.UUID | None = None,
        claim_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Analyze incident for billing denial risk.

        Args:
            db: Database session
            tenant_id: Tenant ID
            incident_data: Incident/claim data
            user_id: User requesting analysis
            incident_id: Related incident
            claim_id: Related claim

        Returns:
            Dict with risk_score, risk_factors, recommendations
        """
        system_prompt = (
            "You are a medical billing compliance analyst for EMS. "
            "Analyze the provided incident data for potential denial risks. "
            "Consider medical necessity, documentation completeness, and payer requirements. "
            "Provide a risk score (0-100) and specific risk factors."
        )

        prompt_text = f"""Analyze this EMS incident for billing denial risk:

{json.dumps(incident_data, indent=2)}

Provide:
1. risk_score (0-100, higher = more risk)
2. risk_factors (list of specific issues)
3. recommendations (list of actions to reduce risk)
4. medical_necessity_justification (brief assessment)

Return as JSON."""

        response = self.bedrock_client.invoke(
            prompt=prompt_text,
            system=system_prompt,
            temperature=0.1,  # Low temp for consistent risk assessment
            max_tokens=1500,
        )

        try:
            result = json.loads(response["content"])
        except json.JSONDecodeError:
            result = {
                "risk_score": 50,
                "risk_factors": ["Unable to parse AI response"],
                "recommendations": [],
                "medical_necessity_justification": response["content"][:500],
            }

        output_data = {
            "risk_score": result.get("risk_score", 50),
            "risk_factors": result.get("risk_factors", []),
            "recommendations": result.get("recommendations", []),
            "medical_necessity_justification": result.get("medical_necessity_justification", ""),
        }

        ai_run = await self._create_ai_run(
            db=db,
            tenant_id=tenant_id,
            run_type=AiRunType.BILLING_RISK,
            model_name=response["model"],
            input_text=prompt_text,
            output_data=output_data,
            tokens_used=response["total_tokens"],
            input_tokens=response["input_tokens"],
            output_tokens=response["output_tokens"],
            cost=Decimal(str(response["cost"])),
            latency_ms=response["latency_ms"],
            incident_id=incident_id,
            claim_id=claim_id,
            user_id=user_id,
        )

        await self._update_budget_spend(db, tenant_id, Decimal(str(response["cost"])))

        return {**output_data, "run_id": str(ai_run.id)}

    async def suggest_medical_codes(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        clinical_context: dict[str, Any],
        user_id: uuid.UUID | None = None,
        incident_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Suggest ICD-10 and CPT codes based on clinical context.

        Args:
            db: Database session
            tenant_id: Tenant ID
            clinical_context: Clinical data (chief_complaint, procedures, diagnosis, etc.)
            user_id: User requesting suggestions
            incident_id: Related incident

        Returns:
            Dict with icd10_codes, cpt_codes, confidence, reasoning
        """
        system_prompt = (
            "You are a medical coding specialist for EMS. "
            "Suggest appropriate ICD-10 diagnosis codes and CPT procedure codes "
            "based on the provided clinical context. Include brief reasoning for each code. "
            "Prioritize accuracy over quantity. "
            "Format response as JSON."
        )

        prompt_text = f"""Suggest medical codes for this EMS incident:

{json.dumps(clinical_context, indent=2)}

Provide:
1. icd10_codes: List of dicts with code, description, reasoning
2. cpt_codes: List of dicts with code, description, reasoning
3. primary_diagnosis_code: Most appropriate primary ICD-10
4. confidence_level: overall confidence (low/medium/high)

Return as JSON."""

        response = self.bedrock_client.invoke(
            prompt=prompt_text,
            system=system_prompt,
            temperature=0.2,
            max_tokens=2000,
        )

        try:
            result = json.loads(response["content"])
        except json.JSONDecodeError:
            result = {
                "icd10_codes": [],
                "cpt_codes": [],
                "primary_diagnosis_code": None,
                "confidence_level": "low",
            }

        output_data = {
            "icd10_codes": result.get("icd10_codes", []),
            "cpt_codes": result.get("cpt_codes", []),
            "primary_diagnosis_code": result.get("primary_diagnosis_code"),
            "confidence_level": result.get("confidence_level", "low"),
        }

        ai_run = await self._create_ai_run(
            db=db,
            tenant_id=tenant_id,
            run_type=AiRunType.CODE_SUGGESTION,
            model_name=response["model"],
            input_text=prompt_text,
            output_data=output_data,
            tokens_used=response["total_tokens"],
            input_tokens=response["input_tokens"],
            output_tokens=response["output_tokens"],
            cost=Decimal(str(response["cost"])),
            latency_ms=response["latency_ms"],
            incident_id=incident_id,
            user_id=user_id,
        )

        await self._update_budget_spend(db, tenant_id, Decimal(str(response["cost"])))

        return {**output_data, "run_id": str(ai_run.id)}

    async def classify_incident_type(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        dispatch_data: dict[str, Any],
        user_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Classify incident type from dispatch data.

        Args:
            db: Database session
            tenant_id: Tenant ID
            dispatch_data: Dispatch info (call_type, notes, location, etc.)
            user_id: User requesting classification

        Returns:
            Dict with incident_type, confidence, reasoning
        """
        system_prompt = (
            "You are an EMS dispatch classifier. "
            "Analyze dispatch information and classify the incident type. "
            "Use standard NEMSIS incident types when possible."
        )

        prompt_text = f"""Classify this EMS incident:

{json.dumps(dispatch_data, indent=2)}

Provide:
1. incident_type: Primary classification (e.g., 'Medical', 'Trauma', 'Cardiac', 'Respiratory')
2. sub_type: More specific classification
3. acuity_level: Estimated acuity (Critical, High, Medium, Low)
4. confidence: 0.0-1.0
5. reasoning: Brief explanation

Return as JSON."""

        response = self.bedrock_client.invoke(
            prompt=prompt_text,
            system=system_prompt,
            temperature=0.1,
            max_tokens=800,
            model_id=self.bedrock_client.get_model_for_use_case("fast"),
        )

        try:
            result = json.loads(response["content"])
        except json.JSONDecodeError:
            result = {
                "incident_type": "Unknown",
                "sub_type": None,
                "acuity_level": "Medium",
                "confidence": 0.5,
                "reasoning": response["content"],
            }

        output_data = {
            "incident_type": result.get("incident_type", "Unknown"),
            "sub_type": result.get("sub_type"),
            "acuity_level": result.get("acuity_level", "Medium"),
            "confidence": result.get("confidence", 0.5),
            "reasoning": result.get("reasoning", ""),
        }

        ai_run = await self._create_ai_run(
            db=db,
            tenant_id=tenant_id,
            run_type=AiRunType.INCIDENT_CLASSIFICATION,
            model_name=response["model"],
            input_text=prompt_text,
            output_data=output_data,
            tokens_used=response["total_tokens"],
            input_tokens=response["input_tokens"],
            output_tokens=response["output_tokens"],
            cost=Decimal(str(response["cost"])),
            latency_ms=response["latency_ms"],
            user_id=user_id,
        )

        await self._update_budget_spend(db, tenant_id, Decimal(str(response["cost"])))

        return {**output_data, "run_id": str(ai_run.id)}

    async def extract_structured_data(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        narrative_text: str,
        user_id: uuid.UUID | None = None,
        incident_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Extract structured data from free-text narrative.

        Args:
            db: Database session
            tenant_id: Tenant ID
            narrative_text: Free-text narrative
            user_id: User requesting extraction
            incident_id: Related incident

        Returns:
            Dict with extracted structured fields
        """
        system_prompt = (
            "You are a medical data extraction specialist. "
            "Extract structured information from the provided EMS narrative. "
            "Return data as JSON with standard medical fields."
        )

        prompt_text = f"""Extract structured data from this EMS narrative:

{narrative_text}

Extract:
1. chief_complaint
2. vitals (dict with BP, HR, RR, SpO2, temp, glucose if mentioned)
3. medications_administered (list)
4. procedures_performed (list)
5. patient_history (list of relevant history)
6. disposition
7. transport_destination

Return as JSON. Use null for missing data."""

        response = self.bedrock_client.invoke(
            prompt=prompt_text,
            system=system_prompt,
            temperature=0.1,
            max_tokens=1500,
        )

        try:
            result = json.loads(response["content"])
        except json.JSONDecodeError:
            result = {"error": "Failed to parse AI response", "raw_response": response["content"]}

        output_data = result

        ai_run = await self._create_ai_run(
            db=db,
            tenant_id=tenant_id,
            run_type=AiRunType.EXTRACTION,
            model_name=response["model"],
            input_text=prompt_text,
            output_data=output_data,
            tokens_used=response["total_tokens"],
            input_tokens=response["input_tokens"],
            output_tokens=response["output_tokens"],
            cost=Decimal(str(response["cost"])),
            latency_ms=response["latency_ms"],
            incident_id=incident_id,
            user_id=user_id,
        )

        await self._update_budget_spend(db, tenant_id, Decimal(str(response["cost"])))

        return {**output_data, "run_id": str(ai_run.id)}

    async def summarize_incident(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        incident_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Generate executive summary of an incident.

        Args:
            db: Database session
            tenant_id: Tenant ID
            incident_id: Incident to summarize
            user_id: User requesting summary

        Returns:
            Dict with summary, key_points, outcome
        """
        # Fetch actual incident data from database
        from core_app.models.incident import Incident

        stmt = select(Incident).where(Incident.id == incident_id)
        result = await db.execute(stmt)
        incident = result.scalar_one_or_none()

        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        # Build incident data dict with available fields
        incident_data = {
            "id": str(incident.id),
            "incident_number": incident.incident_number,
            "status": incident.status,
            "dispatch_time": incident.dispatch_time.isoformat() if incident.dispatch_time else None,
            "primary_impression": incident.primary_impression,
            "disposition": incident.disposition,
        }

        system_prompt = (
            "You are an EMS operations analyst. "
            "Create a concise executive summary of the incident. "
            "Focus on key clinical findings, interventions, and outcome. "
            "Target audience is supervisors and QA reviewers."
        )

        prompt_text = f"""Create an executive summary of this EMS incident:

{json.dumps(incident_data, indent=2)}

Provide:
1. summary: 2-3 sentence overview
2. key_points: List of 3-5 most important facts
3. outcome: Patient outcome/disposition
4. notable_items: Any QA issues or exceptional care

Return as JSON."""

        response = self.bedrock_client.invoke(
            prompt=prompt_text,
            system=system_prompt,
            temperature=0.3,
            max_tokens=1000,
        )

        try:
            result = json.loads(response["content"])
        except json.JSONDecodeError:
            result = {"summary": response["content"], "key_points": [], "outcome": "", "notable_items": []}

        output_data = result

        ai_run = await self._create_ai_run(
            db=db,
            tenant_id=tenant_id,
            run_type=AiRunType.SUMMARIZATION,
            model_name=response["model"],
            input_text=prompt_text,
            output_data=output_data,
            tokens_used=response["total_tokens"],
            input_tokens=response["input_tokens"],
            output_tokens=response["output_tokens"],
            cost=Decimal(str(response["cost"])),
            latency_ms=response["latency_ms"],
            incident_id=incident_id,
            user_id=user_id,
        )

        await self._update_budget_spend(db, tenant_id, Decimal(str(response["cost"])))

        return {**output_data, "run_id": str(ai_run.id)}

    async def generate_appeal_draft(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        denial_data: dict[str, Any],
        user_id: uuid.UUID | None = None,
        claim_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Generate appeal letter draft for denied claim.

        Args:
            db: Database session
            tenant_id: Tenant ID
            denial_data: Denial reason and claim details
            user_id: User requesting draft
            claim_id: Related claim

        Returns:
            Dict with draft_text, key_arguments, estimated_success_rate
        """
        system_prompt = (
            "You are a medical billing appeals specialist for EMS. "
            "Draft a professional appeal letter for a denied claim. "
            "Use regulatory citations and medical necessity arguments. "
            "DO NOT include any PHI - use placeholder references like '[Patient Name]' and '[Date of Service]'. "
            "The letter should be a template that staff will customize with actual patient data."
        )

        prompt_text = f"""Draft an appeal letter for this denied EMS claim:

Denial Reason: {denial_data.get('denial_reason', 'Not specified')}
Service Provided: {denial_data.get('service_type', 'Emergency ambulance transport')}
Documentation Available: {json.dumps(denial_data.get('available_documentation', []), indent=2)}

Create a professional appeal letter that:
1. Addresses the denial reason specifically
2. Cites relevant medical necessity criteria
3. References appropriate regulations (LCD/NCD)
4. Uses placeholder fields for PHI
5. Is ready for human review and finalization

Format as JSON with keys: draft_text, key_arguments (list), supporting_documentation_needed (list), estimated_success_rate (low/medium/high)"""

        response = self.bedrock_client.invoke(
            prompt=prompt_text,
            system=system_prompt,
            temperature=0.4,
            max_tokens=3000,
        )

        try:
            result = json.loads(response["content"])
        except json.JSONDecodeError:
            result = {
                "draft_text": response["content"],
                "key_arguments": [],
                "supporting_documentation_needed": [],
                "estimated_success_rate": "medium",
            }

        # Validate with guardrails
        validated = AiBillingDraftOutput(
            draft_text=result.get("draft_text", ""),
            requires_human_review=True,
        )

        output_data = {
            "draft_text": validated.draft_text,
            "key_arguments": result.get("key_arguments", []),
            "supporting_documentation_needed": result.get("supporting_documentation_needed", []),
            "estimated_success_rate": result.get("estimated_success_rate", "medium"),
            "requires_human_review": validated.requires_human_review,
        }

        ai_run = await self._create_ai_run(
            db=db,
            tenant_id=tenant_id,
            run_type=AiRunType.APPEAL_DRAFT,
            model_name=response["model"],
            input_text=prompt_text,
            output_data=output_data,
            tokens_used=response["total_tokens"],
            input_tokens=response["input_tokens"],
            output_tokens=response["output_tokens"],
            cost=Decimal(str(response["cost"])),
            latency_ms=response["latency_ms"],
            claim_id=claim_id,
            user_id=user_id,
        )

        await self._update_budget_spend(db, tenant_id, Decimal(str(response["cost"])))

        return {**output_data, "run_id": str(ai_run.id)}

    async def detect_documentation_contradictions(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        chart_data: dict[str, Any],
        user_id: uuid.UUID | None = None,
        incident_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Detect contradictions and inconsistencies in chart documentation.

        Args:
            db: Database session
            tenant_id: Tenant ID
            chart_data: Full chart data
            user_id: User requesting check
            incident_id: Related incident

        Returns:
            Dict with contradictions list and severity levels
        """
        system_prompt = (
            "You are a medical documentation QA analyst. "
            "Identify contradictions, inconsistencies, and logical errors in the provided chart. "
            "Focus on medical accuracy and internal consistency."
        )

        prompt_text = f"""Analyze this EMS chart for contradictions:

{json.dumps(chart_data, indent=2)}

Identify:
1. Direct contradictions (e.g., narrative says conscious, but GCS is 3)
2. Timeline inconsistencies
3. Vital sign trends that don't match narrative
4. Treatment contradictions (e.g., medication given but allergy documented)

For each issue provide:
- description
- severity (critical/high/medium/low)
- affected_fields
- suggested_resolution

Return as JSON with key: contradictions (list of dicts)"""

        response = self.bedrock_client.invoke(
            prompt=prompt_text,
            system=system_prompt,
            temperature=0.1,
            max_tokens=2000,
        )

        try:
            result = json.loads(response["content"])
        except json.JSONDecodeError:
            result = {"contradictions": []}

        output_data = {
            "contradictions": result.get("contradictions", []),
            "total_issues": len(result.get("contradictions", [])),
            "critical_count": sum(
                1 for c in result.get("contradictions", []) if c.get("severity") == "critical"
            ),
        }

        ai_run = await self._create_ai_run(
            db=db,
            tenant_id=tenant_id,
            run_type=AiRunType.CONTRADICTION_DETECTION,
            model_name=response["model"],
            input_text=prompt_text,
            output_data=output_data,
            tokens_used=response["total_tokens"],
            input_tokens=response["input_tokens"],
            output_tokens=response["output_tokens"],
            cost=Decimal(str(response["cost"])),
            latency_ms=response["latency_ms"],
            incident_id=incident_id,
            user_id=user_id,
        )

        await self._update_budget_spend(db, tenant_id, Decimal(str(response["cost"])))

        return {**output_data, "run_id": str(ai_run.id)}


def hash_input(text: str) -> str:
    """Generate SHA256 hash of input text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
