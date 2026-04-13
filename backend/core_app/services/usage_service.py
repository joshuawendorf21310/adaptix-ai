"""Usage tracking and aggregation service."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from core_app.models.usage import UsageLedgerEntry, UsageAggregation
from core_app.models.execution import ExecutionRequest, ExecutionResult


class UsageService:
    """Service for tracking and aggregating AI usage metrics."""

    def __init__(self, db: Session):
        self.db = db

    def record_usage(
        self,
        *,
        tenant_id: UUID,
        request_id: UUID,
        user_id: UUID,
        module: str | None,
        task_type: str | None,
        model_provider: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        latency_ms: int | None,
        cost: float,
        cost_currency: str = "USD",
        is_estimated: bool = True,
        success: bool = True,
        error_type: str | None = None,
    ) -> UsageLedgerEntry:
        """
        Record a usage entry in the ledger.

        Args:
            tenant_id: Tenant identifier
            request_id: Execution request ID
            user_id: User who made the request
            module: AI module (command, field, flow, etc.)
            task_type: Specific task type
            model_provider: Provider name (aws-bedrock, etc.)
            model_id: Model identifier
            input_tokens: Input token count
            output_tokens: Output token count
            total_tokens: Total token count
            latency_ms: Request latency in milliseconds
            cost: Estimated cost
            cost_currency: Currency code
            is_estimated: Whether cost is estimated or actual
            success: Whether request succeeded
            error_type: Error type if failed

        Returns:
            Created usage ledger entry
        """
        entry = UsageLedgerEntry(
            tenant_id=tenant_id,
            request_id=request_id,
            user_id=user_id,
            module=module,
            task_type=task_type,
            model_provider=model_provider,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            cost=cost,
            cost_currency=cost_currency,
            is_estimated=is_estimated,
            success=success,
            error_type=error_type,
            usage_date=date.today(),
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def get_daily_usage(
        self,
        tenant_id: UUID,
        usage_date: date | None = None,
    ) -> dict[str, Any]:
        """
        Get aggregated usage for a specific date.

        Args:
            tenant_id: Tenant identifier
            usage_date: Date to query (defaults to today)

        Returns:
            Dictionary with aggregated metrics
        """
        if usage_date is None:
            usage_date = date.today()

        # Query usage entries for the date
        query = select(
            func.count(UsageLedgerEntry.id).label("total_requests"),
            func.sum(UsageLedgerEntry.total_tokens).label("total_tokens"),
            func.sum(UsageLedgerEntry.input_tokens).label("total_input_tokens"),
            func.sum(UsageLedgerEntry.output_tokens).label("total_output_tokens"),
            func.sum(UsageLedgerEntry.cost).label("total_cost"),
            func.avg(UsageLedgerEntry.latency_ms).label("avg_latency"),
            func.count(UsageLedgerEntry.id).filter(UsageLedgerEntry.success == True).label("successful_requests"),
            func.count(UsageLedgerEntry.id).filter(UsageLedgerEntry.success == False).label("failed_requests"),
        ).where(
            and_(
                UsageLedgerEntry.tenant_id == tenant_id,
                UsageLedgerEntry.usage_date == usage_date,
            )
        )

        result = self.db.execute(query).one()

        return {
            "usage_date": usage_date.isoformat(),
            "total_requests": result.total_requests or 0,
            "total_tokens": result.total_tokens or 0,
            "total_input_tokens": result.total_input_tokens or 0,
            "total_output_tokens": result.total_output_tokens or 0,
            "total_cost": float(result.total_cost or 0.0),
            "avg_latency_ms": float(result.avg_latency or 0.0),
            "successful_requests": result.successful_requests or 0,
            "failed_requests": result.failed_requests or 0,
        }

    def get_usage_by_module(
        self,
        tenant_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Get usage breakdown by module for a date range."""
        query = (
            select(
                UsageLedgerEntry.module,
                func.count(UsageLedgerEntry.id).label("request_count"),
                func.sum(UsageLedgerEntry.total_tokens).label("total_tokens"),
                func.sum(UsageLedgerEntry.cost).label("total_cost"),
            )
            .where(
                and_(
                    UsageLedgerEntry.tenant_id == tenant_id,
                    UsageLedgerEntry.usage_date >= start_date,
                    UsageLedgerEntry.usage_date <= end_date,
                )
            )
            .group_by(UsageLedgerEntry.module)
            .order_by(func.sum(UsageLedgerEntry.total_tokens).desc())
        )

        results = self.db.execute(query).all()

        return [
            {
                "module": row.module or "unknown",
                "request_count": row.request_count or 0,
                "total_tokens": row.total_tokens or 0,
                "total_cost": float(row.total_cost or 0.0),
            }
            for row in results
        ]

    def get_latency_percentiles(
        self,
        tenant_id: UUID,
        usage_date: date | None = None,
    ) -> dict[str, float]:
        """
        Calculate latency percentiles for a date.

        Args:
            tenant_id: Tenant identifier
            usage_date: Date to query (defaults to today)

        Returns:
            Dictionary with p50, p95, p99 latency values
        """
        if usage_date is None:
            usage_date = date.today()

        # Get all latencies for the date
        query = (
            select(UsageLedgerEntry.latency_ms)
            .where(
                and_(
                    UsageLedgerEntry.tenant_id == tenant_id,
                    UsageLedgerEntry.usage_date == usage_date,
                    UsageLedgerEntry.latency_ms.isnot(None),
                )
            )
            .order_by(UsageLedgerEntry.latency_ms)
        )

        latencies = [row[0] for row in self.db.execute(query).all()]

        if not latencies:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}

        def percentile(data: list[int], p: float) -> float:
            if not data:
                return 0.0
            k = (len(data) - 1) * p
            f = int(k)
            c = int(k) + 1
            if c >= len(data):
                return float(data[-1])
            return float(data[f] + (data[c] - data[f]) * (k - f))

        return {
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
            "p99": percentile(latencies, 0.99),
        }

    def aggregate_daily_usage(
        self,
        tenant_id: UUID,
        usage_date: date,
    ) -> UsageAggregation:
        """
        Create or update daily aggregation record.

        This can be run as a batch job to pre-compute aggregations.
        """
        # Get usage stats for the date
        usage = self.get_daily_usage(tenant_id, usage_date)
        percentiles = self.get_latency_percentiles(tenant_id, usage_date)

        # Check if aggregation already exists
        existing = self.db.execute(
            select(UsageAggregation).where(
                and_(
                    UsageAggregation.tenant_id == tenant_id,
                    UsageAggregation.aggregation_date == usage_date,
                    UsageAggregation.module.is_(None),  # Overall aggregation
                )
            )
        ).scalar_one_or_none()

        if existing:
            # Update existing
            existing.total_requests = usage["total_requests"]
            existing.successful_requests = usage["successful_requests"]
            existing.failed_requests = usage["failed_requests"]
            existing.total_input_tokens = usage["total_input_tokens"]
            existing.total_output_tokens = usage["total_output_tokens"]
            existing.total_tokens = usage["total_tokens"]
            existing.total_cost = usage["total_cost"]
            existing.avg_latency_ms = usage["avg_latency_ms"]
            existing.p50_latency_ms = percentiles["p50"]
            existing.p95_latency_ms = percentiles["p95"]
            existing.p99_latency_ms = percentiles["p99"]
            existing.updated_at = datetime.now(UTC)
            return existing
        else:
            # Create new
            aggregation = UsageAggregation(
                tenant_id=tenant_id,
                aggregation_date=usage_date,
                module=None,  # Overall aggregation
                model_provider="all",
                total_requests=usage["total_requests"],
                successful_requests=usage["successful_requests"],
                failed_requests=usage["failed_requests"],
                total_input_tokens=usage["total_input_tokens"],
                total_output_tokens=usage["total_output_tokens"],
                total_tokens=usage["total_tokens"],
                total_cost=usage["total_cost"],
                avg_latency_ms=usage["avg_latency_ms"],
                p50_latency_ms=percentiles["p50"],
                p95_latency_ms=percentiles["p95"],
                p99_latency_ms=percentiles["p99"],
            )
            self.db.add(aggregation)
            self.db.flush()
            return aggregation
