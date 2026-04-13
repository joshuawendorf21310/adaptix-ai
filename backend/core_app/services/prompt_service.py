"""Prompt management service."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from core_app.models.prompt import PromptDefinition, PromptVersion, PromptStatus
from core_app.services.audit_service import AuditService


class PromptService:
    """Service for managing prompts and versions."""

    def __init__(self, db: Session, audit_service: AuditService | None = None):
        self.db = db
        self.audit_service = audit_service or AuditService(db)

    def create_prompt(
        self,
        *,
        tenant_id: UUID,
        name: str,
        use_case: str,
        description: str | None,
        owner: str | None,
        created_by: UUID,
    ) -> PromptDefinition:
        """Create a new prompt definition."""
        prompt = PromptDefinition(
            tenant_id=tenant_id,
            name=name,
            use_case=use_case,
            description=description,
            owner=owner,
            created_by=created_by,
            updated_by=created_by,
            status=PromptStatus.DRAFT.value,
        )
        self.db.add(prompt)
        self.db.flush()

        # Audit log
        self.audit_service.log_event(
            tenant_id=tenant_id,
            event_type="prompt_created",
            event_category="prompt",
            summary=f"Created prompt '{name}'",
            actor_id=created_by,
            entity_type="prompt",
            entity_id=prompt.id,
            details={"use_case": use_case},
        )

        return prompt

    def create_version(
        self,
        *,
        prompt_id: UUID,
        tenant_id: UUID,
        prompt_text: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        guardrails_enabled: bool = True,
        pii_masking_enabled: bool = True,
        require_review: bool = False,
        change_summary: str | None = None,
        created_by: UUID,
        model_config: dict[str, Any] | None = None,
    ) -> PromptVersion:
        """Create a new version of a prompt."""
        # Get current max version number
        max_version = (
            self.db.execute(
                select(func.max(PromptVersion.version_number)).where(
                    PromptVersion.prompt_id == prompt_id
                )
            ).scalar()
            or 0
        )

        version = PromptVersion(
            prompt_id=prompt_id,
            tenant_id=tenant_id,
            version_number=max_version + 1,
            prompt_text=prompt_text,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            guardrails_enabled=guardrails_enabled,
            pii_masking_enabled=pii_masking_enabled,
            require_review=require_review,
            change_summary=change_summary,
            created_by=created_by,
            model_config=model_config,
            review_status="pending" if require_review else "approved",
        )
        self.db.add(version)
        self.db.flush()

        # Audit log
        prompt = self.get_prompt(prompt_id)
        self.audit_service.log_event(
            tenant_id=tenant_id,
            event_type="prompt_version_created",
            event_category="prompt",
            summary=f"Created version {version.version_number} of prompt '{prompt.name if prompt else 'unknown'}'",
            actor_id=created_by,
            entity_type="prompt_version",
            entity_id=version.id,
            details={
                "prompt_id": str(prompt_id),
                "version_number": version.version_number,
                "change_summary": change_summary,
            },
        )

        return version

    def activate_version(
        self,
        *,
        version_id: UUID,
        tenant_id: UUID,
        activated_by: UUID,
    ) -> PromptVersion:
        """Activate a prompt version (deactivates other versions of same prompt)."""
        version = self.get_version(version_id)
        if not version or version.tenant_id != tenant_id:
            raise ValueError("Version not found")

        # Deactivate all other versions of this prompt
        self.db.execute(
            PromptVersion.__table__.update()
            .where(
                and_(
                    PromptVersion.prompt_id == version.prompt_id,
                    PromptVersion.is_active == True,
                )
            )
            .values(
                is_active=False,
                deactivated_at=datetime.now(UTC),
                deactivated_by=activated_by,
            )
        )

        # Activate this version
        version.is_active = True
        version.activated_at = datetime.now(UTC)
        version.activated_by = activated_by
        self.db.flush()

        # Update prompt status
        prompt = self.get_prompt(version.prompt_id)
        if prompt:
            prompt.status = PromptStatus.ACTIVE.value
            prompt.updated_by = activated_by

        # Audit log
        self.audit_service.log_event(
            tenant_id=tenant_id,
            event_type="prompt_version_activated",
            event_category="prompt",
            summary=f"Activated version {version.version_number} of prompt '{prompt.name if prompt else 'unknown'}'",
            actor_id=activated_by,
            entity_type="prompt_version",
            entity_id=version.id,
            details={
                "prompt_id": str(version.prompt_id),
                "version_number": version.version_number,
            },
            severity="info",
        )

        return version

    def deactivate_version(
        self,
        *,
        version_id: UUID,
        tenant_id: UUID,
        deactivated_by: UUID,
    ) -> PromptVersion:
        """Deactivate a prompt version."""
        version = self.get_version(version_id)
        if not version or version.tenant_id != tenant_id:
            raise ValueError("Version not found")

        version.is_active = False
        version.deactivated_at = datetime.now(UTC)
        version.deactivated_by = deactivated_by
        self.db.flush()

        # Update prompt status if no active versions remain
        active_count = self.db.execute(
            select(func.count(PromptVersion.id)).where(
                and_(
                    PromptVersion.prompt_id == version.prompt_id,
                    PromptVersion.is_active == True,
                )
            )
        ).scalar()

        if active_count == 0:
            prompt = self.get_prompt(version.prompt_id)
            if prompt:
                prompt.status = PromptStatus.INACTIVE.value
                prompt.updated_by = deactivated_by

        # Audit log
        prompt = self.get_prompt(version.prompt_id)
        self.audit_service.log_event(
            tenant_id=tenant_id,
            event_type="prompt_version_deactivated",
            event_category="prompt",
            summary=f"Deactivated version {version.version_number} of prompt '{prompt.name if prompt else 'unknown'}'",
            actor_id=deactivated_by,
            entity_type="prompt_version",
            entity_id=version.id,
            details={
                "prompt_id": str(version.prompt_id),
                "version_number": version.version_number,
            },
        )

        return version

    def get_prompt(self, prompt_id: UUID) -> PromptDefinition | None:
        """Get a prompt by ID."""
        return self.db.execute(
            select(PromptDefinition).where(PromptDefinition.id == prompt_id)
        ).scalar_one_or_none()

    def get_version(self, version_id: UUID) -> PromptVersion | None:
        """Get a prompt version by ID."""
        return self.db.execute(
            select(PromptVersion).where(PromptVersion.id == version_id)
        ).scalar_one_or_none()

    def list_prompts(
        self,
        tenant_id: UUID,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PromptDefinition]:
        """List prompts for a tenant."""
        query = select(PromptDefinition).where(PromptDefinition.tenant_id == tenant_id)

        if status:
            query = query.where(PromptDefinition.status == status)

        query = query.order_by(PromptDefinition.created_at.desc()).limit(limit).offset(offset)

        return list(self.db.execute(query).scalars().all())

    def get_active_versions(self, tenant_id: UUID) -> list[PromptVersion]:
        """Get all active prompt versions for a tenant."""
        query = (
            select(PromptVersion)
            .where(
                and_(
                    PromptVersion.tenant_id == tenant_id,
                    PromptVersion.is_active == True,
                )
            )
            .order_by(PromptVersion.created_at.desc())
        )

        return list(self.db.execute(query).scalars().all())

    def get_prompt_statistics(self, tenant_id: UUID) -> dict[str, Any]:
        """Get prompt statistics for audit dashboard."""
        total_prompts = self.db.execute(
            select(func.count(PromptDefinition.id)).where(
                PromptDefinition.tenant_id == tenant_id
            )
        ).scalar() or 0

        active_prompts = self.db.execute(
            select(func.count(PromptDefinition.id)).where(
                and_(
                    PromptDefinition.tenant_id == tenant_id,
                    PromptDefinition.status == PromptStatus.ACTIVE.value,
                )
            )
        ).scalar() or 0

        active_versions = self.get_active_versions(tenant_id)

        # Count guardrails enabled across active versions
        guardrails_count = sum(1 for v in active_versions if v.guardrails_enabled)
        pii_masking_count = sum(1 for v in active_versions if v.pii_masking_enabled)

        return {
            "total_prompts": total_prompts,
            "active_prompts": active_prompts,
            "guardrails_enabled_count": guardrails_count,
            "pii_masking_enabled_count": pii_masking_count,
            "active_versions": active_versions,
        }
