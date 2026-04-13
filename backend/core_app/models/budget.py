"""Budget tracking models for AI spend control."""
from __future__ import annotations

from datetime import UTC, datetime, date
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core_app.database import Base


class BudgetPeriod(str, Enum):
    """Budget period types."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class BudgetStatus(str, Enum):
    """Budget status."""
    ACTIVE = "active"
    SOFT_CAP_EXCEEDED = "soft_cap_exceeded"
    HARD_CAP_EXCEEDED = "hard_cap_exceeded"
    SUSPENDED = "suspended"


class Budget(Base):
    """
    Budget configuration for AI spend control.

    Supports tenant-level, module-level, and task-type-level budgets.
    """
    __tablename__ = "budgets"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Budget scope
    scope_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # tenant, module, task_type, user
    scope_value: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )  # specific module/task/user if scoped

    # Budget configuration
    period: Mapped[str] = mapped_column(String(50), nullable=False, default=BudgetPeriod.MONTHLY.value)
    limit_usd: Mapped[float] = mapped_column(Float, nullable=False)
    soft_cap_threshold: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.9
    )  # 90% triggers warning

    # Enforcement
    hard_cap_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    alert_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=BudgetStatus.ACTIVE.value)

    # Period tracking
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    # Metadata
    created_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC)
    )

    def __repr__(self) -> str:
        return f"<Budget {self.scope_type}:{self.scope_value} ${self.limit_usd}>"


class BudgetConsumption(Base):
    """
    Real-time budget consumption tracking.

    Tracks spend against budgets in real-time for enforcement.
    """
    __tablename__ = "budget_consumptions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    budget_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("budgets.id"), nullable=False, index=True
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Consumption metrics
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    consumed_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Status
    is_soft_cap_exceeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_hard_cap_exceeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    soft_cap_exceeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hard_cap_exceeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC)
    )

    def __repr__(self) -> str:
        return f"<BudgetConsumption ${self.consumed_usd:.2f}>"


class CostAlert(Base):
    """
    Cost alerts for budget monitoring.

    Tracks alerts triggered by budget violations or anomalies.
    """
    __tablename__ = "cost_alerts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Alert details
    alert_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # soft_cap, hard_cap, anomaly, spike
    severity: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # low, medium, high, critical
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Context
    budget_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("budgets.id"), nullable=True
    )
    scope_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    scope_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_spend_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    budget_limit_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Status
    is_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Notifications
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notification_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )

    def __repr__(self) -> str:
        return f"<CostAlert {self.severity}:{self.alert_type}>"
