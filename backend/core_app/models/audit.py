"""Audit event model."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core_app.database import Base


class AuditEvent(Base):
    """
    Immutable audit log of governance actions and system events.

    All prompt activations, policy changes, review actions, and
    security events are recorded here for founder oversight.
    """
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Event classification
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Types: prompt_created, prompt_activated, prompt_deactivated, prompt_archived,
    #        policy_created, policy_updated, review_approved, review_rejected,
    #        execution_failed, auth_failed, guardrail_violation, etc.

    event_category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Categories: prompt, policy, execution, security, system

    # Actor
    actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    actor_role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actor_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # Event details
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Entity references
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    entity_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)

    # Before/after state for changes
    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Severity
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    # Severity: debug, info, warning, error, critical

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )

    def __repr__(self) -> str:
        return f"<AuditEvent {self.event_type} {self.severity}>"
