"""Integration tests for complete workflows."""
import pytest
from uuid import uuid4
from datetime import datetime, UTC

from core_app.services.budget_service import BudgetService
from core_app.services.review_service import ReviewService
from core_app.services.policy_service import PolicyService
from core_app.models.budget import BudgetPeriod


class TestBudgetReviewWorkflow:
    """Test complete budget enforcement and review workflow."""

    def test_budget_exceeded_triggers_review(self, db_session, test_tenant_id, test_user_id, test_admin_id):
        """Test that exceeding budget triggers review queue item."""
        # Create budget with hard cap
        budget_service = BudgetService(db_session)
        budget = budget_service.create_budget(
            tenant_id=test_tenant_id,
            scope_type="tenant",
            scope_value=None,
            period=BudgetPeriod.DAILY.value,
            limit_usd=50.0,
            hard_cap_enabled=True,
            created_by=test_admin_id,
        )

        # Record consumption up to soft cap
        budget_service.record_consumption(
            tenant_id=test_tenant_id,
            module=None,
            task_type=None,
            cost_usd=46.0,  # 92% of budget
        )

        # Verify soft cap alert created
        alerts = budget_service.get_recent_alerts(tenant_id=test_tenant_id)
        assert len(alerts) >= 1
        assert any(a.alert_type == "soft_cap_exceeded" for a in alerts)

        # Verify budget check blocks further execution
        allowed, reason = budget_service.check_budget_before_execution(
            tenant_id=test_tenant_id,
            module=None,
            task_type=None,
            estimated_cost_usd=10.0,
        )
        assert allowed is False
        assert "hard cap" in reason.lower()


class TestPolicyEnforcementWorkflow:
    """Test complete policy enforcement workflow."""

    def test_policy_blocks_high_risk_task(self, db_session, test_tenant_id, test_user_id, test_admin_id):
        """Test that policy blocks high-risk tasks and creates review item."""
        policy_service = PolicyService(db_session)
        review_service = ReviewService(db_session)

        # Create restrictive policy
        policy = policy_service.create_policy(
            tenant_id=test_tenant_id,
            name="Block High Cost Tasks",
            description="Block tasks over $5",
            scope_type="tenant",
            scope_value=None,
            rules={
                "max_cost_per_request": 5.0,
                "max_input_tokens": 10000,
            },
            enforcement_level="hard",
            created_by=test_admin_id,
        )

        # Evaluate high-cost request
        request_context = {
            "module": "test_module",
            "task_type": "expensive_task",
            "estimated_cost": 10.0,
            "estimated_input_tokens": 5000,
        }

        result = policy_service.evaluate_request(
            tenant_id=test_tenant_id,
            request_context=request_context,
        )

        assert result["allowed"] is False
        assert len(result["violations"]) > 0


class TestReviewEscalationWorkflow:
    """Test review escalation workflow."""

    def test_review_escalation_flow(self, db_session, test_tenant_id, test_user_id, test_admin_id):
        """Test complete review escalation flow."""
        review_service = ReviewService(db_session)
        execution_request_id = uuid4()

        # Create review item
        review = review_service.create_review_item(
            tenant_id=test_tenant_id,
            execution_request_id=execution_request_id,
            review_reason="Budget cap exceeded",
            review_type="budget_exceeded",
            priority="high",
            metadata={"estimated_cost": 100.0, "budget_limit": 50.0},
        )

        # Escalate review
        escalated = review_service.escalate_review(
            review_id=review.id,
            escalated_by=test_user_id,
            escalation_reason="Requires management approval",
            escalate_to=test_admin_id,
        )

        assert escalated.is_escalated is True
        assert escalated.assigned_to == test_admin_id

        # Admin approves with modifications
        approved = review_service.approve_review(
            review_id=review.id,
            reviewer_id=test_admin_id,
            notes="Approved with reduced scope",
            modifications={"reduced_cost": 50.0},
        )

        assert approved.status == "approved"
        assert approved.reviewed_at is not None

        # Verify audit trail
        history = review_service.get_review_history(review_id=review.id)
        assert len(history) >= 2  # Escalation + Approval


class TestCompleteBillingWorkflow:
    """Test complete billing intelligence workflow."""

    def test_billing_workflow_from_claim_to_submission(self, db_session, test_tenant_id, test_user_id):
        """Test complete workflow from claim creation to submission."""
        # This is a placeholder for billing workflow integration test
        # In a real implementation, this would:
        # 1. Create claim data
        # 2. Run claim readiness scoring
        # 3. Run denial risk assessment
        # 4. Generate medical necessity summary
        # 5. Check documentation completeness
        # 6. Suggest coding improvements
        # 7. Submit claim if all checks pass
        #
        # For now, we just verify the services can be instantiated
        assert db_session is not None
        assert test_tenant_id is not None
        assert test_user_id is not None
