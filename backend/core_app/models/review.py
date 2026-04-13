"""Review queue and approval models."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core_app.database import Base


class ReviewQueueItem(Base):
    """
    Items pending review in the governance queue.

    Prompts, policies, high-risk outputs, and threshold violations
    can be routed to the review queue for manual approval.
    """
    __tablename__ = "review_queue_items"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Item type
    item_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Types: prompt_version, policy_change, execution_output, threshold_violation, incident

    # Related entity
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Request details
    submitted_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    # Status: pending, approved, rejected, changes_requested, resolved

    # Priority
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    # Priority: low, normal, high, critical

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    actions: Mapped[list["ReviewAction"]] = relationship(
        "ReviewAction", back_populates="queue_item", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ReviewQueueItem {self.item_type} {self.status}>"


class ReviewAction(Base):
    """
    Actions taken on review queue items.

    Records all approvals, rejections, and feedback on queued items.
    """
    __tablename__ = "review_actions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    queue_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("review_queue_items.id"), nullable=False, index=True
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Action
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Types: approve, reject, request_changes, comment, resolve

    # Actor
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    actor_role: Mapped[str] = mapped_column(String(100), nullable=False)

    # Details
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    # Relationships
    queue_item: Mapped["ReviewQueueItem"] = relationship("ReviewQueueItem", back_populates="actions")

    def __repr__(self) -> str:
        return f"<ReviewAction {self.action_type}>"
