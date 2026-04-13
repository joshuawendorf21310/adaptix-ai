"""Review queue service for AI governance workflows."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import Session

from core_app.models.review import ReviewQueueItem, ReviewAction
from core_app.models.execution import ExecutionRequest, ExecutionResult

logger = logging.getLogger(__name__)


class ReviewService:
    """
    Service for managing AI review workflows.

    Features:
    - Review queue management
    - Assignment and escalation
    - Approval/rejection workflows
    - Before/after comparison
    - Domain-specific review rules
    - Audit trails
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def queue_for_review(
        self,
        *,
        tenant_id: UUID,
        execution_request_id: UUID,
        review_reason: str,
        review_type: str,
        priority: str = "normal",
        assigned_to: UUID | None = None,
        context: dict[str, Any] | None = None,
    ) -> ReviewQueueItem:
        """Queue an execution for manual review."""
        item = ReviewQueueItem(
            tenant_id=tenant_id,
            execution_request_id=execution_request_id,
            review_reason=review_reason,
            review_type=review_type,
            priority=priority,
            assigned_to=assigned_to,
            context=context or {},
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_review_queue(
        self,
        *,
        tenant_id: UUID,
        review_type: str | None = None,
        priority: str | None = None,
        assigned_to: UUID | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ReviewQueueItem]:
        """Get review queue items with filters."""
        stmt = select(ReviewQueueItem).where(ReviewQueueItem.tenant_id == tenant_id)

        if review_type:
            stmt = stmt.where(ReviewQueueItem.review_type == review_type)
        if priority:
            stmt = stmt.where(ReviewQueueItem.priority == priority)
        if assigned_to:
            stmt = stmt.where(ReviewQueueItem.assigned_to == assigned_to)
        if status:
            stmt = stmt.where(ReviewQueueItem.status == status)
        else:
            # Default to pending items
            stmt = stmt.where(ReviewQueueItem.status == "pending")

        stmt = stmt.order_by(
            ReviewQueueItem.priority.desc(),
            ReviewQueueItem.created_at.asc()
        ).limit(limit).offset(offset)

        result = self.db.execute(stmt)
        return list(result.scalars().all())

    def assign_review(
        self,
        *,
        review_id: UUID,
        assigned_to: UUID,
        assigned_by: UUID,
    ) -> ReviewQueueItem:
        """Assign a review to a user."""
        stmt = select(ReviewQueueItem).where(ReviewQueueItem.id == review_id)
        result = self.db.execute(stmt)
        item = result.scalar_one()

        item.assigned_to = assigned_to
        item.assigned_at = datetime.now(UTC)
        item.assigned_by = assigned_by
        self.db.commit()
        self.db.refresh(item)
        return item

    def approve_review(
        self,
        *,
        review_id: UUID,
        reviewer_id: UUID,
        notes: str | None = None,
        modifications: dict[str, Any] | None = None,
    ) -> ReviewQueueItem:
        """Approve a review item."""
        stmt = select(ReviewQueueItem).where(ReviewQueueItem.id == review_id)
        result = self.db.execute(stmt)
        item = result.scalar_one()

        # Update review item
        item.status = "approved"
        item.reviewed_at = datetime.now(UTC)
        item.reviewed_by = reviewer_id
        item.reviewer_notes = notes

        # Create review action
        action = ReviewAction(
            review_queue_item_id=item.id,
            tenant_id=item.tenant_id,
            action_type="approve",
            actor_id=reviewer_id,
            notes=notes,
            modifications=modifications,
        )
        self.db.add(action)
        self.db.commit()
        self.db.refresh(item)
        return item

    def reject_review(
        self,
        *,
        review_id: UUID,
        reviewer_id: UUID,
        rejection_reason: str,
        notes: str | None = None,
    ) -> ReviewQueueItem:
        """Reject a review item."""
        stmt = select(ReviewQueueItem).where(ReviewQueueItem.id == review_id)
        result = self.db.execute(stmt)
        item = result.scalar_one()

        # Update review item
        item.status = "rejected"
        item.reviewed_at = datetime.now(UTC)
        item.reviewed_by = reviewer_id
        item.reviewer_notes = notes
        item.rejection_reason = rejection_reason

        # Create review action
        action = ReviewAction(
            review_queue_item_id=item.id,
            tenant_id=item.tenant_id,
            action_type="reject",
            actor_id=reviewer_id,
            notes=notes,
            rejection_reason=rejection_reason,
        )
        self.db.add(action)
        self.db.commit()
        self.db.refresh(item)
        return item

    def request_changes(
        self,
        *,
        review_id: UUID,
        reviewer_id: UUID,
        requested_changes: str,
        notes: str | None = None,
    ) -> ReviewQueueItem:
        """Request changes to a review item."""
        stmt = select(ReviewQueueItem).where(ReviewQueueItem.id == review_id)
        result = self.db.execute(stmt)
        item = result.scalar_one()

        # Update review item
        item.status = "changes_requested"
        item.reviewed_at = datetime.now(UTC)
        item.reviewed_by = reviewer_id
        item.reviewer_notes = notes

        # Create review action
        action = ReviewAction(
            review_queue_item_id=item.id,
            tenant_id=item.tenant_id,
            action_type="request_changes",
            actor_id=reviewer_id,
            notes=notes,
            requested_changes=requested_changes,
        )
        self.db.add(action)
        self.db.commit()
        self.db.refresh(item)
        return item

    def escalate_review(
        self,
        *,
        review_id: UUID,
        escalated_by: UUID,
        escalation_reason: str,
        escalate_to: UUID | None = None,
    ) -> ReviewQueueItem:
        """Escalate a review item."""
        stmt = select(ReviewQueueItem).where(ReviewQueueItem.id == review_id)
        result = self.db.execute(stmt)
        item = result.scalar_one()

        # Update review item
        item.priority = "high"  # Escalated items become high priority
        item.is_escalated = True
        item.escalated_at = datetime.now(UTC)
        item.escalated_by = escalated_by
        if escalate_to:
            item.assigned_to = escalate_to

        # Create review action
        action = ReviewAction(
            review_queue_item_id=item.id,
            tenant_id=item.tenant_id,
            action_type="escalate",
            actor_id=escalated_by,
            notes=escalation_reason,
        )
        self.db.add(action)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_review_history(
        self,
        *,
        review_id: UUID,
    ) -> list[ReviewAction]:
        """Get full history of actions for a review item."""
        stmt = select(ReviewAction).where(
            ReviewAction.review_queue_item_id == review_id
        ).order_by(ReviewAction.created_at.asc())

        result = self.db.execute(stmt)
        return list(result.scalars().all())

    def get_review_metrics(
        self,
        *,
        tenant_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Get review queue metrics."""
        if not start_date:
            start_date = datetime.now(UTC) - timedelta(days=30)
        if not end_date:
            end_date = datetime.now(UTC)

        # Pending reviews
        pending_stmt = select(func.count(ReviewQueueItem.id)).where(
            and_(
                ReviewQueueItem.tenant_id == tenant_id,
                ReviewQueueItem.status == "pending",
            )
        )
        pending_count = self.db.execute(pending_stmt).scalar() or 0

        # Average review time
        avg_time_stmt = select(
            func.avg(
                func.extract("epoch", ReviewQueueItem.reviewed_at - ReviewQueueItem.created_at)
            )
        ).where(
            and_(
                ReviewQueueItem.tenant_id == tenant_id,
                ReviewQueueItem.reviewed_at.isnot(None),
                ReviewQueueItem.created_at >= start_date,
                ReviewQueueItem.created_at <= end_date,
            )
        )
        avg_time_seconds = self.db.execute(avg_time_stmt).scalar() or 0

        # Approval rate
        total_reviewed_stmt = select(func.count(ReviewQueueItem.id)).where(
            and_(
                ReviewQueueItem.tenant_id == tenant_id,
                ReviewQueueItem.reviewed_at.isnot(None),
                ReviewQueueItem.created_at >= start_date,
                ReviewQueueItem.created_at <= end_date,
            )
        )
        total_reviewed = self.db.execute(total_reviewed_stmt).scalar() or 0

        approved_stmt = select(func.count(ReviewQueueItem.id)).where(
            and_(
                ReviewQueueItem.tenant_id == tenant_id,
                ReviewQueueItem.status == "approved",
                ReviewQueueItem.created_at >= start_date,
                ReviewQueueItem.created_at <= end_date,
            )
        )
        approved_count = self.db.execute(approved_stmt).scalar() or 0

        approval_rate = (approved_count / total_reviewed * 100) if total_reviewed > 0 else 0

        # Escalated reviews
        escalated_stmt = select(func.count(ReviewQueueItem.id)).where(
            and_(
                ReviewQueueItem.tenant_id == tenant_id,
                ReviewQueueItem.is_escalated == True,
                ReviewQueueItem.created_at >= start_date,
                ReviewQueueItem.created_at <= end_date,
            )
        )
        escalated_count = self.db.execute(escalated_stmt).scalar() or 0

        # By review type
        by_type_stmt = select(
            ReviewQueueItem.review_type,
            func.count(ReviewQueueItem.id).label("count")
        ).where(
            and_(
                ReviewQueueItem.tenant_id == tenant_id,
                ReviewQueueItem.created_at >= start_date,
                ReviewQueueItem.created_at <= end_date,
            )
        ).group_by(ReviewQueueItem.review_type)

        by_type_result = self.db.execute(by_type_stmt)
        by_type = {row[0]: row[1] for row in by_type_result}

        return {
            "pending_count": pending_count,
            "avg_review_time_seconds": avg_time_seconds,
            "avg_review_time_hours": avg_time_seconds / 3600 if avg_time_seconds else 0,
            "total_reviewed": total_reviewed,
            "approved_count": approved_count,
            "approval_rate_pct": approval_rate,
            "escalated_count": escalated_count,
            "by_review_type": by_type,
        }

    def auto_escalate_stale_reviews(
        self,
        *,
        tenant_id: UUID,
        age_hours: int = 24,
        escalate_to: UUID | None = None,
    ) -> list[ReviewQueueItem]:
        """Auto-escalate reviews older than threshold."""
        threshold = datetime.now(UTC) - timedelta(hours=age_hours)

        stmt = select(ReviewQueueItem).where(
            and_(
                ReviewQueueItem.tenant_id == tenant_id,
                ReviewQueueItem.status == "pending",
                ReviewQueueItem.is_escalated == False,
                ReviewQueueItem.created_at < threshold,
            )
        )

        result = self.db.execute(stmt)
        stale_items = list(result.scalars().all())

        escalated = []
        for item in stale_items:
            item.priority = "high"
            item.is_escalated = True
            item.escalated_at = datetime.now(UTC)
            item.escalated_by = None  # System escalation
            if escalate_to:
                item.assigned_to = escalate_to

            action = ReviewAction(
                review_queue_item_id=item.id,
                tenant_id=item.tenant_id,
                action_type="escalate",
                actor_id=None,  # System action
                notes=f"Auto-escalated after {age_hours} hours without review",
            )
            self.db.add(action)
            escalated.append(item)

        if escalated:
            self.db.commit()

        return escalated
