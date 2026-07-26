"""Fail-closed recovery for spacing-only email-template regressions."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import AuditEventType
from app.db.models import EmailTemplate, EmailTemplateDraft, EntityVersion
from app.services import audit_service, email_service, version_service
from app.services.email_content import html_to_text


_TEMPLATE_VARIABLE_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
_PARAGRAPH_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)
_BREAK_RE = re.compile(r"<br\b[^>]*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_BLANK_ENTITY_RE = re.compile(r"(?:&nbsp;|&#160;|&#x0*a0;)", re.IGNORECASE)
_TAG_RE_WITH_ATTRS = re.compile(
    r"<\s*/?\s*([a-zA-Z0-9]+)\b([^>]*)>",
    re.IGNORECASE,
)
_BLANK_PARAGRAPH_NODE_RE = re.compile(
    r"<p\b[^>]*>\s*(?:(?:<br\b[^>]*>)|(?:&nbsp;|&#160;|&#x0*a0;))*\s*</p>",
    re.IGNORECASE,
)
_BETWEEN_TAG_WHITESPACE_RE = re.compile(r">\s+<")


class TemplateBlankLineRecoveryConflict(ValueError):
    """A reviewed recovery is missing, unsafe, or no longer current."""


@dataclass(frozen=True, slots=True)
class TemplateBlankLineRecoveryPlan:
    """Content-free evidence for one proposed body-only recovery."""

    template_id: UUID
    organization_id: UUID
    current_version: int
    target_version: int
    current_body_sha256: str
    target_body_sha256: str
    current_blank_line_count: int
    target_blank_line_count: int
    visible_text_equal: bool
    variable_tokens_equal: bool
    structural_content_equal: bool
    eligible: bool


def body_sha256(body: str) -> str:
    """Return the review digest for one canonical template body."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _blank_line_count(body: str) -> int:
    paragraph_count = 0
    for content in _PARAGRAPH_RE.findall(body):
        visible = _BREAK_RE.sub("", content)
        visible = _TAG_RE.sub("", visible)
        visible = _BLANK_ENTITY_RE.sub("", visible)
        if not visible.strip():
            paragraph_count += 1
    if paragraph_count:
        return paragraph_count

    normalized = body.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    if len(lines) < 3:
        return 0
    return sum(
        1
        for index, line in enumerate(lines[1:-1], start=1)
        if not line.strip()
        and any(previous.strip() for previous in lines[:index])
        and any(following.strip() for following in lines[index + 1 :])
    )


def _variable_tokens(body: str) -> tuple[str, ...]:
    return tuple(sorted(_TEMPLATE_VARIABLE_RE.findall(body)))


def _is_plain_or_simple_paragraph_body(body: str) -> bool:
    """Allow the Studio's plain-text-to-paragraph representation change."""
    for match in _TAG_RE_WITH_ATTRS.finditer(body):
        tag = match.group(1).casefold()
        attributes = match.group(2).strip().rstrip("/").strip()
        if tag not in {"p", "br"} or attributes:
            return False
    return True


def _canonical_nonspacing_markup(body: str) -> str:
    normalized = body.replace("\r\n", "\n").replace("\r", "\n")
    normalized = _BLANK_PARAGRAPH_NODE_RE.sub("", normalized)
    normalized = _BETWEEN_TAG_WHITESPACE_RE.sub("><", normalized)
    return normalized.strip()


def _spacing_only_structure_equal(current_body: str, target_body: str) -> bool:
    if _is_plain_or_simple_paragraph_body(current_body) and _is_plain_or_simple_paragraph_body(
        target_body
    ):
        return True
    return _canonical_nonspacing_markup(current_body) == _canonical_nonspacing_markup(target_body)


def _template_payload(template: EmailTemplate) -> dict[str, object]:
    return {
        "name": template.name,
        "subject": template.subject,
        "from_email": template.from_email,
        "body": template.body,
        "is_active": template.is_active,
    }


def _verified_version_payload(
    db: Session,
    *,
    template: EmailTemplate,
    version_number: int,
) -> tuple[EntityVersion, dict[str, object]]:
    version = version_service.get_version(
        db,
        template.organization_id,
        email_service.ENTITY_TYPE,
        template.id,
        version_number,
    )
    if version is None:
        raise TemplateBlankLineRecoveryConflict("Template version was not found")
    if version.schema_version != 1:
        raise TemplateBlankLineRecoveryConflict("Template version uses an unsupported schema")
    if not version_service.verify_checksum(
        version.payload_encrypted,
        version.checksum,
    ):
        raise TemplateBlankLineRecoveryConflict("Template version failed its integrity check")
    payload = version_service.decrypt_payload(version.payload_encrypted)
    if not isinstance(payload, dict) or not isinstance(payload.get("body"), str):
        raise TemplateBlankLineRecoveryConflict("Template version has no recoverable body")
    return version, payload


