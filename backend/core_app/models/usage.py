"""Usage tracking and aggregation models."""
from __future__ import annotations

from datetime import UTC, datetime, date
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core_app.database import Base


class UsageLedgerEntry(Base):
    """
    Individual usage ledger entry for metering and billing.

    Each AI execution creates a ledger entry for cost and usage tracking.
    """
    __tablename__ = "usage_ledger_entries"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # References
    request_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("execution_requests.id"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Dimensions
    module: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    task_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    model_provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Usage metrics
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Performance
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Cost
    cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cost_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    is_estimated: Mapped[bool] = mapped_column(nullable=False, default=True)

    # Outcome
    success: Mapped[bool] = mapped_column(nullable=False, index=True)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Timestamps
    usage_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )

    def __repr__(self) -> str:
        return f"<UsageLedgerEntry {self.total_tokens} tokens ${self.cost:.4f}>"


class UsageAggregation(Base):
    """
    Pre-aggregated usage rollups for fast dashboard queries.

    Aggregates usage by tenant, date, module, and provider.
    """
    __tablename__ = "usage_aggregations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Aggregation dimensions
    aggregation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    module: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    model_provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Counts
    total_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Token usage
    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Cost
    total_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Latency metrics
    avg_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    p50_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    p95_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    p99_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC)
    )

    def __repr__(self) -> str:
        return f"<UsageAggregation {self.aggregation_date} {self.total_requests} requests>"
