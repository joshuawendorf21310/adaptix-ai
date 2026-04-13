"""Advanced analytics service for denial patterns, ROI tracking, and prompt performance."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, and_, func, case
from sqlalchemy.orm import Session

from core_app.models.usage import UsageLedgerEntry
from core_app.models.budget import CostAlert

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Advanced analytics for AI governance.

    Features:
    - Denial pattern detection and analysis
    - ROI tracking and cost-benefit analysis
    - Prompt performance analytics
    - Model effectiveness comparison
    - Cost optimization recommendations
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def analyze_denial_patterns(
        self,
        *,
        tenant_id: UUID,
        lookback_days: int = 30,
        min_occurrences: int = 3,
    ) -> dict[str, Any]:
        """
        Analyze patterns in claim denials.

        Args:
            tenant_id: Tenant ID
            lookback_days: Days to analyze
            min_occurrences: Minimum occurrences to identify pattern

        Returns:
            Denial patterns with recommendations
        """
        window_start = datetime.now(UTC) - timedelta(days=lookback_days)

        # Get failed billing intelligence tasks
        stmt = select(
            UsageLedgerEntry.metadata,
            func.count(UsageLedgerEntry.id).label("count"),
        ).where(
            and_(
                UsageLedgerEntry.tenant_id == tenant_id,
                UsageLedgerEntry.module == "billing",
                UsageLedgerEntry.created_at >= window_start,
                UsageLedgerEntry.success == False,
            )
        ).group_by(UsageLedgerEntry.error_type)

        result_rows = self.db.execute(stmt).all()

        # Analyze patterns
        patterns = []
        for metadata, count in result_rows:
            if count >= min_occurrences:
                # Extract denial reason from metadata if available
                denial_data = metadata or {}
                patterns.append({
                    "pattern_type": denial_data.get("denial_type", "unknown"),
                    "occurrences": count,
                    "common_codes": denial_data.get("common_codes", []),
                    "avg_claim_value": denial_data.get("avg_claim_value", 0.0),
                })

        # Calculate denial rate
        total_stmt = select(func.count(UsageLedgerEntry.id)).where(
            and_(
                UsageLedgerEntry.tenant_id == tenant_id,
                UsageLedgerEntry.module == "billing",
                UsageLedgerEntry.created_at >= window_start,
            )
        )
        total_claims = self.db.execute(total_stmt).scalar() or 0
        total_denials = sum(p["occurrences"] for p in patterns)
        denial_rate = total_denials / total_claims if total_claims > 0 else 0.0

        return {
            "period_days": lookback_days,
            "total_claims": total_claims,
            "total_denials": total_denials,
            "denial_rate": denial_rate,
            "patterns": patterns,
            "top_denial_reasons": sorted(patterns, key=lambda x: x["occurrences"], reverse=True)[:5],
        }

    def calculate_roi_metrics(
        self,
        *,
        tenant_id: UUID,
        module: str | None = None,
        lookback_days: int = 30,
    ) -> dict[str, Any]:
        """
        Calculate ROI metrics for AI usage.

        Args:
            tenant_id: Tenant ID
            module: Optional module filter
            lookback_days: Days to analyze

        Returns:
            ROI metrics including cost savings and efficiency gains
        """
        window_start = datetime.now(UTC) - timedelta(days=lookback_days)

        # Calculate total AI costs
        cost_stmt = select(func.sum(UsageLedgerEntry.cost)).where(
            and_(
                UsageLedgerEntry.tenant_id == tenant_id,
                UsageLedgerEntry.created_at >= window_start,
            )
        )
        if module:
            cost_stmt = cost_stmt.where(UsageLedgerEntry.module == module)

        total_ai_cost = self.db.execute(cost_stmt).scalar() or 0.0

        # Calculate task counts
        task_stmt = select(
            func.count(UsageLedgerEntry.id).label("total"),
            func.sum(case((UsageLedgerEntry.success == True, 1), else_=0)).label("successful"),
        ).where(
            and_(
                UsageLedgerEntry.tenant_id == tenant_id,
                UsageLedgerEntry.created_at >= window_start,
            )
        )
        if module:
            task_stmt = task_stmt.where(UsageLedgerEntry.module == module)

        task_result = self.db.execute(task_stmt).one()
        total_tasks = task_result.total or 0
        successful_tasks = task_result.successful or 0

        # Calculate average latency
        latency_stmt = select(func.avg(UsageLedgerEntry.latency_ms)).where(
            and_(
                UsageLedgerEntry.tenant_id == tenant_id,
                UsageLedgerEntry.created_at >= window_start,
                UsageLedgerEntry.latency_ms.isnot(None),
            )
        )
        if module:
            latency_stmt = latency_stmt.where(UsageLedgerEntry.module == module)

        avg_latency = self.db.execute(latency_stmt).scalar() or 0.0

        # Module-specific ROI calculations
        estimated_manual_cost = 0.0
        estimated_time_saved_hours = 0.0

        if module == "billing":
            # Billing: $15/claim manual review, 15 min/claim
            estimated_manual_cost = successful_tasks * 15.0
            estimated_time_saved_hours = (successful_tasks * 15) / 60.0

        elif module == "documentation":
            # Documentation: $25/report, 30 min/report
            estimated_manual_cost = successful_tasks * 25.0
            estimated_time_saved_hours = (successful_tasks * 30) / 60.0

        elif module == "protocol":
            # Protocol review: $30/review, 20 min/review
            estimated_manual_cost = successful_tasks * 30.0
            estimated_time_saved_hours = (successful_tasks * 20) / 60.0

        # Calculate ROI
        cost_savings = estimated_manual_cost - total_ai_cost
        roi_percentage = (cost_savings / total_ai_cost * 100) if total_ai_cost > 0 else 0.0

        return {
            "period_days": lookback_days,
            "module": module or "all",
            "total_ai_cost_usd": round(total_ai_cost, 2),
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "success_rate": successful_tasks / total_tasks if total_tasks > 0 else 0.0,
            "avg_latency_ms": round(avg_latency, 2),
            "estimated_manual_cost_usd": round(estimated_manual_cost, 2),
            "cost_savings_usd": round(cost_savings, 2),
            "roi_percentage": round(roi_percentage, 2),
            "time_saved_hours": round(estimated_time_saved_hours, 2),
            "cost_per_task": round(total_ai_cost / total_tasks, 4) if total_tasks > 0 else 0.0,
        }

    def analyze_prompt_performance(
        self,
        *,
        tenant_id: UUID,
        module: str | None = None,
        task_type: str | None = None,
        lookback_days: int = 7,
    ) -> dict[str, Any]:
        """
        Analyze prompt performance metrics.

        Args:
            tenant_id: Tenant ID
            module: Optional module filter
            task_type: Optional task type filter
            lookback_days: Days to analyze

        Returns:
            Prompt performance analytics
        """
        window_start = datetime.now(UTC) - timedelta(days=lookback_days)

        # Performance by task type
        perf_stmt = select(
            UsageLedgerEntry.task_type,
            func.count(UsageLedgerEntry.id).label("count"),
            func.avg(UsageLedgerEntry.cost).label("avg_cost"),
            func.avg(UsageLedgerEntry.latency_ms).label("avg_latency"),
            func.sum(case((UsageLedgerEntry.success == True, 1), else_=0)).label("successful"),
            func.avg(UsageLedgerEntry.tokens_input).label("avg_tokens_input"),
            func.avg(UsageLedgerEntry.tokens_output).label("avg_tokens_output"),
        ).where(
            and_(
                UsageLedgerEntry.tenant_id == tenant_id,
                UsageLedgerEntry.created_at >= window_start,
            )
        ).group_by(UsageLedgerEntry.task_type)

        if module:
            perf_stmt = perf_stmt.where(UsageLedgerEntry.module == module)
        if task_type:
            perf_stmt = perf_stmt.where(UsageLedgerEntry.task_type == task_type)

        result_rows = self.db.execute(perf_stmt).all()

        task_performance = []
        for row in result_rows:
            task_performance.append({
                "task_type": row.task_type,
                "total_executions": row.count,
                "success_rate": (row.successful / row.count) if row.count > 0 else 0.0,
                "avg_cost_usd": round(row.avg_cost or 0.0, 4),
                "avg_latency_ms": round(row.avg_latency or 0.0, 2),
                "avg_tokens_input": round(row.avg_tokens_input or 0.0, 0),
                "avg_tokens_output": round(row.avg_tokens_output or 0.0, 0),
            })

        # Overall metrics
        total_executions = sum(p["total_executions"] for p in task_performance)
        overall_success_rate = (
            sum(p["success_rate"] * p["total_executions"] for p in task_performance) / total_executions
            if total_executions > 0 else 0.0
        )

        # Identify best and worst performers
        sorted_by_success = sorted(task_performance, key=lambda x: x["success_rate"], reverse=True)
        sorted_by_cost = sorted(task_performance, key=lambda x: x["avg_cost_usd"])

        return {
            "period_days": lookback_days,
            "module": module or "all",
            "total_executions": total_executions,
            "overall_success_rate": round(overall_success_rate, 4),
            "task_performance": task_performance,
            "best_performers": sorted_by_success[:3],
            "worst_performers": sorted_by_success[-3:],
            "most_cost_efficient": sorted_by_cost[:3],
            "least_cost_efficient": sorted_by_cost[-3:],
        }

    def compare_model_effectiveness(
        self,
        *,
        tenant_id: UUID,
        lookback_days: int = 7,
    ) -> dict[str, Any]:
        """
        Compare effectiveness of different models.

        Args:
            tenant_id: Tenant ID
            lookback_days: Days to analyze

        Returns:
            Model comparison analytics
        """
        window_start = datetime.now(UTC) - timedelta(days=lookback_days)

        # Performance by model
        model_stmt = select(
            UsageLedgerEntry.model_id,
            func.count(UsageLedgerEntry.id).label("count"),
            func.avg(UsageLedgerEntry.cost).label("avg_cost"),
            func.avg(UsageLedgerEntry.latency_ms).label("avg_latency"),
            func.sum(case((UsageLedgerEntry.success == True, 1), else_=0)).label("successful"),
            func.sum(UsageLedgerEntry.tokens_input).label("total_tokens_input"),
            func.sum(UsageLedgerEntry.tokens_output).label("total_tokens_output"),
        ).where(
            and_(
                UsageLedgerEntry.tenant_id == tenant_id,
                UsageLedgerEntry.created_at >= window_start,
                UsageLedgerEntry.model_id.isnot(None),
            )
        ).group_by(UsageLedgerEntry.model_id)

        result_rows = self.db.execute(model_stmt).all()

        model_performance = []
        for row in result_rows:
            model_performance.append({
                "model_id": row.model_id,
                "total_executions": row.count,
                "success_rate": (row.successful / row.count) if row.count > 0 else 0.0,
                "avg_cost_usd": round(row.avg_cost or 0.0, 4),
                "avg_latency_ms": round(row.avg_latency or 0.0, 2),
                "total_tokens": (row.total_tokens_input or 0) + (row.total_tokens_output or 0),
                "cost_per_1k_tokens": round(
                    (row.avg_cost or 0.0) * 1000 / ((row.total_tokens_input or 0) + (row.total_tokens_output or 0))
                    if ((row.total_tokens_input or 0) + (row.total_tokens_output or 0)) > 0 else 0.0,
                    4
                ),
            })

        # Sort by different metrics
        sorted_by_success = sorted(model_performance, key=lambda x: x["success_rate"], reverse=True)
        sorted_by_cost = sorted(model_performance, key=lambda x: x["avg_cost_usd"])
        sorted_by_latency = sorted(model_performance, key=lambda x: x["avg_latency_ms"])

        return {
            "period_days": lookback_days,
            "models_compared": len(model_performance),
            "model_performance": model_performance,
            "highest_success_rate": sorted_by_success[0] if sorted_by_success else None,
            "lowest_cost": sorted_by_cost[0] if sorted_by_cost else None,
            "lowest_latency": sorted_by_latency[0] if sorted_by_latency else None,
        }

    def generate_cost_optimization_recommendations(
        self,
        *,
        tenant_id: UUID,
        lookback_days: int = 7,
    ) -> dict[str, Any]:
        """
        Generate cost optimization recommendations.

        Args:
            tenant_id: Tenant ID
            lookback_days: Days to analyze

        Returns:
            Cost optimization recommendations
        """
        # Get prompt performance data
        prompt_perf = self.analyze_prompt_performance(
            tenant_id=tenant_id,
            lookback_days=lookback_days,
        )

        # Get model comparison data
        model_comp = self.compare_model_effectiveness(
            tenant_id=tenant_id,
            lookback_days=lookback_days,
        )

        recommendations = []

        # Check for expensive task types with low success rates
        for task in prompt_perf["task_performance"]:
            if task["success_rate"] < 0.8 and task["avg_cost_usd"] > 0.05:
                recommendations.append({
                    "type": "improve_prompt_quality",
                    "priority": "high",
                    "task_type": task["task_type"],
                    "reason": f"Low success rate ({task['success_rate']:.1%}) with high cost (${task['avg_cost_usd']:.4f})",
                    "potential_savings_usd": task["avg_cost_usd"] * task["total_executions"] * 0.3,
                })

        # Check for model inefficiencies
        if model_comp["models_compared"] > 1:
            highest_cost_model = max(model_comp["model_performance"], key=lambda x: x["avg_cost_usd"])
            lowest_cost_model = min(model_comp["model_performance"], key=lambda x: x["avg_cost_usd"])

            if highest_cost_model["avg_cost_usd"] > lowest_cost_model["avg_cost_usd"] * 2:
                recommendations.append({
                    "type": "switch_model",
                    "priority": "medium",
                    "current_model": highest_cost_model["model_id"],
                    "suggested_model": lowest_cost_model["model_id"],
                    "reason": f"Cost reduction of {((highest_cost_model['avg_cost_usd'] - lowest_cost_model['avg_cost_usd']) / highest_cost_model['avg_cost_usd'] * 100):.1f}%",
                    "potential_savings_usd": (highest_cost_model["avg_cost_usd"] - lowest_cost_model["avg_cost_usd"]) * highest_cost_model["total_executions"],
                })

        # Check for high token usage
        for task in prompt_perf["task_performance"]:
            if task["avg_tokens_input"] > 5000:
                recommendations.append({
                    "type": "reduce_prompt_size",
                    "priority": "low",
                    "task_type": task["task_type"],
                    "reason": f"High input tokens ({task['avg_tokens_input']:.0f} avg)",
                    "potential_savings_usd": task["avg_cost_usd"] * task["total_executions"] * 0.2,
                })

        # Sort by potential savings
        recommendations.sort(key=lambda x: x.get("potential_savings_usd", 0), reverse=True)

        total_potential_savings = sum(r.get("potential_savings_usd", 0) for r in recommendations)

        return {
            "period_days": lookback_days,
            "total_recommendations": len(recommendations),
            "total_potential_savings_usd": round(total_potential_savings, 2),
            "recommendations": recommendations,
        }
