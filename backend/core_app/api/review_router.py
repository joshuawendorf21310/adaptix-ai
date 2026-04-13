"""Review queue API router."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Any
from uuid import UUID

from core_app.api.dependencies import get_db, get_current_user
from core_app.services.review_service import ReviewService

router = APIRouter(prefix="/api/v1/review", tags=["review"])


class ApproveReviewRequest(BaseModel):
    """Request to approve a review."""
    notes: str | None = Field(None, description="Reviewer notes")
    modifications: dict[str, Any] | None = Field(None, description="Any modifications made")


class RejectReviewRequest(BaseModel):
    """Request to reject a review."""
    rejection_reason: str = Field(..., description="Reason for rejection")
    notes: str | None = Field(None, description="Additional notes")


class RequestChangesRequest(BaseModel):
    """Request to request changes."""
    requested_changes: str = Field(..., description="Description of requested changes")
    notes: str | None = Field(None, description="Additional notes")


class EscalateReviewRequest(BaseModel):
    """Request to escalate a review."""
    escalation_reason: str = Field(..., description="Reason for escalation")
    escalate_to: UUID | None = Field(None, description="User to escalate to")


@router.get("/queue")
def get_review_queue(
    review_type: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Get review queue items."""
    service = ReviewService(db)
    tenant_id = UUID(current_user["tenant_id"])

    items = service.get_review_queue(
        tenant_id=tenant_id,
        review_type=review_type,
        priority=priority,
        status=status,
        limit=limit,
        offset=offset,
    )

    return {
        "items": [
            {
                "id": str(item.id),
                "execution_request_id": str(item.execution_request_id),
                "review_reason": item.review_reason,
                "review_type": item.review_type,
                "priority": item.priority,
                "status": item.status,
                "assigned_to": str(item.assigned_to) if item.assigned_to else None,
                "is_escalated": item.is_escalated,
                "created_at": item.created_at.isoformat(),
            }
            for item in items
        ],
        "total": len(items),
        "limit": limit,
        "offset": offset,
    }


@router.post("/{review_id}/approve")
def approve_review(
    review_id: UUID,
    request: ApproveReviewRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Approve a review item."""
    service = ReviewService(db)
    user_id = UUID(current_user["user_id"])

    try:
        item = service.approve_review(
            review_id=review_id,
            reviewer_id=user_id,
            notes=request.notes,
            modifications=request.modifications,
        )

        return {
            "review_id": str(item.id),
            "status": "approved",
            "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
        }
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{review_id}/reject")
def reject_review(
    review_id: UUID,
    request: RejectReviewRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Reject a review item."""
    service = ReviewService(db)
    user_id = UUID(current_user["user_id"])

    try:
        item = service.reject_review(
            review_id=review_id,
            reviewer_id=user_id,
            rejection_reason=request.rejection_reason,
            notes=request.notes,
        )

        return {
            "review_id": str(item.id),
            "status": "rejected",
            "rejection_reason": item.rejection_reason,
        }
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{review_id}/request-changes")
def request_changes(
    review_id: UUID,
    request: RequestChangesRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Request changes to a review item."""
    service = ReviewService(db)
    user_id = UUID(current_user["user_id"])

    try:
        item = service.request_changes(
            review_id=review_id,
            reviewer_id=user_id,
            requested_changes=request.requested_changes,
            notes=request.notes,
        )

        return {
            "review_id": str(item.id),
            "status": "changes_requested",
        }
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{review_id}/escalate")
def escalate_review(
    review_id: UUID,
    request: EscalateReviewRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Escalate a review item."""
    service = ReviewService(db)
    user_id = UUID(current_user["user_id"])

    try:
        item = service.escalate_review(
            review_id=review_id,
            escalated_by=user_id,
            escalation_reason=request.escalation_reason,
            escalate_to=request.escalate_to,
        )

        return {
            "review_id": str(item.id),
            "is_escalated": item.is_escalated,
            "escalated_at": item.escalated_at.isoformat() if item.escalated_at else None,
        }
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{review_id}/history")
def get_review_history(
    review_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Get review action history."""
    service = ReviewService(db)

    try:
        actions = service.get_review_history(review_id=review_id)

        return {
            "review_id": str(review_id),
            "actions": [
                {
                    "id": str(action.id),
                    "action_type": action.action_type,
                    "actor_id": str(action.actor_id) if action.actor_id else None,
                    "notes": action.notes,
                    "created_at": action.created_at.isoformat(),
                }
                for action in actions
            ],
            "total": len(actions),
        }
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/metrics")
def get_review_metrics(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Get review queue metrics."""
    service = ReviewService(db)
    tenant_id = UUID(current_user["tenant_id"])

    metrics = service.get_review_metrics(tenant_id=tenant_id)

    return metrics
