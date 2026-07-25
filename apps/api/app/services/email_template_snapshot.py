"""Immutable published-template snapshots for delayed email intents."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.db.models import EmailTemplate


class EmailTemplateSnapshotError(ValueError):
    """A persisted template snapshot is missing or fails shape validation."""


@dataclass(frozen=True, slots=True)
class EmailTemplateSnapshot:
    organization_id: UUID
    template_id: UUID
    template_version: int
    subject: str
    body: str
    from_email: str | None
    scope: str | None = None
    owner_user_id: UUID | None = None
    system_key: str | None = None


def format_from_address(address: str | None, name: str | None) -> str | None:
    """Return the exact provider From header selected for a queued intent."""
    clean_address = (address or "").strip()
    if not clean_address:
        return None
    clean_name = (name or "").strip()
    if clean_name and "<" not in clean_address:
        return f"{clean_name} <{clean_address}>"
    return clean_address


def build_snapshot(
    template: EmailTemplate,
    *,
    effective_from_email: str | None,
    include_scope: bool = False,
) -> dict:
    """Serialize the current published row without normalizing its content bytes."""
    payload: dict[str, object] = {
        "schema_version": 1,
        "organization_id": str(template.organization_id),
        "template_id": str(template.id),
        "template_version": template.current_version,
        "subject": template.subject,
        "body": template.body,
        "from_email": effective_from_email,
    }
    if include_scope:
        payload["scope"] = template.scope
        payload["owner_user_id"] = (
            str(template.owner_user_id) if template.owner_user_id is not None else None
        )
        payload["system_key"] = template.system_key
    return payload


def parse_snapshot(payload: object, *, require_scope: bool = False) -> EmailTemplateSnapshot:
    """Validate a persisted snapshot; never fall back when one is malformed."""
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise EmailTemplateSnapshotError("Email template snapshot is invalid")
    try:
        organization_id = UUID(str(payload["organization_id"]))
        template_id = UUID(str(payload["template_id"]))
        template_version = payload["template_version"]
        subject = payload["subject"]
        body = payload["body"]
        from_email = payload["from_email"]
    except (KeyError, TypeError, ValueError) as exc:
        raise EmailTemplateSnapshotError("Email template snapshot is invalid") from exc
    if (
        not isinstance(template_version, int)
        or isinstance(template_version, bool)
        or template_version < 1
        or not isinstance(subject, str)
        or not isinstance(body, str)
        or (from_email is not None and not isinstance(from_email, str))
    ):
        raise EmailTemplateSnapshotError("Email template snapshot is invalid")

    scope = payload.get("scope")
    raw_owner_user_id = payload.get("owner_user_id")
    system_key = payload.get("system_key")
    if require_scope and scope not in {"org", "personal"}:
        raise EmailTemplateSnapshotError("Email template snapshot is invalid")
    if require_scope and "system_key" not in payload:
        raise EmailTemplateSnapshotError("Email template snapshot is invalid")
    if scope is not None and scope not in {"org", "personal"}:
        raise EmailTemplateSnapshotError("Email template snapshot is invalid")
    if system_key is not None and (not isinstance(system_key, str) or not system_key.strip()):
        raise EmailTemplateSnapshotError("Email template snapshot is invalid")
    try:
        owner_user_id = UUID(str(raw_owner_user_id)) if raw_owner_user_id is not None else None
    except (TypeError, ValueError) as exc:
        raise EmailTemplateSnapshotError("Email template snapshot is invalid") from exc
    if scope == "org" and owner_user_id is not None:
        raise EmailTemplateSnapshotError("Email template snapshot is invalid")
    if scope == "personal" and owner_user_id is None:
        raise EmailTemplateSnapshotError("Email template snapshot is invalid")

    return EmailTemplateSnapshot(
        organization_id=organization_id,
        template_id=template_id,
        template_version=template_version,
        subject=subject,
        body=body,
        from_email=from_email,
        scope=scope,
        owner_user_id=owner_user_id,
        system_key=system_key,
    )
