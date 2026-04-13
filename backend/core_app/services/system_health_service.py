"""System health monitoring service."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from core_app.models.system_health import SystemHealthSnapshot, ProviderHealthCheck
from core_app.database import check_database_health


class SystemHealthService:
    """Service for monitoring system and component health."""

    def __init__(self, db: Session):
        self.db = db

    def check_provider_health(
        self,
        provider_name: str,
        provider_region: str | None = None,
    ) -> ProviderHealthCheck:
        """
        Check AI provider health and record result.

        Args:
            provider_name: Provider name (e.g., 'aws-bedrock')
            provider_region: Provider region

        Returns:
            Provider health check result
        """
        # For now, we'll do a simple placeholder check
        # In a real implementation, this would call the provider API
        try:
            # TODO: Implement actual provider health check
            # This is a placeholder that assumes healthy
            start_time = datetime.now(UTC)

            # Simulate check
            is_healthy = True
            status = "available"
            error_message = None
            error_type = None

            end_time = datetime.now(UTC)
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)

        except Exception as e:
            is_healthy = False
            status = "error"
            error_message = str(e)
            error_type = type(e).__name__
            response_time_ms = None

        # Record check
        check = ProviderHealthCheck(
            provider_name=provider_name,
            provider_region=provider_region,
            is_healthy=is_healthy,
            status=status,
            response_time_ms=response_time_ms,
            error_message=error_message,
            error_type=error_type,
            check_type="ping",
        )
        self.db.add(check)
        self.db.flush()
        return check

    def get_latest_provider_health(
        self,
        provider_name: str,
    ) -> ProviderHealthCheck | None:
        """Get the most recent health check for a provider."""
        query = (
            select(ProviderHealthCheck)
            .where(ProviderHealthCheck.provider_name == provider_name)
            .order_by(ProviderHealthCheck.checked_at.desc())
            .limit(1)
        )
        return self.db.execute(query).scalar_one_or_none()

    def create_system_snapshot(self) -> SystemHealthSnapshot:
        """
        Create a system health snapshot.

        Aggregates health from all components and creates a snapshot.
        """
        component_status = {}
        healthy_count = 0
        degraded_count = 0
        down_count = 0

        # Check database
        db_healthy, db_status = check_database_health()
        component_status["database"] = db_status
        if db_healthy:
            healthy_count += 1
        elif db_status == "database_not_configured":
            degraded_count += 1
        else:
            down_count += 1

        # Check AI provider
        bedrock_check = self.get_latest_provider_health("aws-bedrock")
        if bedrock_check:
            component_status["bedrock"] = bedrock_check.status
            if bedrock_check.is_healthy:
                healthy_count += 1
            elif bedrock_check.status == "degraded":
                degraded_count += 1
            else:
                down_count += 1
        else:
            component_status["bedrock"] = "unknown"
            degraded_count += 1

        # Determine overall status
        if down_count > 0:
            overall_status = "down"
        elif degraded_count > 0:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        # Get performance metrics (placeholder - would calculate from recent data)
        # In a real implementation, would query usage ledger for recent latencies
        p95_latency = None
        error_rate = None

        snapshot = SystemHealthSnapshot(
            overall_status=overall_status,
            healthy_components=healthy_count,
            degraded_components=degraded_count,
            down_components=down_count,
            active_alerts=0,  # Would come from alerting system
            p95_latency_ms=p95_latency,
            error_rate=error_rate,
            component_status=component_status,
        )
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

    def get_latest_snapshot(self) -> SystemHealthSnapshot | None:
        """Get the most recent system health snapshot."""
        query = (
            select(SystemHealthSnapshot)
            .order_by(SystemHealthSnapshot.created_at.desc())
            .limit(1)
        )
        return self.db.execute(query).scalar_one_or_none()

    def get_current_health_dashboard(self) -> dict[str, Any]:
        """
        Get current system health data for dashboard.

        Returns live health status, optionally using cached snapshot if recent.
        """
        # Try to get recent snapshot (within last 5 minutes)
        recent_cutoff = datetime.now(UTC) - timedelta(minutes=5)
        recent_snapshot = self.db.execute(
            select(SystemHealthSnapshot)
            .where(SystemHealthSnapshot.created_at >= recent_cutoff)
            .order_by(SystemHealthSnapshot.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        if recent_snapshot:
            # Use cached snapshot
            return {
                "active_alerts": recent_snapshot.active_alerts,
                "p95_latency_ms": recent_snapshot.p95_latency_ms or 0,
                "healthy": recent_snapshot.healthy_components,
                "degraded": recent_snapshot.degraded_components,
                "down": recent_snapshot.down_components,
                "overall_status": recent_snapshot.overall_status,
                "component_status": recent_snapshot.component_status or {},
                "as_of": recent_snapshot.created_at.isoformat(),
            }
        else:
            # Create new snapshot
            snapshot = self.create_system_snapshot()
            return {
                "active_alerts": snapshot.active_alerts,
                "p95_latency_ms": snapshot.p95_latency_ms or 0,
                "healthy": snapshot.healthy_components,
                "degraded": snapshot.degraded_components,
                "down": snapshot.down_components,
                "overall_status": snapshot.overall_status,
                "component_status": snapshot.component_status or {},
                "as_of": snapshot.created_at.isoformat(),
            }
