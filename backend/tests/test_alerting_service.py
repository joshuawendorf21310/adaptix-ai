"""Tests for alerting service."""
import pytest
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from core_app.services.alerting_service import AlertingService
from core_app.models.usage import UsageLedgerEntry
from core_app.models.budget import CostAlert


class TestAlertingService:
    """Test alerting service."""

    def test_detect_cost_spike_no_spike(self, db_session, test_tenant_id):
        """Test cost spike detection when no spike occurs."""
        service = AlertingService(db_session)

        # Add baseline usage (steady $10/hour)
        now = datetime.now(UTC)
        for i in range(24):
            entry = UsageLedgerEntry(
                tenant_id=test_tenant_id,
                module="test_module",
                task_type="test_task",
                cost=10.0,
                created_at=now - timedelta(hours=24-i),
            )
            db_session.add(entry)
        db_session.commit()

        result = service.detect_cost_spike(
            tenant_id=test_tenant_id,
            module="test_module",
            lookback_hours=24,
            spike_threshold=2.0,
        )

        assert result["is_spike"] is False
        assert "alert_id" not in result

    def test_detect_cost_spike_with_spike(self, db_session, test_tenant_id):
        """Test cost spike detection when spike occurs."""
        service = AlertingService(db_session)

        # Add baseline usage ($10/hour)
        now = datetime.now(UTC)
        for i in range(1, 24):
            entry = UsageLedgerEntry(
                tenant_id=test_tenant_id,
                module="test_module",
                task_type="test_task",
                cost=10.0,
                created_at=now - timedelta(hours=24-i),
            )
            db_session.add(entry)

        # Add spike in current hour ($100)
        spike_entry = UsageLedgerEntry(
            tenant_id=test_tenant_id,
            module="test_module",
            task_type="test_task",
            cost=100.0,
            created_at=now - timedelta(minutes=30),
        )
        db_session.add(spike_entry)
        db_session.commit()

        result = service.detect_cost_spike(
            tenant_id=test_tenant_id,
            module="test_module",
            lookback_hours=24,
            spike_threshold=2.0,
        )

        assert result["is_spike"] is True
        assert result["current_hour_cost"] == 100.0
        assert result["spike_multiplier"] > 2.0
        assert "alert_id" in result

    def test_detect_latency_regression_no_regression(self, db_session, test_tenant_id):
        """Test latency regression detection when no regression occurs."""
        service = AlertingService(db_session)

        # Add baseline latency (100ms p95)
        now = datetime.now(UTC)
        for i in range(24):
            for j in range(10):
                entry = UsageLedgerEntry(
                    tenant_id=test_tenant_id,
                    module="test_module",
                    task_type="test_task",
                    cost=1.0,
                    latency_ms=100.0 + (j * 5),  # 100-145ms range
                    created_at=now - timedelta(hours=24-i, minutes=j*5),
                )
                db_session.add(entry)
        db_session.commit()

        result = service.detect_latency_regression(
            tenant_id=test_tenant_id,
            module="test_module",
            lookback_hours=24,
            regression_threshold=1.5,
        )

        assert result["is_regression"] is False
        assert "alert_id" not in result

    def test_detect_quality_regression_high_error_rate(self, db_session, test_tenant_id):
        """Test quality regression detection with high error rate."""
        service = AlertingService(db_session)

        # Add 20 requests with 5 failures (25% error rate)
        now = datetime.now(UTC)
        for i in range(20):
            entry = UsageLedgerEntry(
                tenant_id=test_tenant_id,
                module="test_module",
                task_type="test_task",
                cost=1.0,
                success=(i >= 5),  # First 5 failed
                created_at=now - timedelta(hours=1, minutes=i*2),
            )
            db_session.add(entry)
        db_session.commit()

        result = service.detect_quality_regression(
            tenant_id=test_tenant_id,
            module="test_module",
            lookback_hours=24,
            error_rate_threshold=0.1,  # 10% threshold
        )

        assert result["is_regression"] is True
        assert result["error_rate"] == 0.25  # 25%
        assert result["total_requests"] == 20
        assert result["failed_requests"] == 5
        assert "alert_id" in result

    def test_detect_task_failure_clustering(self, db_session, test_tenant_id):
        """Test task failure clustering detection."""
        service = AlertingService(db_session)

        # Add clustered failures of same error type
        now = datetime.now(UTC)
        for i in range(10):
            entry = UsageLedgerEntry(
                tenant_id=test_tenant_id,
                module="test_module",
                task_type="test_task",
                cost=1.0,
                success=False,
                error_type="BudgetExceededError",
                created_at=now - timedelta(minutes=i*5),
            )
            db_session.add(entry)
        db_session.commit()

        result = service.detect_task_failure_clustering(
            tenant_id=test_tenant_id,
            lookback_hours=1,
            cluster_threshold=5,
        )

        assert result["has_clusters"] is True
        assert len(result["clusters"]) == 1
        assert result["clusters"][0]["error_type"] == "BudgetExceededError"
        assert result["clusters"][0]["failure_count"] == 10

    def test_get_active_alerts(self, db_session, test_tenant_id):
        """Test getting active alerts."""
        service = AlertingService(db_session)

        # Create some alerts
        alert1 = CostAlert(
            tenant_id=test_tenant_id,
            alert_type="cost_spike",
            severity="high",
            title="Cost Spike",
            message="Cost spike detected",
            is_resolved=False,
        )
        alert2 = CostAlert(
            tenant_id=test_tenant_id,
            alert_type="latency_regression",
            severity="medium",
            title="Latency Regression",
            message="Latency increased",
            is_resolved=False,
        )
        alert3 = CostAlert(
            tenant_id=test_tenant_id,
            alert_type="cost_spike",
            severity="high",
            title="Old Alert",
            message="Resolved",
            is_resolved=True,
        )

        db_session.add_all([alert1, alert2, alert3])
        db_session.commit()

        # Get all active alerts
        alerts = service.get_active_alerts(tenant_id=test_tenant_id)
        assert len(alerts) == 2

        # Filter by severity
        high_alerts = service.get_active_alerts(tenant_id=test_tenant_id, severity="high")
        assert len(high_alerts) == 1

        # Filter by alert type
        cost_alerts = service.get_active_alerts(tenant_id=test_tenant_id, alert_type="cost_spike")
        assert len(cost_alerts) == 1

    def test_resolve_alert(self, db_session, test_tenant_id, test_user_id):
        """Test resolving an alert."""
        service = AlertingService(db_session)

        # Create an alert
        alert = CostAlert(
            tenant_id=test_tenant_id,
            alert_type="cost_spike",
            severity="high",
            title="Cost Spike",
            message="Cost spike detected",
            is_resolved=False,
        )
        db_session.add(alert)
        db_session.commit()

        # Resolve the alert
        resolved = service.resolve_alert(
            alert_id=alert.id,
            resolved_by=test_user_id,
            resolution_notes="Fixed by reducing parallelism",
        )

        assert resolved.is_resolved is True
        assert resolved.resolved_by == test_user_id
        assert resolved.resolution_notes == "Fixed by reducing parallelism"
        assert resolved.resolved_at is not None
