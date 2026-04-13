"""Tests for BudgetService."""
import pytest
from datetime import date
from decimal import Decimal

from core_app.services.budget_service import BudgetService
from core_app.models.budget import Budget, BudgetPeriod


class TestBudgetService:
    """Test suite for BudgetService."""

    def test_create_budget(self, db_session, test_tenant_id, test_admin_id):
        """Test creating a budget."""
        service = BudgetService(db_session)

        budget = service.create_budget(
            tenant_id=test_tenant_id,
            scope_type="tenant",
            scope_value=None,
            period=BudgetPeriod.MONTHLY.value,
            limit_usd=1000.0,
            soft_cap_threshold=0.9,
            hard_cap_enabled=True,
            created_by=test_admin_id,
        )

        assert budget.id is not None
        assert budget.tenant_id == test_tenant_id
        assert budget.limit_usd == 1000.0
        assert budget.soft_cap_threshold == 0.9
        assert budget.hard_cap_enabled is True
        assert budget.period == BudgetPeriod.MONTHLY.value

    def test_check_budget_before_execution_allowed(self, db_session, test_tenant_id, test_admin_id):
        """Test budget check allows execution when under limit."""
        service = BudgetService(db_session)

        budget = service.create_budget(
            tenant_id=test_tenant_id,
            scope_type="tenant",
            scope_value=None,
            period=BudgetPeriod.DAILY.value,
            limit_usd=100.0,
            hard_cap_enabled=True,
            created_by=test_admin_id,
        )

        # Check with cost under limit
        allowed, reason = service.check_budget_before_execution(
            tenant_id=test_tenant_id,
            module=None,
            task_type=None,
            estimated_cost_usd=50.0,
        )

        assert allowed is True
        assert reason is None

    def test_check_budget_before_execution_blocked(self, db_session, test_tenant_id, test_admin_id):
        """Test budget check blocks execution when over limit."""
        service = BudgetService(db_session)

        budget = service.create_budget(
            tenant_id=test_tenant_id,
            scope_type="tenant",
            scope_value=None,
            period=BudgetPeriod.DAILY.value,
            limit_usd=100.0,
            hard_cap_enabled=True,
            created_by=test_admin_id,
        )

        # Record some consumption
        service.record_consumption(
            tenant_id=test_tenant_id,
            module=None,
            task_type=None,
            cost_usd=90.0,
        )

        # Check with cost that would exceed limit
        allowed, reason = service.check_budget_before_execution(
            tenant_id=test_tenant_id,
            module=None,
            task_type=None,
            estimated_cost_usd=20.0,
        )

        assert allowed is False
        assert reason is not None
        assert "hard cap exceeded" in reason.lower()

    def test_record_consumption_soft_cap_violation(self, db_session, test_tenant_id, test_admin_id):
        """Test recording consumption triggers soft cap alert."""
        service = BudgetService(db_session)

        budget = service.create_budget(
            tenant_id=test_tenant_id,
            scope_type="tenant",
            scope_value=None,
            period=BudgetPeriod.DAILY.value,
            limit_usd=100.0,
            soft_cap_threshold=0.9,
            alert_enabled=True,
            created_by=test_admin_id,
        )

        # Record consumption that exceeds soft cap
        result = service.record_consumption(
            tenant_id=test_tenant_id,
            module=None,
            task_type=None,
            cost_usd=95.0,
        )

        assert len(result["violations"]) > 0
        assert result["violations"][0]["type"] == "soft_cap"
        assert len(result["alerts_triggered"]) > 0

    def test_get_budget_status(self, db_session, test_tenant_id, test_admin_id):
        """Test retrieving budget status."""
        service = BudgetService(db_session)

        budget = service.create_budget(
            tenant_id=test_tenant_id,
            scope_type="module",
            scope_value="billing",
            period=BudgetPeriod.MONTHLY.value,
            limit_usd=500.0,
            created_by=test_admin_id,
        )

        # Record some consumption
        service.record_consumption(
            tenant_id=test_tenant_id,
            module="billing",
            task_type=None,
            cost_usd=100.0,
        )

        status = service.get_budget_status(
            tenant_id=test_tenant_id,
            scope_type="module",
            scope_value="billing",
        )

        assert status["exists"] is True
        assert status["limit_usd"] == 500.0
        assert status["consumed_usd"] == 100.0
        assert status["remaining_usd"] == 400.0
        assert status["utilization_pct"] == 20.0
