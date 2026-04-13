"""Budget tracking and enforcement service."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from core_app.models.budget import Budget, BudgetConsumption, CostAlert, BudgetStatus, BudgetPeriod
from core_app.models.usage import UsageLedgerEntry

logger = logging.getLogger(__name__)


class BudgetService:
    """
    Service for budget tracking and enforcement.

    Features:
    - Tenant, module, and task-type budgets
    - Soft and hard cap enforcement
    - Real-time consumption tracking
    - Cost alerts and notifications
    - Budget period management
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_budget(
        self,
        *,
        tenant_id: UUID,
        scope_type: str,
        scope_value: str | None,
        period: str,
        limit_usd: float,
        soft_cap_threshold: float = 0.9,
        hard_cap_enabled: bool = False,
        alert_enabled: bool = True,
        created_by: UUID,
    ) -> Budget:
        """Create a new budget."""
        # Calculate period dates
        period_start, period_end = self._calculate_period_dates(period)

        budget = Budget(
            tenant_id=tenant_id,
            scope_type=scope_type,
            scope_value=scope_value,
            period=period,
            limit_usd=limit_usd,
            soft_cap_threshold=soft_cap_threshold,
            hard_cap_enabled=hard_cap_enabled,
            alert_enabled=alert_enabled,
            period_start=period_start,
            period_end=period_end,
            created_by=created_by,
        )
        self.db.add(budget)
        self.db.commit()
        self.db.refresh(budget)

        # Initialize consumption tracker
        consumption = BudgetConsumption(
            budget_id=budget.id,
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
        )
        self.db.add(consumption)
        self.db.commit()

        return budget

    def record_consumption(
        self,
        *,
        tenant_id: UUID,
        module: str | None,
        task_type: str | None,
        cost_usd: float,
    ) -> dict[str, Any]:
        """
        Record consumption and check budget limits.

        Returns:
            Dict with budget status and any violations
        """
        today = date.today()
        violations = []
        alerts_triggered = []

        # Check tenant budget
        tenant_budget = self._get_active_budget(
            tenant_id=tenant_id,
            scope_type="tenant",
            scope_value=None,
            check_date=today,
        )
        if tenant_budget:
            violation = self._update_and_check_budget(
                budget=tenant_budget,
                cost_usd=cost_usd,
            )
            if violation:
                violations.append(violation)
                if tenant_budget.alert_enabled:
                    alert = self._create_alert(
                        tenant_id=tenant_id,
                        budget=tenant_budget,
                        violation=violation,
                    )
                    alerts_triggered.append(alert)

        # Check module budget
        if module:
            module_budget = self._get_active_budget(
                tenant_id=tenant_id,
                scope_type="module",
                scope_value=module,
                check_date=today,
            )
            if module_budget:
                violation = self._update_and_check_budget(
                    budget=module_budget,
                    cost_usd=cost_usd,
                )
                if violation:
                    violations.append(violation)
                    if module_budget.alert_enabled:
                        alert = self._create_alert(
                            tenant_id=tenant_id,
                            budget=module_budget,
                            violation=violation,
                        )
                        alerts_triggered.append(alert)

        # Check task-type budget
        if task_type:
            task_budget = self._get_active_budget(
                tenant_id=tenant_id,
                scope_type="task_type",
                scope_value=task_type,
                check_date=today,
            )
            if task_budget:
                violation = self._update_and_check_budget(
                    budget=task_budget,
                    cost_usd=cost_usd,
                )
                if violation:
                    violations.append(violation)
                    if task_budget.alert_enabled:
                        alert = self._create_alert(
                            tenant_id=tenant_id,
                            budget=task_budget,
                            violation=violation,
                        )
                        alerts_triggered.append(alert)

        self.db.commit()

        return {
            "violations": violations,
            "alerts_triggered": [str(a.id) for a in alerts_triggered],
            "hard_cap_exceeded": any(v["type"] == "hard_cap" for v in violations),
        }

    def check_budget_before_execution(
        self,
        *,
        tenant_id: UUID,
        module: str | None,
        task_type: str | None,
        estimated_cost_usd: float,
    ) -> tuple[bool, str | None]:
        """
        Check if execution is allowed under budget constraints.

        Returns:
            Tuple of (allowed, reason)
        """
        today = date.today()

        # Check tenant budget
        tenant_budget = self._get_active_budget(
            tenant_id=tenant_id,
            scope_type="tenant",
            scope_value=None,
            check_date=today,
        )
        if tenant_budget and tenant_budget.hard_cap_enabled:
            consumption = self._get_consumption(tenant_budget.id, today)
            if consumption:
                projected_spend = consumption.consumed_usd + estimated_cost_usd
                if projected_spend > tenant_budget.limit_usd:
                    return False, f"Tenant budget hard cap exceeded: ${projected_spend:.2f} > ${tenant_budget.limit_usd:.2f}"

        # Check module budget
        if module:
            module_budget = self._get_active_budget(
                tenant_id=tenant_id,
                scope_type="module",
                scope_value=module,
                check_date=today,
            )
            if module_budget and module_budget.hard_cap_enabled:
                consumption = self._get_consumption(module_budget.id, today)
                if consumption:
                    projected_spend = consumption.consumed_usd + estimated_cost_usd
                    if projected_spend > module_budget.limit_usd:
                        return False, f"Module '{module}' budget hard cap exceeded"

        return True, None

    def get_budget_status(
        self,
        *,
        tenant_id: UUID,
        scope_type: str,
        scope_value: str | None = None,
    ) -> dict[str, Any]:
        """Get current budget status and consumption."""
        today = date.today()
        budget = self._get_active_budget(
            tenant_id=tenant_id,
            scope_type=scope_type,
            scope_value=scope_value,
            check_date=today,
        )

        if not budget:
            return {
                "exists": False,
                "message": "No active budget found for this scope",
            }

        consumption = self._get_consumption(budget.id, today)
        if not consumption:
            return {
                "exists": True,
                "limit_usd": budget.limit_usd,
                "consumed_usd": 0.0,
                "remaining_usd": budget.limit_usd,
                "utilization_pct": 0.0,
                "status": budget.status,
            }

        remaining = budget.limit_usd - consumption.consumed_usd
        utilization = (consumption.consumed_usd / budget.limit_usd) * 100 if budget.limit_usd > 0 else 0

        return {
            "exists": True,
            "limit_usd": budget.limit_usd,
            "consumed_usd": consumption.consumed_usd,
            "remaining_usd": max(0, remaining),
            "utilization_pct": utilization,
            "request_count": consumption.request_count,
            "period_start": budget.period_start.isoformat(),
            "period_end": budget.period_end.isoformat(),
            "status": budget.status,
            "soft_cap_threshold": budget.soft_cap_threshold,
            "hard_cap_enabled": budget.hard_cap_enabled,
            "is_soft_cap_exceeded": consumption.is_soft_cap_exceeded,
            "is_hard_cap_exceeded": consumption.is_hard_cap_exceeded,
        }

    def get_recent_alerts(
        self,
        *,
        tenant_id: UUID,
        limit: int = 50,
        unresolved_only: bool = False,
    ) -> list[CostAlert]:
        """Get recent cost alerts."""
        stmt = select(CostAlert).where(CostAlert.tenant_id == tenant_id)

        if unresolved_only:
            stmt = stmt.where(CostAlert.is_resolved == False)

        stmt = stmt.order_by(CostAlert.created_at.desc()).limit(limit)
        result = self.db.execute(stmt)
        return list(result.scalars().all())

    def _get_active_budget(
        self,
        *,
        tenant_id: UUID,
        scope_type: str,
        scope_value: str | None,
        check_date: date,
    ) -> Budget | None:
        """Get active budget for scope."""
        stmt = select(Budget).where(
            and_(
                Budget.tenant_id == tenant_id,
                Budget.scope_type == scope_type,
                Budget.scope_value == scope_value,
                Budget.period_start <= check_date,
                Budget.period_end >= check_date,
            )
        )
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    def _get_consumption(self, budget_id: UUID, check_date: date) -> BudgetConsumption | None:
        """Get consumption record for budget."""
        stmt = select(BudgetConsumption).where(
            and_(
                BudgetConsumption.budget_id == budget_id,
                BudgetConsumption.period_start <= check_date,
                BudgetConsumption.period_end >= check_date,
            )
        )
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    def _update_and_check_budget(
        self,
        budget: Budget,
        cost_usd: float,
    ) -> dict[str, Any] | None:
        """Update consumption and check for violations."""
        consumption = self._get_consumption(budget.id, date.today())
        if not consumption:
            return None

        # Update consumption
        consumption.consumed_usd += cost_usd
        consumption.request_count += 1
        consumption.updated_at = datetime.now(UTC)

        # Check thresholds
        soft_cap_limit = budget.limit_usd * budget.soft_cap_threshold
        violation = None

        if budget.hard_cap_enabled and consumption.consumed_usd > budget.limit_usd:
            if not consumption.is_hard_cap_exceeded:
                consumption.is_hard_cap_exceeded = True
                consumption.hard_cap_exceeded_at = datetime.now(UTC)
                budget.status = BudgetStatus.HARD_CAP_EXCEEDED.value
                violation = {
                    "type": "hard_cap",
                    "budget_id": str(budget.id),
                    "scope": f"{budget.scope_type}:{budget.scope_value}",
                    "consumed": consumption.consumed_usd,
                    "limit": budget.limit_usd,
                }

        elif consumption.consumed_usd > soft_cap_limit:
            if not consumption.is_soft_cap_exceeded:
                consumption.is_soft_cap_exceeded = True
                consumption.soft_cap_exceeded_at = datetime.now(UTC)
                budget.status = BudgetStatus.SOFT_CAP_EXCEEDED.value
                violation = {
                    "type": "soft_cap",
                    "budget_id": str(budget.id),
                    "scope": f"{budget.scope_type}:{budget.scope_value}",
                    "consumed": consumption.consumed_usd,
                    "threshold": soft_cap_limit,
                    "limit": budget.limit_usd,
                }

        return violation

    def _create_alert(
        self,
        tenant_id: UUID,
        budget: Budget,
        violation: dict[str, Any],
    ) -> CostAlert:
        """Create cost alert for violation."""
        violation_type = violation["type"]
        scope = violation["scope"]
        consumed = violation["consumed"]
        limit = violation.get("limit", 0)

        if violation_type == "hard_cap":
            severity = "critical"
            title = f"Hard Cap Exceeded: {scope}"
            message = f"Budget hard cap exceeded for {scope}. Consumed: ${consumed:.2f}, Limit: ${limit:.2f}"
        else:
            severity = "high"
            title = f"Soft Cap Exceeded: {scope}"
            threshold = violation.get("threshold", 0)
            message = f"Budget soft cap exceeded for {scope}. Consumed: ${consumed:.2f}, Threshold: ${threshold:.2f}, Limit: ${limit:.2f}"

        alert = CostAlert(
            tenant_id=tenant_id,
            alert_type=violation_type,
            severity=severity,
            title=title,
            message=message,
            budget_id=budget.id,
            scope_type=budget.scope_type,
            scope_value=budget.scope_value,
            current_spend_usd=consumed,
            budget_limit_usd=limit,
        )
        self.db.add(alert)
        return alert

    def _calculate_period_dates(self, period: str) -> tuple[date, date]:
        """Calculate start and end dates for budget period."""
        today = date.today()

        if period == BudgetPeriod.DAILY.value:
            return today, today
        elif period == BudgetPeriod.WEEKLY.value:
            # Week starts Monday
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
            return start, end
        elif period == BudgetPeriod.MONTHLY.value:
            start = date(today.year, today.month, 1)
            if today.month == 12:
                end = date(today.year + 1, 1, 1) - timedelta(days=1)
            else:
                end = date(today.year, today.month + 1, 1) - timedelta(days=1)
            return start, end
        elif period == BudgetPeriod.QUARTERLY.value:
            quarter = (today.month - 1) // 3 + 1
            start_month = (quarter - 1) * 3 + 1
            start = date(today.year, start_month, 1)
            if quarter == 4:
                end = date(today.year + 1, 1, 1) - timedelta(days=1)
            else:
                end_month = quarter * 3 + 1
                end = date(today.year, end_month, 1) - timedelta(days=1)
            return start, end
        elif period == BudgetPeriod.ANNUAL.value:
            start = date(today.year, 1, 1)
            end = date(today.year, 12, 31)
            return start, end
        else:
            # Default to monthly
            return self._calculate_period_dates(BudgetPeriod.MONTHLY.value)
