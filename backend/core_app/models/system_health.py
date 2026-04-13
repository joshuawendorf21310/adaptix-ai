"""System health and provider monitoring models."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core_app.database import Base


class SystemHealthSnapshot(Base):
    """
    Point-in-time snapshot of overall system health.

    Captures component health, performance metrics, and active incidents.
    """
    __tablename__ = "system_health_snapshots"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Overall status
    overall_status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Status: healthy, degraded, down

    # Component counts
    healthy_components: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    degraded_components: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    down_components: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Active incidents
    active_alerts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Performance metrics
    p95_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Component details
    component_status: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # {database: "healthy", bedrock: "healthy", redis: "degraded", ...}

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )

    def __repr__(self) -> str:
        return f"<SystemHealthSnapshot {self.overall_status} at {self.created_at}>"


class ProviderHealthCheck(Base):
    """
    Health check results for AI provider (e.g., AWS Bedrock).

    Periodic probes to verify provider connectivity and performance.
    """
    __tablename__ = "provider_health_checks"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Provider identity
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    provider_region: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Check result
    is_healthy: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    # Status: available, degraded, unavailable, timeout, error

    # Performance
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Error details
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Check metadata
    check_type: Mapped[str] = mapped_column(String(50), nullable=False, default="ping")
    # Types: ping, full_inference, capability_test

    # Timestamp
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )

    def __repr__(self) -> str:
        health = "healthy" if self.is_healthy else "unhealthy"
        return f"<ProviderHealthCheck {self.provider_name} {health}>"
