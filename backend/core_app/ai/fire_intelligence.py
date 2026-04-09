"""
Fire Intelligence AI Service for Adaptix.

Provides AI-powered classification, validation, and analysis for Fire RMS operations:
- Incident classification from structured inputs
- NERIS field validation and completeness scoring
- Narrative assistance and contradiction detection
- Property duplicate detection and occupancy classification
- Preplan update recommendations
- Inspection finding suggestions
- Permission conflict detection
- Access pattern analysis

All AI outputs are marked as system-generated and fully auditable.
Production-ready with comprehensive error handling and guardrails.
"""
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
from core_app.ai.guardrails import contains_phi
from core_app.core.config import get_settings
from core_app.models.ai import (
    AiBudgetLimit,
    AiRun,
    AiRunStatus,
    AiRunType,
)
from core_app.models.fire import (
    FireIncidentType,
)


class FireIntelligenceService:
    """
    AI service for Fire RMS operations with AWS Bedrock integration.

    Provides intelligent classification, validation, and recommendations
    for fire incidents, inspections, preplans, and compliance operations.
    """

    def __init__(self, bedrock_client: BedrockClient | None = None) -> None:
        """
        Initialize Fire Intelligence service.

        Args:
            bedrock_client: Optional Bedrock client (for testing/DI)
        """
        self.bedrock_client = bedrock_client or get_bedrock_client()
        self.settings = get_settings()

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
                AiBudgetLimit.enabled == True,
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
        fire_incident_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        prompt_version: str | None = None,
        confidence_score: float | None = None,
        phi_detected: bool = False,
        hallucination_risk: str | None = None,
        guardrail_violations: list[str] | None = None,
    ) -> AiRun:
        """Create and persist an AI run record for fire operations."""
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
            incident_id=fire_incident_id,  # Maps to generic incident_id field
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
                AiBudgetLimit.enabled == True,
            )
        )
        budget = result.scalar_one_or_none()

        if budget:
            budget.current_day_spend += cost
            budget.current_month_spend += cost
            await db.flush()

    async def classify_fire_incident(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        incident_data: dict[str, Any],
        user_id: uuid.UUID | None = None,
        fire_incident_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Classify fire incident from structured dispatch/initial data.

        Uses AWS Bedrock Claude to analyze dispatch information and classify
        the incident according to NERIS standards.

        Args:
            db: Database session
            tenant_id: Tenant ID
            incident_data: Structured incident data (dispatch notes, location, initial reports)
            user_id: User requesting classification
            fire_incident_id: Related fire incident ID

        Returns:
            Dict with:
                - incident_type: NERIS-compatible incident classification
                - confidence: Classification confidence (0.0-1.0)
                - reasoning: Explanation for classification
                - suggested_actions: Recommended initial actions
                - alarm_level_recommendation: Suggested alarm level
                - ai_generated: True
                - requires_review: True
                - run_id: AI run ID for auditing
        """
        system_prompt = (
            "You are a fire incident classification expert. "
            "Analyze dispatch and initial incident data to classify fire incidents "
            "according to NERIS (National Emergency Response Information System) standards. "
            "Consider incident type, severity, required resources, and hazards. "
            "Provide clear reasoning and actionable recommendations."
        )

        prompt_text = f"""Classify this fire incident based on the following information:

{json.dumps(incident_data, indent=2)}

Analyze and provide:
1. incident_type: Primary classification (structure_fire, vehicle_fire, wildland_fire, medical_assist, hazmat, rescue, service_call, false_alarm, other)
2. sub_classification: More specific type (e.g., "residential_structure", "commercial_structure", "single_vehicle", "multi-vehicle")
3. alarm_level_recommendation: Suggested alarm level (1-5) based on severity and resources needed
4. confidence: Your confidence in this classification (0.0-1.0)
5. reasoning: Clear explanation for your classification
6. suggested_actions: List of recommended initial actions (e.g., "Request hazmat team", "Establish defensive positions")
7. hazard_assessment: List of potential hazards identified
8. resource_requirements: Estimated apparatus and personnel needed

Return as valid JSON."""

        # Check budget
        estimated_cost = Decimal("0.03")  # Rough estimate
        if not await self._check_budget_limits(db, tenant_id, estimated_cost):
            raise ValueError("AI budget limit exceeded for this tenant")

        # Invoke Bedrock
        start_time = time.time()
        response = self.bedrock_client.invoke(
            prompt=prompt_text,
            system=system_prompt,
            temperature=0.2,  # Low temperature for consistent classification
            max_tokens=1500,
            model_id=self.bedrock_client.get_model_for_use_case("balanced"),
        )
        latency_ms = int((time.time() - start_time) * 1000)

        # Parse JSON response
        try:
            result = json.loads(response["content"])
        except json.JSONDecodeError:
            result = {
                "incident_type": "other",
                "sub_classification": "unknown",
                "alarm_level_recommendation": 1,
                "confidence": 0.3,
                "reasoning": "Unable to parse AI response",
                "suggested_actions": [],
                "hazard_assessment": [],
                "resource_requirements": {},
            }

        # Validate incident_type against enum
        valid_types = [t.value for t in FireIncidentType]
        if result.get("incident_type") not in valid_types:
            result["incident_type"] = "other"

        output_data = {
            "incident_type": result.get("incident_type", "other"),
            "sub_classification": result.get("sub_classification", "unknown"),
            "alarm_level_recommendation": result.get("alarm_level_recommendation", 1),
            "confidence": result.get("confidence", 0.5),
            "reasoning": result.get("reasoning", ""),
            "suggested_actions": result.get("suggested_actions", []),
            "hazard_assessment": result.get("hazard_assessment", []),
            "resource_requirements": result.get("resource_requirements", {}),
            "ai_generated": True,
            "requires_review": True,
            "generated_at": datetime.utcnow().isoformat(),
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
            latency_ms=latency_ms,
            fire_incident_id=fire_incident_id,
            user_id=user_id,
            confidence_score=output_data["confidence"],
        )

        await self._update_budget_spend(db, tenant_id, Decimal(str(response["cost"])))

        return {**output_data, "run_id": str(ai_run.id)}

    async def validate_neris_completeness(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        neris_data: dict[str, Any],
        user_id: uuid.UUID | None = None,
        fire_incident_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Validate NERIS field completeness and provide scoring.

        Analyzes fire incident data against NERIS requirements and provides
        a completeness score with specific recommendations.

        Args:
            db: Database session
            tenant_id: Tenant ID
            neris_data: NERIS incident payload
            user_id: User requesting validation
            fire_incident_id: Related fire incident ID

        Returns:
            Dict with:
                - completeness_score: 0-100 score
                - missing_required_fields: List of missing required fields
                - missing_recommended_fields: List of recommended but missing fields
                - data_quality_issues: List of quality issues found
                - suggestions: Specific improvement suggestions
                - ai_generated: True
                - requires_review: False (automated validation)
                - run_id: AI run ID for auditing
        """
        system_prompt = (
            "You are a NERIS (National Emergency Response Information System) compliance expert. "
            "Analyze fire incident data for completeness and quality against NERIS standards. "
            "Identify missing required fields, data quality issues, and provide specific recommendations "
            "to improve report completeness for state reporting requirements."
        )

        prompt_text = f"""Analyze this NERIS fire incident data for completeness and quality:

{json.dumps(neris_data, indent=2)}

Evaluate and provide:
1. completeness_score: Overall score 0-100 (100 = fully complete and high quality)
2. missing_required_fields: List of NERIS-required fields that are missing or empty
3. missing_recommended_fields: List of recommended fields that should be completed
4. data_quality_issues: List of specific issues (e.g., "arrival_time is before dispatch_time", "invalid property_use code")
5. suggestions: Specific, actionable suggestions to improve the report
6. neris_export_ready: true/false - whether this incident is ready for state NERIS export
7. blocking_issues: Critical issues that must be resolved before export

Return as valid JSON. Be specific with field names using dot notation (e.g., "incident.alarm_level")."""

        # Check budget
        estimated_cost = Decimal("0.04")
        if not await self._check_budget_limits(db, tenant_id, estimated_cost):
            raise ValueError("AI budget limit exceeded for this tenant")

        # Invoke Bedrock
        start_time = time.time()
        response = self.bedrock_client.invoke(
            prompt=prompt_text,
            system=system_prompt,
            temperature=0.1,  # Very low for consistent validation
            max_tokens=2000,
            model_id=self.bedrock_client.get_model_for_use_case("balanced"),
        )
        latency_ms = int((time.time() - start_time) * 1000)

        # Parse JSON response
        try:
            result = json.loads(response["content"])
        except json.JSONDecodeError:
            result = {
                "completeness_score": 50,
                "missing_required_fields": [],
                "missing_recommended_fields": [],
                "data_quality_issues": ["Unable to parse AI validation response"],
                "suggestions": [],
                "neris_export_ready": False,
                "blocking_issues": ["AI validation failed"],
            }

        output_data = {
            "completeness_score": result.get("completeness_score", 50),
            "missing_required_fields": result.get("missing_required_fields", []),
            "missing_recommended_fields": result.get("missing_recommended_fields", []),
            "data_quality_issues": result.get("data_quality_issues", []),
            "suggestions": result.get("suggestions", []),
            "neris_export_ready": result.get("neris_export_ready", False),
            "blocking_issues": result.get("blocking_issues", []),
            "ai_generated": True,
            "requires_review": False,  # Automated validation doesn't require review
            "validated_at": datetime.utcnow().isoformat(),
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
            latency_ms=latency_ms,
            fire_incident_id=fire_incident_id,
            user_id=user_id,
        )

        await self._update_budget_spend(db, tenant_id, Decimal(str(response["cost"])))

        return {**output_data, "run_id": str(ai_run.id)}

    async def generate_narrative_assistance(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        incident_data: dict[str, Any],
        user_id: uuid.UUID | None = None,
        fire_incident_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Generate fire incident narrative from structured data.

        Creates a professional fire incident narrative suitable for NERIS reporting
        based on structured incident information.

        Args:
            db: Database session
            tenant_id: Tenant ID
            incident_data: Structured incident data
            user_id: User requesting narrative
            fire_incident_id: Related fire incident ID

        Returns:
            Dict with:
                - narrative_text: Generated narrative
                - confidence: Generation confidence
                - key_points: Key incident points covered
                - requires_review: Always True
                - ai_generated: True
                - run_id: AI run ID for auditing
        """
        system_prompt = (
            "You are a fire service documentation specialist. "
            "Generate clear, professional fire incident narratives for NERIS reporting. "
            "Use appropriate fire service terminology and follow chronological order. "
            "Include critical details: dispatch, response, scene arrival, actions taken, and outcome. "
            "Do NOT include any personal identifiers or sensitive information."
        )

        prompt_text = f"""Generate a professional fire incident narrative based on this data:

{json.dumps(incident_data, indent=2)}

Create a narrative that:
1. Follows chronological order (dispatch → response → arrival → actions → outcome)
2. Uses professional fire service terminology
3. Includes critical timestamps and actions taken
4. Documents resources used and outcomes achieved
5. Is suitable for official NERIS reporting
6. Is concise but thorough (2-4 paragraphs)

Also provide:
- key_points: List of critical facts documented
- timeline_events: Chronological list of key events with times

Return as JSON with keys: narrative_text, key_points, timeline_events"""

        # Check budget
        estimated_cost = Decimal("0.05")
        if not await self._check_budget_limits(db, tenant_id, estimated_cost):
            raise ValueError("AI budget limit exceeded for this tenant")

        # Invoke Bedrock
        start_time = time.time()
        response = self.bedrock_client.invoke(
            prompt=prompt_text,
            system=system_prompt,
            temperature=0.3,  # Moderate temperature for natural narrative
            max_tokens=2048,
            model_id=self.bedrock_client.get_model_for_use_case("balanced"),
        )
        latency_ms = int((time.time() - start_time) * 1000)

        # Check for PHI in output
        narrative_content = response["content"]
        phi_detected = contains_phi(narrative_content)
        if phi_detected:
            raise ValueError("Generated narrative contains PHI - blocked by guardrail")

        # Parse JSON response
        try:
            result = json.loads(narrative_content)
            narrative_text = result.get("narrative_text", "")
            key_points = result.get("key_points", [])
            timeline_events = result.get("timeline_events", [])
        except json.JSONDecodeError:
            # If not JSON, treat entire response as narrative
            narrative_text = narrative_content
            key_points = []
            timeline_events = []

        output_data = {
            "narrative_text": narrative_text,
            "key_points": key_points,
            "timeline_events": timeline_events,
            "confidence": 0.85,
            "requires_review": True,
            "ai_generated": True,
            "generated_at": datetime.utcnow().isoformat(),
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
            fire_incident_id=fire_incident_id,
            user_id=user_id,
            phi_detected=phi_detected,
            confidence_score=0.85,
        )

        await self._update_budget_spend(db, tenant_id, Decimal(str(response["cost"])))

        return {**output_data, "run_id": str(ai_run.id)}

    async def detect_narrative_contradictions(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        incident_data: dict[str, Any],
        narrative_text: str,
        user_id: uuid.UUID | None = None,
        fire_incident_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Detect contradictions between narrative and structured data.

        Analyzes fire incident narrative against structured data to identify
        inconsistencies, contradictions, and logical errors.

        Args:
            db: Database session
            tenant_id: Tenant ID
            incident_data: Structured incident data
            narrative_text: Incident narrative text
            user_id: User requesting check
            fire_incident_id: Related fire incident ID

        Returns:
            Dict with:
                - contradictions: List of contradiction objects
                - total_issues: Count of issues found
                - critical_count: Count of critical issues
                - severity_breakdown: Count by severity
                - ai_generated: True
                - run_id: AI run ID for auditing
        """
        system_prompt = (
            "You are a fire documentation quality assurance analyst. "
            "Identify contradictions, inconsistencies, and logical errors between "
            "the narrative and structured incident data. Focus on:\n"
            "- Timeline inconsistencies (e.g., arrival before dispatch)\n"
            "- Contradictory statements (e.g., narrative says controlled in 10 minutes but timestamps show 2 hours)\n"
            "- Missing critical information in narrative that exists in data\n"
            "- Impossible or illogical sequences of events"
        )

        prompt_text = f"""Analyze this fire incident for contradictions:

STRUCTURED DATA:
{json.dumps(incident_data, indent=2)}

NARRATIVE:
{narrative_text}

Identify contradictions and inconsistencies. For each issue provide:
- description: Clear description of the contradiction
- severity: critical, high, medium, or low
- affected_fields: List of data fields involved
- narrative_excerpt: Relevant excerpt from narrative (if applicable)
- suggested_resolution: How to resolve the contradiction

Return as JSON with key: contradictions (array of objects)"""

        # Check budget
        estimated_cost = Decimal("0.04")
        if not await self._check_budget_limits(db, tenant_id, estimated_cost):
            raise ValueError("AI budget limit exceeded for this tenant")

        # Invoke Bedrock
        start_time = time.time()
        response = self.bedrock_client.invoke(
            prompt=prompt_text,
            system=system_prompt,
            temperature=0.1,  # Low temperature for consistent detection
            max_tokens=2000,
            model_id=self.bedrock_client.get_model_for_use_case("balanced"),
        )
        latency_ms = int((time.time() - start_time) * 1000)

        # Parse JSON response
        try:
            result = json.loads(response["content"])
            contradictions = result.get("contradictions", [])
        except json.JSONDecodeError:
            contradictions = []

        # Calculate severity breakdown
        severity_breakdown = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for contradiction in contradictions:
            severity = contradiction.get("severity", "medium")
            if severity in severity_breakdown:
                severity_breakdown[severity] += 1

        output_data = {
            "contradictions": contradictions,
            "total_issues": len(contradictions),
            "critical_count": severity_breakdown["critical"],
            "severity_breakdown": severity_breakdown,
            "ai_generated": True,
            "analyzed_at": datetime.utcnow().isoformat(),
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
            latency_ms=latency_ms,
            fire_incident_id=fire_incident_id,
            user_id=user_id,
        )

        await self._update_budget_spend(db, tenant_id, Decimal(str(response["cost"])))

        return {**output_data, "run_id": str(ai_run.id)}

    async def detect_property_duplicates(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        property_data: dict[str, Any],
        existing_properties: list[dict[str, Any]],
        user_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Detect potential duplicate properties for preplan management.

        Uses AI to identify properties that may be duplicates based on
        address, name, location, and other characteristics.

        Args:
            db: Database session
            tenant_id: Tenant ID
            property_data: New property data to check
            existing_properties: List of existing properties to compare against
            user_id: User requesting check

        Returns:
            Dict with:
                - is_likely_duplicate: Boolean
                - duplicate_confidence: 0.0-1.0
                - potential_matches: List of potential duplicate property IDs with scores
                - reasoning: Explanation of duplicate detection
                - recommended_action: merge, create_new, or review_manually
                - ai_generated: True
                - run_id: AI run ID for auditing
        """
        system_prompt = (
            "You are a property data deduplication expert. "
            "Analyze property information to detect potential duplicates. "
            "Consider address variations, name similarities, coordinates, and other identifiers. "
            "Account for common variations (e.g., 'Street' vs 'St', '100' vs '100-102'). "
            "Provide confidence scores and clear reasoning."
        )

        # Limit existing properties to avoid token limits
        sample_size = min(len(existing_properties), 50)
        sampled_properties = existing_properties[:sample_size] if existing_properties else []

        prompt_text = f"""Analyze this property for potential duplicates:

NEW PROPERTY:
{json.dumps(property_data, indent=2)}

EXISTING PROPERTIES TO COMPARE:
{json.dumps(sampled_properties, indent=2)}

Analyze and provide:
1. is_likely_duplicate: true/false
2. duplicate_confidence: 0.0-1.0 score
3. potential_matches: Array of objects with {{property_id, match_score (0.0-1.0), matching_factors}}
4. reasoning: Explanation of why you believe these are/aren't duplicates
5. recommended_action: "merge", "create_new", or "review_manually"
6. merge_strategy: If merge recommended, suggest which fields to keep from each property

Return as valid JSON. Be conservative - only flag as likely duplicate if confidence > 0.75."""

        # Check budget
        estimated_cost = Decimal("0.05")
        if not await self._check_budget_limits(db, tenant_id, estimated_cost):
            raise ValueError("AI budget limit exceeded for this tenant")

        # Invoke Bedrock
        start_time = time.time()
        response = self.bedrock_client.invoke(
            prompt=prompt_text,
            system=system_prompt,
            temperature=0.2,
            max_tokens=2000,
            model_id=self.bedrock_client.get_model_for_use_case("balanced"),
        )
        latency_ms = int((time.time() - start_time) * 1000)

        # Parse JSON response
        try:
            result = json.loads(response["content"])
        except json.JSONDecodeError:
            result = {
                "is_likely_duplicate": False,
                "duplicate_confidence": 0.0,
                "potential_matches": [],
                "reasoning": "Unable to parse AI response",
                "recommended_action": "review_manually",
                "merge_strategy": None,
            }

        output_data = {
            "is_likely_duplicate": result.get("is_likely_duplicate", False),
            "duplicate_confidence": result.get("duplicate_confidence", 0.0),
            "potential_matches": result.get("potential_matches", []),
            "reasoning": result.get("reasoning", ""),
            "recommended_action": result.get("recommended_action", "review_manually"),
            "merge_strategy": result.get("merge_strategy"),
            "properties_analyzed": len(sampled_properties),
            "ai_generated": True,
            "analyzed_at": datetime.utcnow().isoformat(),
        }

        ai_run = await self._create_ai_run(
            db=db,
            tenant_id=tenant_id,
            run_type=AiRunType.EXTRACTION,  # Reusing EXTRACTION type for duplicate detection
            model_name=response["model"],
            input_text=prompt_text,
            output_data=output_data,
            tokens_used=response["total_tokens"],
            input_tokens=response["input_tokens"],
            output_tokens=response["output_tokens"],
            cost=Decimal(str(response["cost"])),
            latency_ms=latency_ms,
            user_id=user_id,
            confidence_score=output_data["duplicate_confidence"],
        )

        await self._update_budget_spend(db, tenant_id, Decimal(str(response["cost"])))

        return {**output_data, "run_id": str(ai_run.id)}

    async def classify_property_occupancy(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        property_data: dict[str, Any],
        user_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Classify property occupancy type for NERIS compliance.

        Determines the correct NERIS occupancy classification based on
        property characteristics and business type.

        Args:
            db: Database session
            tenant_id: Tenant ID
            property_data: Property information
            user_id: User requesting classification

        Returns:
            Dict with:
                - occupancy_type: NERIS occupancy code
                - occupancy_description: Human-readable description
                - confidence: Classification confidence
                - reasoning: Explanation
                - construction_type_suggestion: Suggested construction type
                - hazard_flags: Identified hazard categories
                - ai_generated: True
                - run_id: AI run ID for auditing
        """
        system_prompt = (
            "You are a fire safety and building classification expert. "
            "Classify properties according to NERIS occupancy standards and NFPA guidelines. "
            "Consider business type, building use, occupancy load, and construction characteristics. "
            "Provide appropriate NERIS codes and identify potential hazards."
        )

        prompt_text = f"""Classify this property's occupancy type for NERIS fire reporting:

PROPERTY DATA:
{json.dumps(property_data, indent=2)}

Provide:
1. occupancy_type: Specific NERIS occupancy code (e.g., "Assembly", "Educational", "Residential-Multi-family", etc.)
2. occupancy_description: Human-readable description
3. confidence: 0.0-1.0 confidence in classification
4. reasoning: Explanation for classification choice
5. construction_type_suggestion: Likely construction type (Type I-V) based on description
6. hazard_flags: Array of potential hazards (e.g., "High Occupancy Load", "Hazardous Materials", "Limited Access")
7. special_considerations: Any special considerations for firefighters

Return as valid JSON."""

        # Check budget
        estimated_cost = Decimal("0.03")
        if not await self._check_budget_limits(db, tenant_id, estimated_cost):
            raise ValueError("AI budget limit exceeded for this tenant")

        # Invoke Bedrock
        start_time = time.time()
        response = self.bedrock_client.invoke(
            prompt=prompt_text,
            system=system_prompt,
            temperature=0.2,
            max_tokens=1200,
            model_id=self.bedrock_client.get_model_for_use_case("fast"),
        )
        latency_ms = int((time.time() - start_time) * 1000)

        # Parse JSON response
        try:
            result = json.loads(response["content"])
        except json.JSONDecodeError:
            result = {
                "occupancy_type": "Unknown",
                "occupancy_description": "Unable to classify",
                "confidence": 0.3,
                "reasoning": "Unable to parse AI response",
                "construction_type_suggestion": "Unknown",
                "hazard_flags": [],
                "special_considerations": [],
            }

        output_data = {
            "occupancy_type": result.get("occupancy_type", "Unknown"),
            "occupancy_description": result.get("occupancy_description", ""),
            "confidence": result.get("confidence", 0.5),
            "reasoning": result.get("reasoning", ""),
            "construction_type_suggestion": result.get("construction_type_suggestion", "Unknown"),
            "hazard_flags": result.get("hazard_flags", []),
            "special_considerations": result.get("special_considerations", []),
            "ai_generated": True,
            "classified_at": datetime.utcnow().isoformat(),
        }

        ai_run = await self._create_ai_run(
            db=db,
            tenant_id=tenant_id,
            run_type=AiRunType.INCIDENT_CLASSIFICATION,  # Reusing for property classification
            model_name=response["model"],
            input_text=prompt_text,
            output_data=output_data,
            tokens_used=response["total_tokens"],
            input_tokens=response["input_tokens"],
            output_tokens=response["output_tokens"],
            cost=Decimal(str(response["cost"])),
            latency_ms=latency_ms,
            user_id=user_id,
            confidence_score=output_data["confidence"],
        )

        await self._update_budget_spend(db, tenant_id, Decimal(str(response["cost"])))

        return {**output_data, "run_id": str(ai_run.id)}

    async def recommend_preplan_updates(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        preplan_data: dict[str, Any],
        recent_incidents: list[dict[str, Any]],
        user_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Recommend preplan updates based on recent incidents.

        Analyzes existing preplan data and recent incidents at the property
        to suggest updates and improvements to the preplan.

        Args:
            db: Database session
            tenant_id: Tenant ID
            preplan_data: Current preplan data
            recent_incidents: Recent incidents at this property
            user_id: User requesting recommendations

        Returns:
            Dict with:
                - update_recommendations: List of specific update recommendations
                - priority: high, medium, or low
                - outdated_information: List of potentially outdated items
                - new_hazards_identified: Hazards identified from incidents not in preplan
                - access_changes_needed: Suggested access point updates
                - resource_requirement_changes: Updated resource needs
                - ai_generated: True
                - run_id: AI run ID for auditing
        """
        system_prompt = (
            "You are a fire preplan development expert. "
            "Analyze existing preplans and recent incident data to recommend updates. "
            "Focus on: new hazards, access changes, outdated information, resource needs, "
            "and lessons learned from actual incidents. Prioritize recommendations by importance."
        )

        # Limit recent incidents
        sample_incidents = recent_incidents[:10] if recent_incidents else []

        prompt_text = f"""Analyze this preplan for needed updates based on recent incidents:

CURRENT PREPLAN:
{json.dumps(preplan_data, indent=2)}

RECENT INCIDENTS AT THIS PROPERTY:
{json.dumps(sample_incidents, indent=2)}

Provide:
1. update_recommendations: Array of specific recommended updates with {{description, reason, field_to_update}}
2. priority: Overall priority of updates (high, medium, low)
3. outdated_information: List of preplan items that appear outdated
4. new_hazards_identified: Hazards found in incidents not documented in preplan
5. access_changes_needed: Updates to access points, keys, codes
6. resource_requirement_changes: Updated apparatus/personnel requirements based on incident history
7. next_inspection_priority: high, medium, or low based on findings

Return as valid JSON. Be specific and actionable."""

        # Check budget
        estimated_cost = Decimal("0.04")
        if not await self._check_budget_limits(db, tenant_id, estimated_cost):
            raise ValueError("AI budget limit exceeded for this tenant")

        # Invoke Bedrock
        start_time = time.time()
        response = self.bedrock_client.invoke(
            prompt=prompt_text,
            system=system_prompt,
            temperature=0.3,
            max_tokens=2000,
            model_id=self.bedrock_client.get_model_for_use_case("balanced"),
        )
        latency_ms = int((time.time() - start_time) * 1000)

        # Parse JSON response
        try:
            result = json.loads(response["content"])
        except json.JSONDecodeError:
            result = {
                "update_recommendations": [],
                "priority": "medium",
                "outdated_information": [],
                "new_hazards_identified": [],
                "access_changes_needed": [],
                "resource_requirement_changes": {},
                "next_inspection_priority": "medium",
            }

        output_data = {
            "update_recommendations": result.get("update_recommendations", []),
            "priority": result.get("priority", "medium"),
            "outdated_information": result.get("outdated_information", []),
            "new_hazards_identified": result.get("new_hazards_identified", []),
            "access_changes_needed": result.get("access_changes_needed", []),
            "resource_requirement_changes": result.get("resource_requirement_changes", {}),
            "next_inspection_priority": result.get("next_inspection_priority", "medium"),
            "incidents_analyzed": len(sample_incidents),
            "ai_generated": True,
            "analyzed_at": datetime.utcnow().isoformat(),
        }

        ai_run = await self._create_ai_run(
            db=db,
            tenant_id=tenant_id,
            run_type=AiRunType.SUMMARIZATION,  # Reusing for preplan analysis
            model_name=response["model"],
            input_text=prompt_text,
            output_data=output_data,
            tokens_used=response["total_tokens"],
            input_tokens=response["input_tokens"],
            output_tokens=response["output_tokens"],
            cost=Decimal(str(response["cost"])),
            latency_ms=latency_ms,
            user_id=user_id,
        )

        await self._update_budget_spend(db, tenant_id, Decimal(str(response["cost"])))

        return {**output_data, "run_id": str(ai_run.id)}

    async def suggest_inspection_findings(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        property_data: dict[str, Any],
        inspection_observations: str,
        user_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Suggest inspection findings and violations from observations.

        Analyzes inspection observations to suggest specific code violations
        and findings with appropriate citations.

        Args:
            db: Database session
            tenant_id: Tenant ID
            property_data: Property information
            inspection_observations: Inspector's notes/observations
            user_id: User requesting suggestions

        Returns:
            Dict with:
                - suggested_violations: List of potential violations with codes
                - severity_levels: Severity for each violation
                - corrective_actions: Recommended corrective actions
                - reinspection_needed: Boolean
                - estimated_correction_time: Time estimate for corrections
                - ai_generated: True
                - requires_review: True
                - run_id: AI run ID for auditing
        """
        system_prompt = (
            "You are a fire code enforcement expert. "
            "Analyze inspection observations to identify potential code violations. "
            "Suggest appropriate fire code citations (NFPA, IFC), severity levels, "
            "and corrective actions. Be specific but recognize that final determination "
            "must be made by a qualified inspector."
        )

        prompt_text = f"""Analyze these inspection observations and suggest findings:

PROPERTY INFORMATION:
{json.dumps(property_data, indent=2)}

INSPECTOR OBSERVATIONS:
{inspection_observations}

Provide:
1. suggested_violations: Array of potential violations with {{description, code_reference (e.g., "NFPA 1, 10.3.1"), severity (critical/major/minor)}}
2. corrective_actions: Specific actions needed to correct each violation
3. reinspection_needed: true/false - whether reinspection should be required
4. estimated_correction_time: Time estimate for all corrections (e.g., "30 days", "immediate")
5. compliance_areas: List of compliance areas checked (e.g., "Fire Extinguishers", "Exit Signage", "Sprinkler System")
6. inspector_notes: Additional notes for the inspector to consider

Return as valid JSON. Be conservative - suggest potential violations but acknowledge inspector's authority."""

        # Check budget
        estimated_cost = Decimal("0.04")
        if not await self._check_budget_limits(db, tenant_id, estimated_cost):
            raise ValueError("AI budget limit exceeded for this tenant")

        # Invoke Bedrock
        start_time = time.time()
        response = self.bedrock_client.invoke(
            prompt=prompt_text,
            system=system_prompt,
            temperature=0.3,
            max_tokens=2000,
            model_id=self.bedrock_client.get_model_for_use_case("balanced"),
        )
        latency_ms = int((time.time() - start_time) * 1000)

        # Parse JSON response
        try:
            result = json.loads(response["content"])
        except json.JSONDecodeError:
            result = {
                "suggested_violations": [],
                "corrective_actions": [],
                "reinspection_needed": False,
                "estimated_correction_time": "Unknown",
                "compliance_areas": [],
                "inspector_notes": [],
            }

        output_data = {
            "suggested_violations": result.get("suggested_violations", []),
            "corrective_actions": result.get("corrective_actions", []),
            "reinspection_needed": result.get("reinspection_needed", False),
            "estimated_correction_time": result.get("estimated_correction_time", "Unknown"),
            "compliance_areas": result.get("compliance_areas", []),
            "inspector_notes": result.get("inspector_notes", []),
            "ai_generated": True,
            "requires_review": True,
            "generated_at": datetime.utcnow().isoformat(),
        }

        ai_run = await self._create_ai_run(
            db=db,
            tenant_id=tenant_id,
            run_type=AiRunType.CODE_SUGGESTION,  # Reusing for code violation suggestions
            model_name=response["model"],
            input_text=prompt_text,
            output_data=output_data,
            tokens_used=response["total_tokens"],
            input_tokens=response["input_tokens"],
            output_tokens=response["output_tokens"],
            cost=Decimal(str(response["cost"])),
            latency_ms=latency_ms,
            user_id=user_id,
        )

        await self._update_budget_spend(db, tenant_id, Decimal(str(response["cost"])))

        return {**output_data, "run_id": str(ai_run.id)}

    async def detect_permission_conflicts(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        user_roles: list[dict[str, Any]],
        requested_action: str,
        resource_type: str,
        user_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Detect permission conflicts in complex role hierarchies.

        Analyzes user roles and permissions to identify conflicts or
        ambiguous authorization scenarios.

        Args:
            db: Database session
            tenant_id: Tenant ID
            user_roles: User's assigned roles and permissions
            requested_action: Action being attempted
            resource_type: Type of resource being accessed
            user_id: User being analyzed

        Returns:
            Dict with:
                - has_conflicts: Boolean
                - conflict_details: List of specific conflicts
                - resolution_suggestions: How to resolve conflicts
                - effective_permissions: Calculated effective permissions
                - ai_generated: True
                - run_id: AI run ID for auditing
        """
        system_prompt = (
            "You are a security and access control expert. "
            "Analyze role-based access control (RBAC) configurations to detect conflicts, "
            "ambiguities, and authorization issues. Consider role inheritance, permission precedence, "
            "and principle of least privilege."
        )

        prompt_text = f"""Analyze this permission scenario for conflicts:

USER ROLES AND PERMISSIONS:
{json.dumps(user_roles, indent=2)}

REQUESTED ACTION: {requested_action}
RESOURCE TYPE: {resource_type}

Analyze and provide:
1. has_conflicts: true/false - whether conflicting permissions exist
2. conflict_details: Array of specific conflicts (e.g., {{role_a: "fire_captain", role_b: "inspector", conflict: "Both have overlapping permissions with different scopes"}})
3. resolution_suggestions: How to resolve each conflict
4. effective_permissions: The calculated effective permissions for this action (allowed/denied/ambiguous)
5. risk_level: low/medium/high - security risk level of current configuration
6. least_privilege_recommendations: Suggestions to improve security posture

Return as valid JSON."""

        # Check budget
        estimated_cost = Decimal("0.03")
        if not await self._check_budget_limits(db, tenant_id, estimated_cost):
            raise ValueError("AI budget limit exceeded for this tenant")

        # Invoke Bedrock
        start_time = time.time()
        response = self.bedrock_client.invoke(
            prompt=prompt_text,
            system=system_prompt,
            temperature=0.1,  # Low temperature for consistent security analysis
            max_tokens=1500,
            model_id=self.bedrock_client.get_model_for_use_case("fast"),
        )
        latency_ms = int((time.time() - start_time) * 1000)

        # Parse JSON response
        try:
            result = json.loads(response["content"])
        except json.JSONDecodeError:
            result = {
                "has_conflicts": False,
                "conflict_details": [],
                "resolution_suggestions": [],
                "effective_permissions": "ambiguous",
                "risk_level": "medium",
                "least_privilege_recommendations": [],
            }

        output_data = {
            "has_conflicts": result.get("has_conflicts", False),
            "conflict_details": result.get("conflict_details", []),
            "resolution_suggestions": result.get("resolution_suggestions", []),
            "effective_permissions": result.get("effective_permissions", "ambiguous"),
            "risk_level": result.get("risk_level", "medium"),
            "least_privilege_recommendations": result.get("least_privilege_recommendations", []),
            "ai_generated": True,
            "analyzed_at": datetime.utcnow().isoformat(),
        }

        ai_run = await self._create_ai_run(
            db=db,
            tenant_id=tenant_id,
            run_type=AiRunType.EXTRACTION,  # Reusing for permission analysis
            model_name=response["model"],
            input_text=prompt_text,
            output_data=output_data,
            tokens_used=response["total_tokens"],
            input_tokens=response["input_tokens"],
            output_tokens=response["output_tokens"],
            cost=Decimal(str(response["cost"])),
            latency_ms=latency_ms,
            user_id=user_id,
        )

        await self._update_budget_spend(db, tenant_id, Decimal(str(response["cost"])))

        return {**output_data, "run_id": str(ai_run.id)}

    async def analyze_access_patterns(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        access_logs: list[dict[str, Any]],
        user_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Analyze access patterns for anomaly detection.

        Reviews access logs to identify unusual patterns, potential security
        issues, or suspicious activity.

        Args:
            db: Database session
            tenant_id: Tenant ID
            access_logs: Recent access logs to analyze
            user_id: User requesting analysis

        Returns:
            Dict with:
                - anomalies_detected: Boolean
                - anomaly_details: List of specific anomalies
                - risk_score: 0-100 risk score
                - suspicious_patterns: Identified suspicious patterns
                - recommendations: Security recommendations
                - ai_generated: True
                - run_id: AI run ID for auditing
        """
        system_prompt = (
            "You are a security analytics expert specializing in access pattern analysis. "
            "Identify anomalies, unusual behaviors, and potential security threats in access logs. "
            "Consider: unusual times, location changes, failed attempts, privilege escalation, "
            "data access patterns, and deviation from baseline behavior."
        )

        # Limit access logs to avoid token limits
        sample_logs = access_logs[:100] if access_logs else []

        prompt_text = f"""Analyze these access logs for anomalies and security concerns:

ACCESS LOGS (most recent):
{json.dumps(sample_logs, indent=2)}

Provide:
1. anomalies_detected: true/false
2. anomaly_details: Array of specific anomalies with {{timestamp, user_id, anomaly_type, description, severity}}
3. risk_score: Overall security risk (0-100, higher = more risk)
4. suspicious_patterns: Patterns that indicate potential security issues
5. recommendations: Specific security recommendations
6. baseline_deviations: How access patterns deviate from normal behavior
7. requires_investigation: true/false - whether security team should investigate

Return as valid JSON. Be thorough but avoid false positives."""

        # Check budget
        estimated_cost = Decimal("0.05")
        if not await self._check_budget_limits(db, tenant_id, estimated_cost):
            raise ValueError("AI budget limit exceeded for this tenant")

        # Invoke Bedrock
        start_time = time.time()
        response = self.bedrock_client.invoke(
            prompt=prompt_text,
            system=system_prompt,
            temperature=0.2,
            max_tokens=2000,
            model_id=self.bedrock_client.get_model_for_use_case("balanced"),
        )
        latency_ms = int((time.time() - start_time) * 1000)

        # Parse JSON response
        try:
            result = json.loads(response["content"])
        except json.JSONDecodeError:
            result = {
                "anomalies_detected": False,
                "anomaly_details": [],
                "risk_score": 0,
                "suspicious_patterns": [],
                "recommendations": [],
                "baseline_deviations": [],
                "requires_investigation": False,
            }

        output_data = {
            "anomalies_detected": result.get("anomalies_detected", False),
            "anomaly_details": result.get("anomaly_details", []),
            "risk_score": result.get("risk_score", 0),
            "suspicious_patterns": result.get("suspicious_patterns", []),
            "recommendations": result.get("recommendations", []),
            "baseline_deviations": result.get("baseline_deviations", []),
            "requires_investigation": result.get("requires_investigation", False),
            "logs_analyzed": len(sample_logs),
            "ai_generated": True,
            "analyzed_at": datetime.utcnow().isoformat(),
        }

        ai_run = await self._create_ai_run(
            db=db,
            tenant_id=tenant_id,
            run_type=AiRunType.EXTRACTION,  # Reusing for pattern analysis
            model_name=response["model"],
            input_text=prompt_text,
            output_data=output_data,
            tokens_used=response["total_tokens"],
            input_tokens=response["input_tokens"],
            output_tokens=response["output_tokens"],
            cost=Decimal(str(response["cost"])),
            latency_ms=latency_ms,
            user_id=user_id,
        )

        await self._update_budget_spend(db, tenant_id, Decimal(str(response["cost"])))

        return {**output_data, "run_id": str(ai_run.id)}
