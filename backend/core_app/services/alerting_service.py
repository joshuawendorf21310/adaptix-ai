"""Alerting service for AI observability and cost monitoring."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from core_app.models.budget import CostAlert
from core_app.models.usage import UsageLedgerEntry
from core_app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class AlertingService:
    """
    Service for AI observability alerts.

    Features:
    - Cost spike detection
    - Quality regression alerts
    - Latency regression alerts
    - Safety violation alerts
    - Prompt drift alerts
    - Task failure clustering
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.audit_service = AuditService(db)

    def detect_cost_spike(
        self,
        *,
        tenant_id: UUID,
        module: str | None = None,
        lookback_hours: int = 24,
        spike_threshold: float = 2.0,  # 2x normal cost
    ) -> dict[str, Any]:
        """
        Detect cost spikes compared to baseline.

        Args:
            tenant_id: Tenant ID
            module: Optional module filter
            lookback_hours: Hours to look back for baseline
            spike_threshold: Multiplier for spike detection (e.g., 2.0 = 200%)

        Returns:
            Spike detection results with alert if needed
        """
        now = datetime.now(UTC)
        current_window_start = now - timedelta(hours=1)
        baseline_window_start = now - timedelta(hours=lookback_hours)

        # Calculate current hour cost
        current_stmt = select(func.sum(UsageLedgerEntry.cost)).where(
            and_(
                UsageLedgerEntry.tenant_id == tenant_id,
                UsageLedgerEntry.created_at >= current_window_start,
            )
        )
        if module:
            current_stmt = current_stmt.where(UsageLedgerEntry.module == module)

        current_cost = self.db.execute(current_stmt).scalar() or 0.0

        # Calculate baseline average cost per hour
        baseline_stmt = select(func.sum(UsageLedgerEntry.cost)).where(
            and_(
                UsageLedgerEntry.tenant_id == tenant_id,
                UsageLedgerEntry.created_at >= baseline_window_start,
                UsageLedgerEntry.created_at < current_window_start,
            )
        )
        if module:
            baseline_stmt = baseline_stmt.where(UsageLedgerEntry.module == module)

        baseline_total = self.db.execute(baseline_stmt).scalar() or 0.0
        baseline_avg = baseline_total / max(lookback_hours - 1, 1)

        # Detect spike
        is_spike = False
        spike_multiplier = 0.0
        if baseline_avg > 0:
            spike_multiplier = current_cost / baseline_avg
            is_spike = spike_multiplier >= spike_threshold

        result = {
            "is_spike": is_spike,
            "current_hour_cost": current_cost,
            "baseline_avg_cost": baseline_avg,
            "spike_multiplier": spike_multiplier,
            "threshold": spike_threshold,
        }

        # Create alert if spike detected
        if is_spike:
            alert = CostAlert(
                tenant_id=tenant_id,
                alert_type="cost_spike",
                severity="high",
                title=f"Cost Spike Detected: {module or 'All Modules'}",
                message=f"Cost spike detected: ${current_cost:.2f} vs baseline ${baseline_avg:.2f} ({spike_multiplier:.1f}x)",
                scope_type="module" if module else "tenant",
                scope_value=module,
                current_spend_usd=current_cost,
            )
            self.db.add(alert)
            self.db.commit()
            result["alert_id"] = str(alert.id)

        return result

    def detect_latency_regression(
        self,
        *,
        tenant_id: UUID,
        module: str | None = None,
        task_type: str | None = None,
        lookback_hours: int = 24,
        regression_threshold: float = 1.5,  # 1.5x baseline
    ) -> dict[str, Any]:
        """
        Detect latency regression compared to baseline.

        Args:
            tenant_id: Tenant ID
            module: Optional module filter
            task_type: Optional task type filter
            lookback_hours: Hours to look back for baseline
            regression_threshold: Multiplier for regression detection

        Returns:
            Regression detection results
        """
        now = datetime.now(UTC)
        current_window_start = now - timedelta(hours=1)
        baseline_window_start = now - timedelta(hours=lookback_hours)

        # Calculate current hour p95 latency
        current_stmt = select(
            func.percentile_cont(0.95).within_group(UsageLedgerEntry.latency_ms)
        ).where(
            and_(
                UsageLedgerEntry.tenant_id == tenant_id,
                UsageLedgerEntry.created_at >= current_window_start,
                UsageLedgerEntry.latency_ms.isnot(None),
            )
        )
        if module:
            current_stmt = current_stmt.where(UsageLedgerEntry.module == module)
        if task_type:
            current_stmt = current_stmt.where(UsageLedgerEntry.task_type == task_type)

        current_p95 = self.db.execute(current_stmt).scalar() or 0.0

        # Calculate baseline p95 latency
        baseline_stmt = select(
            func.percentile_cont(0.95).within_group(UsageLedgerEntry.latency_ms)
        ).where(
            and_(
                UsageLedgerEntry.tenant_id == tenant_id,
                UsageLedgerEntry.created_at >= baseline_window_start,
                UsageLedgerEntry.created_at < current_window_start,
                UsageLedgerEntry.latency_ms.isnot(None),
            )
        )
        if module:
            baseline_stmt = baseline_stmt.where(UsageLedgerEntry.module == module)
        if task_type:
            baseline_stmt = baseline_stmt.where(UsageLedgerEntry.task_type == task_type)

        baseline_p95 = self.db.execute(baseline_stmt).scalar() or 0.0

        # Detect regression
        is_regression = False
        regression_multiplier = 0.0
        if baseline_p95 > 0:
            regression_multiplier = current_p95 / baseline_p95
            is_regression = regression_multiplier >= regression_threshold

        result = {
            "is_regression": is_regression,
            "current_p95_latency_ms": current_p95,
            "baseline_p95_latency_ms": baseline_p95,
            "regression_multiplier": regression_multiplier,
            "threshold": regression_threshold,
        }

        # Create alert if regression detected
        if is_regression:
            alert = CostAlert(
                tenant_id=tenant_id,
                alert_type="latency_regression",
                severity="medium",
                title=f"Latency Regression Detected: {module or task_type or 'All Tasks'}",
                message=f"Latency regression: P95 {current_p95:.0f}ms vs baseline {baseline_p95:.0f}ms ({regression_multiplier:.1f}x)",
                scope_type="task_type" if task_type else ("module" if module else "tenant"),
                scope_value=task_type or module,
            )
            self.db.add(alert)
            self.db.commit()
            result["alert_id"] = str(alert.id)

        return result

    def detect_quality_regression(
        self,
        *,
        tenant_id: UUID,
        module: str | None = None,
        task_type: str | None = None,
        lookback_hours: int = 24,
        error_rate_threshold: float = 0.1,  # 10% error rate
    ) -> dict[str, Any]:
        """
        Detect quality regression based on error rates.

        Args:
            tenant_id: Tenant ID
            module: Optional module filter
            task_type: Optional task type filter
            lookback_hours: Hours to look back
            error_rate_threshold: Error rate threshold (0.0-1.0)

        Returns:
            Quality regression results
        """
        now = datetime.now(UTC)
        window_start = now - timedelta(hours=lookback_hours)

        # Count total requests
        total_stmt = select(func.count(UsageLedgerEntry.id)).where(
            and_(
                UsageLedgerEntry.tenant_id == tenant_id,
                UsageLedgerEntry.created_at >= window_start,
            )
        )
        if module:
            total_stmt = total_stmt.where(UsageLedgerEntry.module == module)
        if task_type:
            total_stmt = total_stmt.where(UsageLedgerEntry.task_type == task_type)

        total_requests = self.db.execute(total_stmt).scalar() or 0

        # Count failed requests
        failed_stmt = select(func.count(UsageLedgerEntry.id)).where(
            and_(
                UsageLedgerEntry.tenant_id == tenant_id,
                UsageLedgerEntry.created_at >= window_start,
                UsageLedgerEntry.success == False,
            )
        )
        if module:
            failed_stmt = failed_stmt.where(UsageLedgerEntry.module == module)
        if task_type:
            failed_stmt = failed_stmt.where(UsageLedgerEntry.task_type == task_type)

        failed_requests = self.db.execute(failed_stmt).scalar() or 0

        # Calculate error rate
        error_rate = failed_requests / total_requests if total_requests > 0 else 0.0
        is_regression = error_rate >= error_rate_threshold

        result = {
            "is_regression": is_regression,
            "error_rate": error_rate,
            "total_requests": total_requests,
            "failed_requests": failed_requests,
            "threshold": error_rate_threshold,
        }

        # Create alert if regression detected
        if is_regression and total_requests >= 10:  # Only alert if meaningful sample
            alert = CostAlert(
                tenant_id=tenant_id,
                alert_type="quality_regression",
                severity="high",
                title=f"Quality Regression Detected: {module or task_type or 'All Tasks'}",
                message=f"Error rate: {error_rate*100:.1f}% ({failed_requests}/{total_requests} requests failed)",
                scope_type="task_type" if task_type else ("module" if module else "tenant"),
                scope_value=task_type or module,
            )
            self.db.add(alert)
            self.db.commit()
            result["alert_id"] = str(alert.id)

        return result

    def detect_task_failure_clustering(
        self,
        *,
        tenant_id: UUID,
        lookback_hours: int = 1,
        cluster_threshold: int = 5,  # 5+ failures in window
    ) -> dict[str, Any]:
        """
        Detect clustering of task failures.

        Args:
            tenant_id: Tenant ID
            lookback_hours: Hours to look back
            cluster_threshold: Minimum failures to consider a cluster

        Returns:
            Clustering detection results
        """
        now = datetime.now(UTC)
        window_start = now - timedelta(hours=lookback_hours)

        # Group failures by error type
        stmt = select(
            UsageLedgerEntry.error_type,
            func.count(UsageLedgerEntry.id).label("count"),
        ).where(
            and_(
                UsageLedgerEntry.tenant_id == tenant_id,
                UsageLedgerEntry.created_at >= window_start,
                UsageLedgerEntry.success == False,
                UsageLedgerEntry.error_type.isnot(None),
            )
        ).group_by(UsageLedgerEntry.error_type)

        result_rows = self.db.execute(stmt).all()

        clusters = []
        for error_type, count in result_rows:
            if count >= cluster_threshold:
                clusters.append({
                    "error_type": error_type,
                    "failure_count": count,
                })

                # Create alert for cluster
                alert = CostAlert(
                    tenant_id=tenant_id,
                    alert_type="task_failure_cluster",
                    severity="high",
                    title=f"Task Failure Cluster: {error_type}",
                    message=f"Detected {count} failures of type '{error_type}' in last {lookback_hours} hour(s)",
                    scope_type="error_type",
                    scope_value=error_type,
                )
                self.db.add(alert)

        if clusters:
            self.db.commit()

        return {
            "has_clusters": len(clusters) > 0,
            "clusters": clusters,
            "threshold": cluster_threshold,
        }

    def get_active_alerts(
        self,
        *,
        tenant_id: UUID,
        severity: str | None = None,
        alert_type: str | None = None,
        limit: int = 50,
    ) -> list[CostAlert]:
        """Get active (unresolved) alerts."""
        stmt = select(CostAlert).where(
            and_(
                CostAlert.tenant_id == tenant_id,
                CostAlert.is_resolved == False,
            )
        )

        if severity:
            stmt = stmt.where(CostAlert.severity == severity)
        if alert_type:
            stmt = stmt.where(CostAlert.alert_type == alert_type)

        stmt = stmt.order_by(CostAlert.created_at.desc()).limit(limit)

        result = self.db.execute(stmt)
        return list(result.scalars().all())

    def resolve_alert(
        self,
        *,
        alert_id: UUID,
        resolved_by: UUID,
        resolution_notes: str | None = None,
    ) -> CostAlert:
        """Resolve an alert."""
        stmt = select(CostAlert).where(CostAlert.id == alert_id)
        result = self.db.execute(stmt)
        alert = result.scalar_one()

        alert.is_resolved = True
        alert.resolved_at = datetime.now(UTC)
        alert.resolved_by = resolved_by
        alert.resolution_notes = resolution_notes

        self.db.commit()
        self.db.refresh(alert)
        return alert