def _build_recovery_plan(
    db: Session,
    *,
    template: EmailTemplate,
    target_version: int,
) -> tuple[TemplateBlankLineRecoveryPlan, str, EntityVersion]:
    if target_version >= template.current_version:
        raise TemplateBlankLineRecoveryConflict("Target version must precede the current template")

    current_version_record, recorded_current_payload = _verified_version_payload(
        db,
        template=template,
        version_number=template.current_version,
    )
    if recorded_current_payload != _template_payload(template):
        raise TemplateBlankLineRecoveryConflict(
            "Published template does not match its version history"
        )
    _target_version_record, target_payload = _verified_version_payload(
        db,
        template=template,
        version_number=target_version,
    )
    target_body = target_payload["body"]
    if not isinstance(target_body, str):
        raise TemplateBlankLineRecoveryConflict("Template version has no recoverable body")
    recovery_body = email_service.sanitize_template_html(target_body)

    current_blank_line_count = _blank_line_count(template.body)
    target_blank_line_count = _blank_line_count(recovery_body)
    visible_text_equal = html_to_text(template.body) == html_to_text(recovery_body)
    variable_tokens_equal = _variable_tokens(template.body) == _variable_tokens(recovery_body)
    structural_content_equal = _spacing_only_structure_equal(
        template.body,
        recovery_body,
    )
    bodies_differ = template.body != recovery_body
    eligible = (
        bodies_differ
        and visible_text_equal
        and variable_tokens_equal
        and structural_content_equal
        and target_blank_line_count > current_blank_line_count
    )

    return (
        TemplateBlankLineRecoveryPlan(
            template_id=template.id,
            organization_id=template.organization_id,
            current_version=template.current_version,
            target_version=target_version,
            current_body_sha256=body_sha256(template.body),
            target_body_sha256=body_sha256(recovery_body),
            current_blank_line_count=current_blank_line_count,
            target_blank_line_count=target_blank_line_count,
            visible_text_equal=visible_text_equal,
            variable_tokens_equal=variable_tokens_equal,
            structural_content_equal=structural_content_equal,
            eligible=eligible,
        ),
        recovery_body,
        current_version_record,
    )


def build_recovery_plan(
    db: Session,
    *,
    organization_id: UUID,
    template_id: UUID,
    target_version: int,
) -> TemplateBlankLineRecoveryPlan:
    """Return content-free evidence without changing the template."""
    template = db.execute(
        select(EmailTemplate).where(
            EmailTemplate.id == template_id,
            EmailTemplate.organization_id == organization_id,
        )
    ).scalar_one_or_none()
    if template is None:
        raise TemplateBlankLineRecoveryConflict("Template was not found")
    plan, _target_body, _current_version_record = _build_recovery_plan(
        db,
        template=template,
        target_version=target_version,
    )
    return plan


def apply_recovery_plan(
    db: Session,
    *,
    organization_id: UUID,
    template_id: UUID,
    target_version: int,
    expected_current_version: int,
    expected_current_body_sha256: str,
    expected_target_body_sha256: str,
    review_reason: str,
) -> EmailTemplate:
    """Append a body-only version after revalidating exact reviewed evidence."""
    normalized_reason = review_reason.strip()
    if not normalized_reason or len(normalized_reason) > 500:
        raise TemplateBlankLineRecoveryConflict(
            "Review reason must contain between 1 and 500 characters"
        )

    template = db.execute(
        select(EmailTemplate)
        .where(
            EmailTemplate.id == template_id,
            EmailTemplate.organization_id == organization_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if template is None:
        raise TemplateBlankLineRecoveryConflict("Template was not found")

    plan, target_body, current_version_record = _build_recovery_plan(
        db,
        template=template,
        target_version=target_version,
    )
    if (
        plan.current_version != expected_current_version
        or plan.current_body_sha256 != expected_current_body_sha256
        or plan.target_body_sha256 != expected_target_body_sha256
    ):
        raise TemplateBlankLineRecoveryConflict(
            "Template recovery review no longer matches the published version"
        )
    if not plan.eligible:
        raise TemplateBlankLineRecoveryConflict("Template change is not a spacing-only change")

    open_draft_id = db.execute(
        select(EmailTemplateDraft.id).where(
            EmailTemplateDraft.organization_id == organization_id,
            EmailTemplateDraft.template_id == template_id,
        )
    ).scalar_one_or_none()
    if open_draft_id is not None:
        raise TemplateBlankLineRecoveryConflict(
            "Template has an open Studio draft; recovery was not applied"
        )

    try:
        with db.begin_nested():
            recovered = email_service.update_template(
                db,
                template=template,
                user_id=None,
                body=target_body,
                expected_version=expected_current_version,
                comment="Recovered blank-line formatting",
                commit=False,
            )
            if body_sha256(recovered.body) != plan.target_body_sha256:
                raise TemplateBlankLineRecoveryConflict(
                    "Recovered template body does not match the reviewed digest"
                )
            recovered_version = version_service.get_version(
                db,
                organization_id,
                email_service.ENTITY_TYPE,
                template_id,
                recovered.current_version,
            )
            if recovered_version is None:
                raise TemplateBlankLineRecoveryConflict(
                    "Recovered template version was not recorded"
                )
            audit_service.log_event(
                db=db,
                org_id=organization_id,
                event_type=AuditEventType.CONFIG_TEMPLATE_UPDATED,
                actor_user_id=None,
                target_type="email_template",
                target_id=template_id,
                details={
                    "action": "blank_line_recovery",
                    "review_reason": normalized_reason,
                    "from_version": plan.current_version,
                    "to_version": recovered.current_version,
                    "source_version": plan.target_version,
                    "current_body_sha256": plan.current_body_sha256,
                    "recovered_body_sha256": plan.target_body_sha256,
                    "blank_lines_before": plan.current_blank_line_count,
                    "blank_lines_after": plan.target_blank_line_count,
                },
                before_version_id=current_version_record.id,
                after_version_id=recovered_version.id,
            )
    except Exception:
        db.expire_all()
        raise

    db.commit()
    db.refresh(recovered)
    return recovered
