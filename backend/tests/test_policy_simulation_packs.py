"""Policy simulation test packs for various scenarios."""
import pytest
from uuid import uuid4

from core_app.services.policy_simulation_service import PolicySimulationService
from core_app.services.policy_service import PolicyService


class TestPolicySimulationPacks:
    """Test packs for policy simulation scenarios."""

    def test_cost_control_policy_simulation(self, db_session, test_tenant_id, test_admin_id):
        """Simulate cost control policy across various scenarios."""
        policy_service = PolicyService(db_session)
        sim_service = PolicySimulationService(db_session)

        # Create cost control policy
        policy = policy_service.create_policy(
            tenant_id=test_tenant_id,
            name="Cost Control Policy",
            description="Limit costs per request and daily spend",
            scope_type="tenant",
            scope_value=None,
            rules={
                "max_cost_per_request": 1.0,
                "max_daily_cost": 100.0,
                "max_input_tokens": 50000,
            },
            enforcement_level="hard",
            created_by=test_admin_id,
        )

        # Test scenario pack: various cost levels
        test_scenarios = [
            {"module": "billing", "task_type": "claim_review", "estimated_cost": 0.50, "estimated_input_tokens": 10000},
            {"module": "billing", "task_type": "claim_review", "estimated_cost": 0.80, "estimated_input_tokens": 30000},
            {"module": "billing", "task_type": "complex_claim", "estimated_cost": 1.50, "estimated_input_tokens": 60000},
            {"module": "documentation", "task_type": "narrative", "estimated_cost": 0.30, "estimated_input_tokens": 5000},
            {"module": "documentation", "task_type": "validation", "estimated_cost": 2.00, "estimated_input_tokens": 70000},
        ]

        result = sim_service.simulate_policy_batch(
            tenant_id=test_tenant_id,
            policy_id=policy.id,
            test_scenarios=test_scenarios,
        )

        # Verify simulation results
        assert result["total_scenarios"] == 5
        assert result["blocked_count"] == 2  # 2 scenarios exceed limits
        assert result["allowed_count"] == 3
        assert len(result["violations_by_rule"]) > 0

    def test_content_safety_policy_simulation(self, db_session, test_tenant_id, test_admin_id):
        """Simulate content safety policy."""
        policy_service = PolicyService(db_session)
        sim_service = PolicySimulationService(db_session)

        # Create content safety policy
        policy = policy_service.create_policy(
            tenant_id=test_tenant_id,
            name="Content Safety Policy",
            description="Block requests with forbidden patterns",
            scope_type="tenant",
            scope_value=None,
            rules={
                "forbidden_patterns": ["password", "ssn", "credit card"],
                "require_human_review": True,
            },
            enforcement_level="hard",
            created_by=test_admin_id,
        )

        # Test scenarios with various content
        test_scenarios = [
            {
                "module": "documentation",
                "task_type": "narrative",
                "input_preview": "Patient transported to hospital",
                "metadata": {},
            },
            {
                "module": "documentation",
                "task_type": "narrative",
                "input_preview": "Patient's password is 12345",  # Should be blocked
                "metadata": {},
            },
            {
                "module": "billing",
                "task_type": "claim",
                "input_preview": "Insurance claim for services",
                "metadata": {},
            },
        ]

        result = sim_service.simulate_policy_batch(
            tenant_id=test_tenant_id,
            policy_id=policy.id,
            test_scenarios=test_scenarios,
        )

        # Verify safety checks
        assert result["total_scenarios"] == 3
        assert result["blocked_count"] >= 1  # Password scenario blocked

    def test_workload_throttling_simulation(self, db_session, test_tenant_id, test_admin_id):
        """Simulate workload throttling policy."""
        policy_service = PolicyService(db_session)
        sim_service = PolicySimulationService(db_session)

        # Create throttling policy
        policy = policy_service.create_policy(
            tenant_id=test_tenant_id,
            name="Rate Limiting Policy",
            description="Limit requests per minute",
            scope_type="tenant",
            scope_value=None,
            rules={
                "max_requests_per_minute": 10,
                "max_concurrent_requests": 3,
            },
            enforcement_level="soft",
            created_by=test_admin_id,
        )

        # Simulate burst of requests
        test_scenarios = [
            {"module": "test", "task_type": "task", "timestamp": f"2024-01-01T00:00:{i:02d}Z"}
            for i in range(15)  # 15 requests in one minute
        ]

        result = sim_service.simulate_policy_batch(
            tenant_id=test_tenant_id,
            policy_id=policy.id,
            test_scenarios=test_scenarios,
        )

        # Verify throttling applies
        assert result["total_scenarios"] == 15
        # With soft enforcement, requests may be warned but not blocked
        assert "max_requests_per_minute" in str(result.get("violations_by_rule", {}))

    def test_module_specific_policy_simulation(self, db_session, test_tenant_id, test_admin_id):
        """Simulate module-specific policies."""
        policy_service = PolicyService(db_session)
        sim_service = PolicySimulationService(db_session)

        # Create billing-specific policy
        billing_policy = policy_service.create_policy(
            tenant_id=test_tenant_id,
            name="Billing Module Policy",
            description="Stricter limits for billing tasks",
            scope_type="module",
            scope_value="billing",
            rules={
                "max_cost_per_request": 0.50,
                "require_human_review": True,
            },
            enforcement_level="hard",
            created_by=test_admin_id,
        )

        # Test scenarios across modules
        test_scenarios = [
            {"module": "billing", "task_type": "claim", "estimated_cost": 0.40},  # Within limit
            {"module": "billing", "task_type": "claim", "estimated_cost": 0.60},  # Exceeds limit
            {"module": "documentation", "task_type": "narrative", "estimated_cost": 0.60},  # Not in scope
        ]

        result = sim_service.simulate_policy_batch(
            tenant_id=test_tenant_id,
            policy_id=billing_policy.id,
            test_scenarios=test_scenarios,
        )

        # Verify module-specific enforcement
        assert result["total_scenarios"] == 3
        assert result["blocked_count"] == 1  # Only billing scenario over limit blocked

    def test_complex_multi_policy_simulation(self, db_session, test_tenant_id, test_admin_id):
        """Simulate multiple overlapping policies."""
        policy_service = PolicyService(db_session)
        sim_service = PolicySimulationService(db_session)

        # Create multiple policies
        cost_policy = policy_service.create_policy(
            tenant_id=test_tenant_id,
            name="Cost Policy",
            description="Cost limits",
            scope_type="tenant",
            scope_value=None,
            rules={"max_cost_per_request": 1.0},
            enforcement_level="hard",
            created_by=test_admin_id,
        )

        token_policy = policy_service.create_policy(
            tenant_id=test_tenant_id,
            name="Token Policy",
            description="Token limits",
            scope_type="tenant",
            scope_value=None,
            rules={"max_input_tokens": 20000},
            enforcement_level="hard",
            created_by=test_admin_id,
        )

        # Test scenario that violates multiple policies
        test_scenario = {
            "module": "test",
            "task_type": "task",
            "estimated_cost": 1.50,  # Violates cost policy
            "estimated_input_tokens": 30000,  # Violates token policy
        }

        # Simulate against both policies
        cost_result = sim_service.simulate_policy(
            tenant_id=test_tenant_id,
            policy_id=cost_policy.id,
            test_scenario=test_scenario,
        )

        token_result = sim_service.simulate_policy(
            tenant_id=test_tenant_id,
            policy_id=token_policy.id,
            test_scenario=test_scenario,
        )

        # Verify both policies catch violations
        assert cost_result["allowed"] is False
        assert token_result["allowed"] is False
        assert len(cost_result["violations"]) > 0
        assert len(token_result["violations"]) > 0
