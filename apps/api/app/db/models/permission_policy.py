"""Organization permission policy activation state."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrganizationPermissionPolicy(Base):
    __tablename__ = "organization_permission_policies"
    __table_args__ = (
        CheckConstraint("version IN (1, 2)", name="ck_permission_policy_version"),
        CheckConstraint("configuration_revision > 0", name="ck_permission_policy_revision"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    configuration_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
