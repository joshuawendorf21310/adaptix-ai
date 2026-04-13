"""Policy simulation and dry-run service."""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core_app.models.policy import AiPolicy
from core_app.ai.guardrails import (
    contains_phi,
    contains_financial_mutation,
    contains_claim_submission,
    enforce_compliance_rules,
)

logger = logging.getLogger(__name__)


class PolicySimulationService:
    """
    Service for policy simulation and dry-run mode.

    Features:
    - Dry-run policy execution without enforcement
    - Policy violation simulation
    - Policy testing with test cases
    - Policy drift detection
    - What-if analysis for policy changes
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def simulate_policy(
        self,
        *,
        policy_id: UUID,
        test_input: str,
        test_output: str,
        task_type: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Simulate policy enforcement on test data.

        Args:
            policy_id: Policy to simulate
            test_input: Test input content
            test_output: Test AI output
            task_type: Task type being simulated
            context: Additional context

        Returns:
            Simulation results with violations and warnings
        """
        # Load policy
        stmt = select(AiPolicy).where(AiPolicy.id == policy_id)
        result = self.db.execute(stmt)
        policy = result.scalar_one()

        violations = []
        warnings = []
        passed = True

        # Simulate PII masking
        if policy.pii_masking_enabled:
            if contains_phi(test_input):
                violations.append({
                    "rule": "pii_masking_input",
                    "severity": "high",
                    "message": "Input contains PHI that would be masked in production",
                })
                passed = False

            if contains_phi(test_output):
                violations.append({
                    "rule": "pii_in_output",
                    "severity": "critical",
                    "message": "Output contains PHI that would be blocked in production",
                })
                passed = False

        # Simulate content guardrails
        if policy.content_guardrails_enabled:
            # Check for financial mutations (billing tasks)
            if task_type in ("billing", "claim", "payment"):
                if contains_financial_mutation(test_output):
                    violations.append({
                        "rule": "financial_mutation",
                        "severity": "critical",
                        "message": "Output contains financial mutation instructions that would be blocked",
                    })
                    passed = False

                if contains_claim_submission(test_output):
                    violations.append({
                        "rule": "autonomous_claim_submission",
                        "severity": "critical",
                        "message": "Output contains autonomous claim submission that would be blocked",
                    })
                    passed = False

            # Run comprehensive compliance check
            compliance = enforce_compliance_rules(
                output=test_output,
                task_type=task_type,
                tenant_id=str(policy.tenant_id),
            )

            for violation_msg in compliance["violations"]:
                violations.append({
                    "rule": "compliance_rule",
                    "severity": "high",
                    "message": violation_msg,
                })
                passed = False

            for warning_msg in compliance["warnings"]:
                warnings.append({
                    "rule": "compliance_warning",
                    "severity": "medium",
                    "message": warning_msg,
                })

        # Simulate review requirements
        requires_review = policy.require_manual_review
        if policy.review_threshold_confidence and context:
            confidence = context.get("confidence_score", 1.0)
            if confidence < policy.review_threshold_confidence:
                requires_review = True
                warnings.append({
                    "rule": "confidence_threshold",
                    "severity": "medium",
                    "message": f"Confidence {confidence:.2f} below threshold {policy.review_threshold_confidence:.2f}, would require review",
                })

        return {
            "simulation_passed": passed,
            "violations": violations,
            "warnings": warnings,
            "would_require_review": requires_review,
            "policy_id": str(policy_id),
            "policy_name": policy.name,
            "summary": f"{'PASS' if passed else 'FAIL'}: {len(violations)} violations, {len(warnings)} warnings",
        }

    def dry_run_policy_change(
        self,
        *,
        current_policy_id: UUID,
        proposed_changes: dict[str, Any],
        test_cases: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Dry-run a policy change against test cases.

        Args:
            current_policy_id: Current policy ID
            proposed_changes: Proposed policy changes
            test_cases: List of test cases to run

        Returns:
            Analysis of impact of proposed changes
        """
        # Load current policy
        stmt = select(AiPolicy).where(AiPolicy.id == current_policy_id)
        result = self.db.execute(stmt)
        current_policy = result.scalar_one()

        # Simulate current policy
        current_results = []
        for test_case in test_cases:
            result = self.simulate_policy(
                policy_id=current_policy_id,
                test_input=test_case.get("input", ""),
                test_output=test_case.get("output", ""),
                task_type=test_case.get("task_type", "general"),
                context=test_case.get("context"),
            )
            current_results.append({
                "test_case_id": test_case.get("id", "unknown"),
                "result": result,
            })

        # Create simulated policy with changes
        simulated_policy = {
            "pii_masking_enabled": proposed_changes.get("pii_masking_enabled", current_policy.pii_masking_enabled),
            "content_guardrails_enabled": proposed_changes.get("content_guardrails_enabled", current_policy.content_guardrails_enabled),
            "require_manual_review": proposed_changes.get("require_manual_review", current_policy.require_manual_review),
            "review_threshold_confidence": proposed_changes.get("review_threshold_confidence", current_policy.review_threshold_confidence),
        }

        # Simulate proposed policy (using current policy ID but with overrides)
        proposed_results = []
        for test_case in test_cases:
            # Temporarily override policy settings for simulation
            original_settings = {
                "pii_masking_enabled": current_policy.pii_masking_enabled,
                "content_guardrails_enabled": current_policy.content_guardrails_enabled,
                "require_manual_review": current_policy.require_manual_review,
                "review_threshold_confidence": current_policy.review_threshold_confidence,
            }

            # Apply proposed changes
            for key, value in simulated_policy.items():
                setattr(current_policy, key, value)

            result = self.simulate_policy(
                policy_id=current_policy_id,
                test_input=test_case.get("input", ""),
                test_output=test_case.get("output", ""),
                task_type=test_case.get("task_type", "general"),
                context=test_case.get("context"),
            )

            # Restore original settings
            for key, value in original_settings.items():
                setattr(current_policy, key, value)

            proposed_results.append({
                "test_case_id": test_case.get("id", "unknown"),
                "result": result,
            })

        # Analyze differences
        changes_summary = self._analyze_policy_impact(current_results, proposed_results)

        return {
            "current_policy_results": current_results,
            "proposed_policy_results": proposed_results,
            "impact_summary": changes_summary,
            "proposed_changes": proposed_changes,
            "recommendation": self._generate_recommendation(changes_summary),
        }

    def detect_policy_drift(
        self,
        *,
        policy_id: UUID,
        historical_test_cases: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Detect policy drift by comparing current behavior to historical test cases.

        Args:
            policy_id: Policy to check
            historical_test_cases: Historical test cases with expected outcomes

        Returns:
            Drift detection results
        """
        drifted_cases = []
        consistent_cases = []

        for test_case in historical_test_cases:
            current_result = self.simulate_policy(
                policy_id=policy_id,
                test_input=test_case.get("input", ""),
                test_output=test_case.get("output", ""),
                task_type=test_case.get("task_type", "general"),
                context=test_case.get("context"),
            )

            expected_pass = test_case.get("expected_pass", True)
            actual_pass = current_result["simulation_passed"]

            if expected_pass != actual_pass:
                drifted_cases.append({
                    "test_case_id": test_case.get("id", "unknown"),
                    "expected_pass": expected_pass,
                    "actual_pass": actual_pass,
                    "violations": current_result["violations"],
                })
            else:
                consistent_cases.append({
                    "test_case_id": test_case.get("id", "unknown"),
                    "result": "consistent",
                })

        has_drift = len(drifted_cases) > 0
        drift_rate = len(drifted_cases) / len(historical_test_cases) if historical_test_cases else 0

        return {
            "has_drift": has_drift,
            "drift_rate": drift_rate,
            "drifted_cases": drifted_cases,
            "consistent_cases_count": len(consistent_cases),
            "total_cases": len(historical_test_cases),
            "severity": "high" if drift_rate > 0.2 else "medium" if drift_rate > 0.1 else "low",
        }

    def _analyze_policy_impact(
        self,
        current_results: list[dict[str, Any]],
        proposed_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Analyze the impact of policy changes."""
        changes = {
            "more_restrictive_count": 0,
            "less_restrictive_count": 0,
            "no_change_count": 0,
            "new_violations": [],
            "resolved_violations": [],
        }

        for i, (current, proposed) in enumerate(zip(current_results, proposed_results)):
            current_passed = current["result"]["simulation_passed"]
            proposed_passed = proposed["result"]["simulation_passed"]

            if current_passed and not proposed_passed:
                changes["more_restrictive_count"] += 1
                changes["new_violations"].append({
                    "test_case_id": current["test_case_id"],
                    "violations": proposed["result"]["violations"],
                })
            elif not current_passed and proposed_passed:
                changes["less_restrictive_count"] += 1
                changes["resolved_violations"].append({
                    "test_case_id": current["test_case_id"],
                    "previous_violations": current["result"]["violations"],
                })
            else:
                changes["no_change_count"] += 1

        return changes

    def _generate_recommendation(self, impact: dict[str, Any]) -> str:
        """Generate recommendation based on impact analysis."""
        if impact["more_restrictive_count"] > 0 and impact["less_restrictive_count"] == 0:
            return "CAUTION: Policy change is more restrictive. Review new violations before deployment."
        elif impact["less_restrictive_count"] > 0 and impact["more_restrictive_count"] == 0:
            return "WARNING: Policy change is less restrictive. Ensure this aligns with compliance requirements."
        elif impact["more_restrictive_count"] > 0 and impact["less_restrictive_count"] > 0:
            return "REVIEW REQUIRED: Policy change has mixed impact. Careful review needed."
        else:
            return "OK: Policy change has minimal impact on test cases."
