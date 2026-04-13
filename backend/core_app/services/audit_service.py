"""Audit service for logging governance events."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core_app.models.audit import AuditEvent


class AuditService:
    """Service for creating and retrieving audit events."""

    def __init__(self, db: Session):
        self.db = db

    def log_event(
        self,
        *,
        tenant_id: UUID,
        event_type: str,
        event_category: str,
        summary: str,
        actor_id: UUID | None = None,
        actor_role: str | None = None,
        actor_ip: str | None = None,
        details: dict[str, Any] | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        severity: str = "info",
    ) -> AuditEvent:
        """
        Log an audit event.

        Args:
            tenant_id: Tenant identifier
            event_type: Type of event (e.g., 'prompt_activated', 'policy_updated')
            event_category: Category (prompt, policy, execution, security, system)
            summary: Human-readable event summary
            actor_id: User who performed the action
            actor_role: Role of the actor
            actor_ip: IP address of the actor
            details: Additional event details
            entity_type: Type of affected entity
            entity_id: ID of affected entity
            before_state: State before change
            after_state: State after change
            severity: Event severity (debug, info, warning, error, critical)

        Returns:
            Created audit event
        """
        event = AuditEvent(
            tenant_id=tenant_id,
            event_type=event_type,
            event_category=event_category,
            summary=summary,
            actor_id=actor_id,
            actor_role=actor_role,
            actor_ip=actor_ip,
            details=details,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=before_state,
            after_state=after_state,
            severity=severity,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def get_events(
        self,
        *,
        tenant_id: UUID,
        event_type: str | None = None,
        event_category: str | None = None,
        entity_id: UUID | None = None,
        actor_id: UUID | None = None,
        severity: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """
        Retrieve audit events with filters.

        Args:
            tenant_id: Tenant identifier
            event_type: Filter by event type
            event_category: Filter by category
            entity_id: Filter by affected entity
            actor_id: Filter by actor
            severity: Filter by severity
            limit: Maximum events to return
            offset: Number of events to skip

        Returns:
            List of audit events
        """
        query = select(AuditEvent).where(AuditEvent.tenant_id == tenant_id)

        if event_type:
            query = query.where(AuditEvent.event_type == event_type)
        if event_category:
            query = query.where(AuditEvent.event_category == event_category)
        if entity_id:
            query = query.where(AuditEvent.entity_id == entity_id)
        if actor_id:
            query = query.where(AuditEvent.actor_id == actor_id)
        if severity:
            query = query.where(AuditEvent.severity == severity)

        query = query.order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset)

        return list(self.db.execute(query).scalars().all())

    def get_recent_governance_events(
        self,
        tenant_id: UUID,
        limit: int = 20,
    ) -> list[AuditEvent]:
        """
        Get recent governance-related events for founder dashboard.

        Args:
            tenant_id: Tenant identifier
            limit: Number of events to return

        Returns:
            List of recent governance events
        """
        governance_categories = ["prompt", "policy", "security"]

        query = (
            select(AuditEvent)
            .where(AuditEvent.tenant_id == tenant_id)
            .where(AuditEvent.event_category.in_(governance_categories))
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
        )

        return list(self.db.execute(query).scalars().all())
