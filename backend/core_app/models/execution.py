"""Execution request and result models."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core_app.database import Base


class ExecutionRequest(Base):
    """
    Record of an AI execution request.

    Tracks all inputs, configuration, and metadata for AI provider calls.
    """
    __tablename__ = "execution_requests"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Request identity
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Prompt reference
    prompt_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("prompt_definitions.id"), nullable=True, index=True
    )
    prompt_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("prompt_versions.id"), nullable=True, index=True
    )

    # Request content
    module: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    task_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    input_context: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Configuration
    model_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Policy enforcement
    guardrails_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    pii_masked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    policy_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ai_policies.id"), nullable=True
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", index=True
    )  # pending, queued, running, completed, failed, cancelled

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    result: Mapped["ExecutionResult | None"] = relationship(
        "ExecutionResult", back_populates="request", uselist=False
    )

    def __repr__(self) -> str:
        return f"<ExecutionRequest {self.id} {self.status}>"


class ExecutionResult(Base):
    """
    Result of an AI execution.

    Stores outputs, metrics, costs, and any warnings or errors.
    """
    __tablename__ = "execution_results"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("execution_requests.id"), nullable=False, unique=True, index=True
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Result content
    output: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Success/failure
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Usage metrics
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Performance
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Cost
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # Guardrails results
    phi_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    guardrail_violations: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    warnings: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # Quality metrics
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hallucination_risk: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Metadata
    provider_request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    # Relationships
    request: Mapped["ExecutionRequest"] = relationship("ExecutionRequest", back_populates="result")

    def __repr__(self) -> str:
        return f"<ExecutionResult {'success' if self.success else 'failed'}>"
