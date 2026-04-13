"""Tests for ModelRoutingService."""
import pytest

from core_app.services.model_routing_service import ModelRoutingService


class TestModelRoutingService:
    """Test suite for ModelRoutingService."""

    def test_route_task_type_billing(self):
        """Test routing for billing task type."""
        service = ModelRoutingService()

        decision = service.route(
            module="billing",
            task_type="claim_readiness_scoring",
            priority="balanced",
        )

        assert decision.model_id == "anthropic.claude-3-5-sonnet-20241022-v2:0"
        assert decision.routing_strategy in ["task_type", "module_override"]
        assert len(decision.fallback_chain) > 0

    def test_route_fast_task(self):
        """Test routing for fast task type."""
        service = ModelRoutingService()

        decision = service.route(
            module="field",
            task_type="scene_classification",
            priority="fast",
        )

        # Should route to haiku for fast tasks
        assert "haiku" in decision.model_id.lower()
        assert decision.routing_strategy in ["task_type", "priority"]

    def test_route_cost_constrained(self):
        """Test routing with cost constraint."""
        service = ModelRoutingService()

        decision = service.route(
            module="command",
            task_type="incident_summary",
            max_cost_usd=0.001,  # Very low limit
        )

        # Should select cheaper model
        assert "haiku" in decision.model_id.lower()
        assert decision.routing_strategy == "cost_aware"

    def test_module_override(self):
        """Test module-specific model override."""
        service = ModelRoutingService()

        # Billing module should use module override if configured
        decision = service.route(
            module="billing",
            task_type="general",
            priority="balanced",
        )

        assert decision.model_id is not None
        assert len(decision.fallback_chain) > 0

    def test_fallback_chain(self):
        """Test fallback chain generation."""
        service = ModelRoutingService()

        primary_model = "anthropic.claude-3-5-sonnet-20241022-v2:0"
        fallback_chain = service.get_fallback_chain(primary_model)

        assert len(fallback_chain) >= 1
        assert fallback_chain[0] == primary_model
