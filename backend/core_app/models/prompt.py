"""Prompt definition and version models."""
from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core_app.database import Base


class PromptStatus(str, Enum):
    """Prompt lifecycle status."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class PromptDefinition(Base):
    """
    Top-level prompt definition.

    A prompt definition represents a named, managed AI prompt that can have
    multiple versions over time. Only one version can be active at a time.
    """
    __tablename__ = "prompt_definitions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Identity
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    use_case: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Ownership
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    updated_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    # Status
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=PromptStatus.DRAFT.value)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC)
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    versions: Mapped[list["PromptVersion"]] = relationship(
        "PromptVersion", back_populates="prompt", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PromptDefinition {self.name} ({self.status})>"


class PromptVersion(Base):
    """
    Specific version of a prompt.

    Each version contains the actual prompt content, configuration, and metadata.
    Only one version per prompt can be active at a time.
    """
    __tablename__ = "prompt_versions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    prompt_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("prompt_definitions.id"), nullable=False, index=True
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Version info
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version_label: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Content
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Configuration
    model_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    temperature: Mapped[float | None] = mapped_column(nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Guardrails metadata
    guardrails_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    pii_masking_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    require_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Activation state
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)

    # Review status
    review_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    reviewed_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Rollback lineage
    previous_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("prompt_versions.id"), nullable=True
    )

    # Metadata
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    # Relationships
    prompt: Mapped["PromptDefinition"] = relationship("PromptDefinition", back_populates="versions")
    previous_version: Mapped["PromptVersion | None"] = relationship(
        "PromptVersion", remote_side=[id], foreign_keys=[previous_version_id]
    )

    def __repr__(self) -> str:
        active = "ACTIVE" if self.is_active else "inactive"
        return f"<PromptVersion v{self.version_number} {active}>"
