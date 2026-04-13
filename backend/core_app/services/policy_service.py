"""Policy management service."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from core_app.models.policy import AiPolicy, PolicyRevision
from core_app.services.audit_service import AuditService


class PolicyService:
    """Service for managing AI governance policies."""

    def __init__(self, db: Session, audit_service: AuditService | None = None):
        self.db = db
        self.audit_service = audit_service or AuditService(db)

    def create_policy(
        self,
        *,
        tenant_id: UUID,
        name: str,
        description: str | None,
        pii_masking_enabled: bool = True,
        content_guardrails_enabled: bool = True,
        rate_limit_per_minute: int = 100,
        daily_token_budget: int | None = None,
        allowed_providers: list[str] | None = None,
        fallback_enabled: bool = False,
        require_manual_review: bool = False,
        review_threshold_confidence: float | None = None,
        created_by: UUID,
    ) -> AiPolicy:
        """Create a new AI policy."""
        policy = AiPolicy(
            tenant_id=tenant_id,
            name=name,
            description=description,
            pii_masking_enabled=pii_masking_enabled,
            content_guardrails_enabled=content_guardrails_enabled,
            rate_limit_per_minute=rate_limit_per_minute,
            daily_token_budget=daily_token_budget,
            allowed_providers=allowed_providers,
            fallback_enabled=fallback_enabled,
            require_manual_review=require_manual_review,
            review_threshold_confidence=review_threshold_confidence,
            is_active=True,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(policy)
        self.db.flush()

        # Create initial revision
        self._create_revision(
            policy=policy,
            change_summary="Initial policy creation",
            created_by=created_by,
        )

        # Audit log
        self.audit_service.log_event(
            tenant_id=tenant_id,
            event_type="policy_created",
            event_category="policy",
            summary=f"Created policy '{name}'",
            actor_id=created_by,
            entity_type="policy",
            entity_id=policy.id,
            after_state=self._policy_to_dict(policy),
        )

        return policy

    def update_policy(
        self,
        *,
        policy_id: UUID,
        tenant_id: UUID,
        updated_by: UUID,
        name: str | None = None,
        description: str | None = None,
        pii_masking_enabled: bool | None = None,
        content_guardrails_enabled: bool | None = None,
        rate_limit_per_minute: int | None = None,
        daily_token_budget: int | None = None,
        allowed_providers: list[str] | None = None,
        fallback_enabled: bool | None = None,
        require_manual_review: bool | None = None,
        review_threshold_confidence: float | None = None,
        change_summary: str | None = None,
    ) -> AiPolicy:
        """Update an existing policy."""
        policy = self.get_policy(policy_id)
        if not policy or policy.tenant_id != tenant_id:
            raise ValueError("Policy not found")

        # Capture before state
        before_state = self._policy_to_dict(policy)

        # Update fields
        if name is not None:
            policy.name = name
        if description is not None:
            policy.description = description
        if pii_masking_enabled is not None:
            policy.pii_masking_enabled = pii_masking_enabled
        if content_guardrails_enabled is not None:
            policy.content_guardrails_enabled = content_guardrails_enabled
        if rate_limit_per_minute is not None:
            policy.rate_limit_per_minute = rate_limit_per_minute
        if daily_token_budget is not None:
            policy.daily_token_budget = daily_token_budget
        if allowed_providers is not None:
            policy.allowed_providers = allowed_providers
        if fallback_enabled is not None:
            policy.fallback_enabled = fallback_enabled
        if require_manual_review is not None:
            policy.require_manual_review = require_manual_review
        if review_threshold_confidence is not None:
            policy.review_threshold_confidence = review_threshold_confidence

        policy.updated_by = updated_by
        policy.updated_at = datetime.now(UTC)
        self.db.flush()

        # Create revision
        self._create_revision(
            policy=policy,
            change_summary=change_summary or "Policy updated",
            created_by=updated_by,
        )

        # Audit log
        self.audit_service.log_event(
            tenant_id=tenant_id,
            event_type="policy_updated",
            event_category="policy",
            summary=f"Updated policy '{policy.name}'",
            actor_id=updated_by,
            entity_type="policy",
            entity_id=policy.id,
            before_state=before_state,
            after_state=self._policy_to_dict(policy),
            details={"change_summary": change_summary},
            severity="warning",
        )

        return policy

    def get_policy(self, policy_id: UUID) -> AiPolicy | None:
        """Get a policy by ID."""
        return self.db.execute(
            select(AiPolicy).where(AiPolicy.id == policy_id)
        ).scalar_one_or_none()

    def get_active_policy(self, tenant_id: UUID) -> AiPolicy | None:
        """Get the active policy for a tenant."""
        return self.db.execute(
            select(AiPolicy)
            .where(
                and_(
                    AiPolicy.tenant_id == tenant_id,
                    AiPolicy.is_active == True,
                )
            )
            .order_by(AiPolicy.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    def _create_revision(
        self,
        *,
        policy: AiPolicy,
        change_summary: str,
        created_by: UUID,
    ) -> PolicyRevision:
        """Create a policy revision for audit trail."""
        # Get next revision number
        max_revision = (
            self.db.execute(
                select(func.max(PolicyRevision.revision_number)).where(
                    PolicyRevision.policy_id == policy.id
                )
            ).scalar()
            or 0
        )

        revision = PolicyRevision(
            policy_id=policy.id,
            tenant_id=policy.tenant_id,
            revision_number=max_revision + 1,
            change_summary=change_summary,
            policy_snapshot=self._policy_to_dict(policy),
            created_by=created_by,
        )
        self.db.add(revision)
        self.db.flush()
        return revision

    def _policy_to_dict(self, policy: AiPolicy) -> dict[str, Any]:
        """Convert policy to dictionary for snapshots."""
        return {
            "name": policy.name,
            "description": policy.description,
            "pii_masking_enabled": policy.pii_masking_enabled,
            "content_guardrails_enabled": policy.content_guardrails_enabled,
            "rate_limit_per_minute": policy.rate_limit_per_minute,
            "daily_token_budget": policy.daily_token_budget,
            "allowed_providers": policy.allowed_providers,
            "fallback_enabled": policy.fallback_enabled,
            "require_manual_review": policy.require_manual_review,
            "review_threshold_confidence": policy.review_threshold_confidence,
            "is_active": policy.is_active,
        }
