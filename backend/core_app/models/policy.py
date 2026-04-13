"""AI policy and governance models."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core_app.database import Base


class AiPolicy(Base):
    """
    AI governance policy configuration.

    Policies control guardrails, rate limits, provider restrictions,
    and other governance controls for AI execution.
    """
    __tablename__ = "ai_policies"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Identity
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Policy controls
    pii_masking_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    content_guardrails_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    daily_token_budget: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Provider configuration
    allowed_providers: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    fallback_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Review requirements
    require_manual_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_threshold_confidence: Mapped[float | None] = mapped_column(nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    # Metadata
    created_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    updated_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC)
    )

    # Relationships
    revisions: Mapped[list["PolicyRevision"]] = relationship(
        "PolicyRevision", back_populates="policy", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AiPolicy {self.name}>"


class PolicyRevision(Base):
    """
    Historical revision of a policy for audit trail.
    """
    __tablename__ = "policy_revisions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    policy_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ai_policies.id"), nullable=False, index=True
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Revision info
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Snapshot of policy state
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Metadata
    created_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    # Relationships
    policy: Mapped["AiPolicy"] = relationship("AiPolicy", back_populates="revisions")

    def __repr__(self) -> str:
        return f"<PolicyRevision r{self.revision_number}>"
