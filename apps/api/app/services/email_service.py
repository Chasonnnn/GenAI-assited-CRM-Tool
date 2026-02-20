"""Email service - business logic for email templates and sending.

v2: With version control for templates.
"""

from email.utils import parseaddr
from html import escape as html_escape
import re
from datetime import datetime, timezone
from typing import TypedDict
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

import nh3
from email_validator import EmailNotValidError, validate_email

from app.db.models import Attachment, EmailLog, EmailLogAttachment, EmailTemplate, Job, Surrogate
from app.db.enums import EmailStatus, JobType
from app.services.job_service import enqueue_job
from app.services import email_sender, version_service
from app.services.template_variable_catalog import VARIABLE_PATTERN as _TEMPLATE_VARIABLE_PATTERN
from app.types import JsonObject
from app.utils.normalization import normalize_email
from app.utils.presentation import humanize_identifier


# Variable pattern for template substitution: {{ variable_name }} (whitespace allowed)
VARIABLE_PATTERN = _TEMPLATE_VARIABLE_PATTERN

ENTITY_TYPE = "email_template"

ALLOWED_TEMPLATE_TAGS = {
    "a",
    "b",
    "blockquote",
    "br",
    "code",
    "col",
    "colgroup",
    "div",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "s",
    "small",
    "span",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
    "center",
}
ALLOWED_TEMPLATE_ATTRS = {
    "a": {"href", "target", "style", "class", "title"},
    "img": {"src", "alt", "title", "width", "height", "style"},
    "table": {"width", "cellpadding", "cellspacing", "border", "align", "role", "style", "bgcolor"},
    "thead": {"style", "align", "valign"},
    "tbody": {"style", "align", "valign"},
    "tfoot": {"style", "align", "valign"},
    "tr": {"style", "align", "valign", "bgcolor"},
    "td": {"style", "align", "valign", "width", "height", "colspan", "rowspan", "bgcolor"},
    "th": {"style", "align", "valign", "width", "height", "colspan", "rowspan", "bgcolor", "scope"},
    "colgroup": {"style", "span", "width"},
    "col": {"style", "span", "width"},
    "div": {"style", "class", "align"},
    "p": {"style", "class", "align"},
    "span": {"style", "class"},
    "h1": {"style", "class", "align"},
    "h2": {"style", "class", "align"},
    "h3": {"style", "class", "align"},
    "h4": {"style", "class", "align"},
    "h5": {"style", "class", "align"},
    "h6": {"style", "class", "align"},
    "ul": {"style", "class"},
    "ol": {"style", "class"},
    "li": {"style", "class"},
    "blockquote": {"style", "class"},
    "code": {"style", "class"},
    "pre": {"style", "class"},
    "hr": {"style", "class"},
    "center": {"style", "class"},
    "small": {"style", "class"},
    "sup": {"style", "class"},
    "sub": {"style", "class"},
}
ALLOWED_TEMPLATE_STYLE_PROPERTIES = {
    "background-color",
    "border",
    "border-bottom",
    "border-collapse",
    "border-color",
    "border-left",
    "border-radius",
    "border-right",
    "border-spacing",
    "border-style",
    "border-top",
    "border-width",
    "box-sizing",
    "color",
    "display",
    "font-family",
    "font-size",
    "font-style",
    "font-weight",
    "height",
    "letter-spacing",
    "line-height",
    "list-style",
    "list-style-position",
    "list-style-type",
    "margin",
    "margin-bottom",
    "margin-left",
    "margin-right",
    "margin-top",
    "max-height",
    "max-width",
    "min-height",
    "min-width",
    "mso-line-height-rule",
    "padding",
    "padding-bottom",
    "padding-left",
    "padding-right",
    "padding-top",
    "table-layout",
    "text-align",
    "text-decoration",
    "text-transform",
    "vertical-align",
    "white-space",
    "width",
    "word-break",
}

_UNSET = object()

EMAIL_ATTACHMENT_MAX_COUNT = 10
EMAIL_ATTACHMENT_MAX_TOTAL_BYTES = 18 * 1024 * 1024


class EmailAttachmentNotFoundError(LookupError):
    """Raised when one or more requested attachments are not visible to the caller."""


class EmailAttachmentValidationError(ValueError):
    """Raised when attachment selection violates email-send constraints."""


class ProviderAttachment(TypedDict):
    filename: str
    content_type: str
    content_bytes: bytes


def sanitize_template_html(html: str) -> str:
    """Sanitize email template HTML to prevent XSS."""
    cleaned = nh3.clean(
        html,
        tags=ALLOWED_TEMPLATE_TAGS,
        attributes=ALLOWED_TEMPLATE_ATTRS,
        filter_style_properties=ALLOWED_TEMPLATE_STYLE_PROPERTIES,
    )
    # Many email clients collapse empty paragraphs. Preserve authoring intent by
    # turning `<p></p>` / `<p><br></p>` into a visible blank line.
    cleaned = re.sub(
        r"<p>\s*(?:<br\s*/?>)?\s*</p>",
        "<p>&nbsp;</p>",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned


def _normalize_from_email(value: str | None) -> str | None:
    """Normalize optional From header overrides.

    Accepts either a bare email (e.g. "invites@surrogacyforce.com") or
    a display name + email (e.g. "Surrogacy Force <invites@surrogacyforce.com>").
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None

    _, addr = parseaddr(text)
    try:
        validate_email(addr, check_deliverability=False)
    except EmailNotValidError as e:
        raise ValueError("Invalid from_email") from e
    return text


def _template_payload(template: EmailTemplate) -> dict:
    """Extract versionable payload from template."""
    return {
        "name": template.name,
        "subject": template.subject,
        "from_email": template.from_email,
        "body": template.body,
        "is_active": template.is_active,
    }


def create_template(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    name: str,
    subject: str,
    body: str,
    from_email: str | None = None,
    scope: str = "org",
) -> EmailTemplate:
    """Create a new email template with initial version snapshot."""
    clean_body = sanitize_template_html(body)

    # Determine owner_user_id based on scope
    owner_user_id = user_id if scope == "personal" else None

    template = EmailTemplate(
        organization_id=org_id,
        created_by_user_id=user_id,
        name=name,
        subject=subject,
        from_email=_normalize_from_email(from_email),
        body=clean_body,
        is_active=True,
        scope=scope,
        owner_user_id=owner_user_id,
        current_version=1,
    )
    db.add(template)
    db.flush()

    # Create initial version snapshot
    version_service.create_version(
        db=db,
        org_id=org_id,
        entity_type=ENTITY_TYPE,
        entity_id=template.id,
        payload=_template_payload(template),
        created_by_user_id=user_id,
        comment="Created",
    )

    db.commit()
    db.refresh(template)
    return template


def update_template(
    db: Session,
    template: EmailTemplate,
    user_id: UUID,
    name: str | None = None,
    subject: str | None = None,
    from_email: str | None | object = _UNSET,
    body: str | None = None,
    is_active: bool | None = None,
    expected_version: int | None = None,
    comment: str | None = None,
) -> EmailTemplate:
    """
    Update an email template with version control.

    Creates version snapshot on changes.
    Supports optimistic locking via expected_version.
    """
    # Optimistic locking
    if expected_version is not None:
        version_service.check_version(template.current_version, expected_version)

    if name is not None:
        template.name = name
    if subject is not None:
        template.subject = subject
    if from_email is not _UNSET:
        template.from_email = _normalize_from_email(
            from_email if isinstance(from_email, str) else None
        )
    if body is not None:
        template.body = sanitize_template_html(body)
    if is_active is not None:
        template.is_active = is_active

    # Increment version and snapshot
    template.current_version += 1
    template.updated_at = datetime.now(timezone.utc)

    version_service.create_version(
        db=db,
        org_id=template.organization_id,
        entity_type=ENTITY_TYPE,
        entity_id=template.id,
        payload=_template_payload(template),
        created_by_user_id=user_id,
        comment=comment or "Updated",
    )

    db.commit()
    db.refresh(template)
    return template


def get_template_versions(
    db: Session,
    org_id: UUID,
    template_id: UUID,
    limit: int = 50,
) -> list:
    """Get version history for a template."""
    return version_service.get_version_history(
        db=db,
        org_id=org_id,
        entity_type=ENTITY_TYPE,
        entity_id=template_id,
        limit=limit,
    )


def rollback_template(
    db: Session,
    template: EmailTemplate,
    target_version: int,
    user_id: UUID,
) -> tuple[EmailTemplate | None, str | None]:
    """
    Rollback template to a previous version.

    Creates a NEW version with old payload.
    Returns (updated_template, error).
    """
    new_version, error = version_service.rollback_to_version(
        db=db,
        org_id=template.organization_id,
        entity_type=ENTITY_TYPE,
        entity_id=template.id,
        target_version=target_version,
        user_id=user_id,
    )

    if error:
        return None, error

    # Apply rolled-back payload
    payload = version_service.decrypt_payload(new_version.payload_encrypted)
    template.name = payload.get("name", template.name)
    template.subject = payload.get("subject", template.subject)
    template.from_email = payload.get("from_email", template.from_email)
    if "body" in payload:
        template.body = sanitize_template_html(payload.get("body") or "")
    template.is_active = payload.get("is_active", template.is_active)
    template.current_version = new_version.version
    template.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(template)
    return template, None


def get_template(db: Session, template_id: UUID, org_id: UUID) -> EmailTemplate | None:
    """Get template by ID, scoped to org."""
    return (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.id == template_id,
            EmailTemplate.organization_id == org_id,
        )
        .first()
    )


def get_template_by_name(db: Session, name: str, org_id: UUID) -> EmailTemplate | None:
    """Get template by name, scoped to org."""
    return (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.name == name,
            EmailTemplate.organization_id == org_id,
        )
        .first()
    )


def list_templates(
    db: Session,
    org_id: UUID,
    active_only: bool = True,
) -> list[EmailTemplate]:
    """List email templates for an organization (legacy - returns all org+system templates)."""
    query = db.query(EmailTemplate).filter(
        EmailTemplate.organization_id == org_id,
        EmailTemplate.scope == "org",  # Only org templates for backward compatibility
    )
    if active_only:
        query = query.filter(EmailTemplate.is_active.is_(True))
    return query.order_by(EmailTemplate.name).all()


def list_templates_for_user(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    is_admin: bool = False,
    scope_filter: str | None = None,
    show_all_personal: bool = False,
    active_only: bool = True,
) -> list[EmailTemplate]:
    """
    List email templates visible to a user with scope-based filtering.

    Args:
        db: Database session
        org_id: Organization ID
        user_id: Current user ID
        is_admin: Whether user has admin privileges
        scope_filter: Optional 'org' or 'personal' filter
        show_all_personal: Admin-only flag to view all personal templates (read-only)
        active_only: Only return active templates

    Returns:
        List of templates the user can see
    """
    from sqlalchemy import or_, and_
    from app.services import system_email_template_service

    query = db.query(EmailTemplate).filter(EmailTemplate.organization_id == org_id)

    if active_only:
        query = query.filter(EmailTemplate.is_active.is_(True))

    # Hide platform-level system templates from org-facing lists (e.g. org_invite).
    platform_system_keys = set(system_email_template_service.DEFAULT_SYSTEM_TEMPLATES.keys())
    if platform_system_keys:
        query = query.filter(
            or_(
                EmailTemplate.system_key.is_(None),
                EmailTemplate.system_key.notin_(platform_system_keys),
            )
        )

    if scope_filter == "org":
        # Only org templates (including system templates)
        query = query.filter(EmailTemplate.scope == "org")
    elif scope_filter == "personal":
        if show_all_personal and is_admin:
            # Admin viewing all personal templates (read-only)
            query = query.filter(EmailTemplate.scope == "personal")
        else:
            # User's own personal templates
            query = query.filter(
                EmailTemplate.scope == "personal",
                EmailTemplate.owner_user_id == user_id,
            )
    else:
        # No scope filter: return based on visibility rules
        if show_all_personal and is_admin:
            # Admin sees org + all personal
            pass  # No additional filter needed
        else:
            # User sees org templates + their own personal templates
            query = query.filter(
                or_(
                    EmailTemplate.scope == "org",
                    and_(
                        EmailTemplate.scope == "personal",
                        EmailTemplate.owner_user_id == user_id,
                    ),
                )
            )

    return query.order_by(EmailTemplate.scope.desc(), EmailTemplate.name).all()


def template_name_exists(
    db: Session,
    org_id: UUID,
    name: str,
    scope: str,
    owner_user_id: UUID | None = None,
    exclude_id: UUID | None = None,
) -> bool:
    """Check if a template name already exists for the given scope."""
    query = db.query(EmailTemplate).filter(
        EmailTemplate.organization_id == org_id,
        EmailTemplate.scope == scope,
        EmailTemplate.name == name,
    )
    if scope == "personal":
        query = query.filter(EmailTemplate.owner_user_id == owner_user_id)
    if exclude_id:
        query = query.filter(EmailTemplate.id != exclude_id)
    return query.first() is not None


def copy_template_to_personal(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    template_id: UUID,
    new_name: str,
) -> EmailTemplate:
    """
    Copy an org/system template to the user's personal templates.

    Args:
        db: Database session
        org_id: Organization ID
        user_id: User creating the copy
        template_id: Source template ID
        new_name: Name for the new personal template

    Returns:
        New personal template

    Raises:
        ValueError: If source template not found or name already exists
    """
    # Get source template
    source = (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.id == template_id,
            EmailTemplate.organization_id == org_id,
            EmailTemplate.scope == "org",  # Can only copy org/system templates
        )
        .first()
    )
    if not source:
        raise LookupError("Template not found or cannot be copied")

    from app.services import system_email_template_service

    if (
        source.system_key
        and source.system_key in system_email_template_service.DEFAULT_SYSTEM_TEMPLATES
    ):
        raise PermissionError(
            f"Platform system template '{source.system_key}' cannot be copied. "
            "Invites and other platform templates must be managed via the platform endpoint."
        )

    # Check for duplicate name in user's personal templates
    existing = (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.organization_id == org_id,
            EmailTemplate.owner_user_id == user_id,
            EmailTemplate.scope == "personal",
            EmailTemplate.name == new_name,
        )
        .first()
    )
    if existing:
        raise ValueError(f"You already have a template named '{new_name}'")

    # Create personal copy
    new_template = EmailTemplate(
        organization_id=org_id,
        created_by_user_id=user_id,
        name=new_name,
        subject=source.subject,
        from_email=source.from_email,
        body=source.body,
        is_active=True,
        scope="personal",
        owner_user_id=user_id,
        source_template_id=source.id,
        category=source.category,
        current_version=1,
    )
    db.add(new_template)
    db.commit()
    db.refresh(new_template)
    return new_template


def share_template_with_org(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    template_id: UUID,
    new_name: str,
) -> EmailTemplate:
    """
    Share a personal template with the organization.

    Creates an org copy while keeping the original personal template.

    Args:
        db: Database session
        org_id: Organization ID
        user_id: User sharing the template (must be owner)
        template_id: Source personal template ID
        new_name: Name for the new org template

    Returns:
        New org template

    Raises:
        ValueError: If source template not found, not owned by user, or name exists
    """
    # Get source template (must be owned by user)
    source = (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.id == template_id,
            EmailTemplate.organization_id == org_id,
            EmailTemplate.scope == "personal",
        )
        .first()
    )
    if not source:
        raise LookupError("Template not found")
    if source.owner_user_id != user_id:
        raise PermissionError("You can only share your own personal templates")

    # Check for duplicate name in org templates
    existing = (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.organization_id == org_id,
            EmailTemplate.scope == "org",
            EmailTemplate.name == new_name,
        )
        .first()
    )
    if existing:
        raise ValueError(f"An organization template named '{new_name}' already exists")

    # Create org copy
    new_template = EmailTemplate(
        organization_id=org_id,
        created_by_user_id=user_id,
        name=new_name,
        subject=source.subject,
        from_email=source.from_email,
        body=source.body,
        is_active=True,
        scope="org",
        owner_user_id=None,  # Org templates have no owner
        source_template_id=source.id,
        category=source.category,
        current_version=1,
    )
    db.add(new_template)
    db.commit()
    db.refresh(new_template)
    return new_template


def delete_template(db: Session, template: EmailTemplate) -> None:
    """Soft delete a template (deactivate)."""
    template.is_active = False
    db.commit()


def is_email_suppressed(
    db: Session, org_id: UUID, recipient_email: str, *, ignore_opt_out: bool = False
) -> bool:
    """Check if recipient is suppressed for the org."""
    email_norm = normalize_email(recipient_email) or ""
    if not email_norm:
        return False
    from app.services import campaign_service

    return campaign_service.is_email_suppressed(
        db, org_id, email_norm, ignore_opt_out=ignore_opt_out
    )


def render_template(
    subject: str,
    body: str,
    variables: dict[str, str],
    safe_html_vars: set[str] | None = None,
) -> tuple[str, str]:
    """
    Render a template with variable substitution.

    Variables in format {{variable_name}} are replaced with values.
    Missing variables are replaced with empty string.
    safe_html_vars allows selected variables to render as raw HTML in the body.

    Returns (rendered_subject, rendered_body).
    """

    def normalize_value(value: object) -> str:
        if value is None:
            return ""
        return str(value)

    def sanitize_subject_value(value: object) -> str:
        text = normalize_value(value)
        return re.sub(r"[\\r\\n]+", " ", text).strip()

    subject_vars = {k: sanitize_subject_value(v) for k, v in variables.items()}
    safe_html_vars = safe_html_vars or set()
    body_vars: dict[str, str] = {}
    for key, value in variables.items():
        text = normalize_value(value)
        if key in safe_html_vars:
            body_vars[key] = text
        else:
            body_vars[key] = html_escape(text, quote=True)

    def replace_subject_var(match: re.Match) -> str:
        var_name = match.group(1)
        return subject_vars.get(var_name, "")

    def replace_body_var(match: re.Match) -> str:
        var_name = match.group(1)
        return body_vars.get(var_name, "")

    rendered_subject = VARIABLE_PATTERN.sub(replace_subject_var, subject)
    rendered_body = VARIABLE_PATTERN.sub(replace_body_var, body)
    return rendered_subject, rendered_body


def build_surrogate_template_variables(db: Session, surrogate: Surrogate) -> dict[str, str]:
    """Build flat template variables for a surrogate context."""
    from app.db.enums import FormStatus
    from app.db.enums import OwnerType
    from app.db.models import BookingLink, Form, Organization, Queue, User
    from app.services import media_service

    org = db.query(Organization).filter(Organization.id == surrogate.organization_id).first()
    org_logo_url = media_service.get_signed_media_url(org.signature_logo_url) if org else None

    owner_name = ""
    if surrogate.owner_type == OwnerType.USER.value and surrogate.owner_id:
        owner = db.query(User).filter(User.id == surrogate.owner_id).first()
        owner_name = owner.display_name if owner else ""
    elif surrogate.owner_type == OwnerType.QUEUE.value and surrogate.owner_id:
        queue = db.query(Queue).filter(Queue.id == surrogate.owner_id).first()
        owner_name = queue.name if queue else ""

    full_name = surrogate.full_name or ""
    first_name = full_name.split()[0] if full_name else ""
    email = surrogate.email or ""
    unsubscribe_url = ""
    if email:
        from app.services import unsubscribe_service, org_service

        unsubscribe_url = unsubscribe_service.build_unsubscribe_url(
            org_id=surrogate.organization_id,
            email=email,
            base_url=org_service.get_org_portal_base_url(org),
        )

    form_link = ""
    appointment_link = ""
    from app.services import form_submission_service

    form_token = form_submission_service.get_latest_active_token_for_surrogate(
        db,
        org_id=surrogate.organization_id,
        surrogate_id=surrogate.id,
    )
    if not form_token:
        latest_published_form = (
            db.query(Form)
            .filter(
                Form.organization_id == surrogate.organization_id,
                Form.status == FormStatus.PUBLISHED.value,
            )
            .order_by(Form.updated_at.desc(), Form.created_at.desc())
            .first()
        )
        if latest_published_form:
            form_token = form_submission_service.get_or_create_submission_token(
                db=db,
                org_id=surrogate.organization_id,
                form=latest_published_form,
                surrogate=surrogate,
                user_id=surrogate.created_by_user_id,
                expires_in_days=form_submission_service.DEFAULT_TOKEN_EXPIRES_IN_DAYS,
                commit=False,
            )

    if form_token:
        from app.services import org_service

        portal_base_url = org_service.get_org_portal_base_url(org)
        form_link = (
            f"{portal_base_url}/apply/{form_token.token}"
            if portal_base_url
            else f"/apply/{form_token.token}"
        )

    booking_link_user_id: UUID | None = None
    if surrogate.owner_type == OwnerType.USER.value and surrogate.owner_id:
        booking_link_user_id = surrogate.owner_id
    elif surrogate.created_by_user_id:
        booking_link_user_id = surrogate.created_by_user_id

    if booking_link_user_id:
        booking_link = (
            db.query(BookingLink)
            .filter(
                BookingLink.organization_id == surrogate.organization_id,
                BookingLink.user_id == booking_link_user_id,
            )
            .first()
        )
        if not booking_link:
            from app.services import appointment_service

            booking_link = appointment_service.get_or_create_booking_link(
                db=db,
                user_id=booking_link_user_id,
                org_id=surrogate.organization_id,
            )
        if booking_link:
            from app.services import org_service

            portal_base_url = org_service.get_org_portal_base_url(org)
            appointment_link = (
                f"{portal_base_url}/book/{booking_link.public_slug}"
                if portal_base_url
                else f"/book/{booking_link.public_slug}"
            )

    return {
        "first_name": first_name,
        "full_name": full_name,
        "email": email,
        "phone": surrogate.phone or "",
        "surrogate_number": surrogate.surrogate_number or "",
        "status_label": surrogate.status_label or "",
        "state": surrogate.state or "",
        "owner_name": owner_name,
        "form_link": form_link,
        "appointment_link": appointment_link,
        "org_name": org.name if org else "",
        "org_logo_url": org_logo_url or "",
        "unsubscribe_url": unsubscribe_url,
    }


def build_intended_parent_template_variables(db: Session, intended_parent) -> dict[str, str]:
    """Build flat template variables for an intended parent context."""
    from app.db.enums import OwnerType
    from app.db.models import Organization, Queue, User
    from app.services import media_service

    org = db.query(Organization).filter(Organization.id == intended_parent.organization_id).first()
    org_logo_url = media_service.get_signed_media_url(org.signature_logo_url) if org else None

    owner_name = ""
    if intended_parent.owner_type == OwnerType.USER.value and intended_parent.owner_id:
        owner = db.query(User).filter(User.id == intended_parent.owner_id).first()
        owner_name = owner.display_name if owner else ""
    elif intended_parent.owner_type == OwnerType.QUEUE.value and intended_parent.owner_id:
        queue = db.query(Queue).filter(Queue.id == intended_parent.owner_id).first()
        owner_name = queue.name if queue else ""

    full_name = intended_parent.full_name or ""
    first_name = full_name.split()[0] if full_name else ""
    email = intended_parent.email or ""
    unsubscribe_url = ""
    if email:
        from app.services import unsubscribe_service, org_service

        unsubscribe_url = unsubscribe_service.build_unsubscribe_url(
            org_id=intended_parent.organization_id,
            email=email,
            base_url=org_service.get_org_portal_base_url(org),
        )

    return {
        "first_name": first_name,
        "full_name": full_name,
        "email": email,
        "phone": intended_parent.phone or "",
        "intended_parent_number": intended_parent.intended_parent_number or "",
        "status_label": humanize_identifier(intended_parent.status),
        "state": intended_parent.state or "",
        "owner_name": owner_name,
        "org_name": org.name if org else "",
        "org_logo_url": org_logo_url or "",
        "unsubscribe_url": unsubscribe_url,
    }


def build_appointment_template_variables(
    db: Session,
    appointment,
    surrogate: Surrogate | None = None,
) -> dict[str, str]:
    """
    Build template variables for an appointment context.

    Formats appointment times in the client's timezone (or org timezone fallback).
    Uses client_timezone from the appointment for user-facing display.
    """
    from zoneinfo import ZoneInfo
    from app.db.models import Organization
    from app.services import media_service

    # Get org for fallback timezone
    org = db.query(Organization).filter(Organization.id == appointment.organization_id).first()
    org_logo_url = media_service.get_signed_media_url(org.signature_logo_url) if org else None

    # Use appointment's client_timezone, fall back to org timezone
    tz_name = getattr(appointment, "client_timezone", None) or (
        org.timezone if org else "America/Los_Angeles"
    )
    try:
        local_tz = ZoneInfo(tz_name)
    except Exception:
        local_tz = ZoneInfo("America/Los_Angeles")

    # Convert UTC times to local timezone
    local_start = appointment.scheduled_start.astimezone(local_tz)

    # Format date and time in user-friendly format
    appointment_date = local_start.strftime("%A, %B %d, %Y")  # "Monday, December 25, 2024"
    appointment_time = local_start.strftime("%I:%M %p %Z")  # "2:30 PM PST"

    # Get location (virtual link or physical address)
    location = ""
    if hasattr(appointment, "video_link") and appointment.video_link:
        location = appointment.video_link
    elif hasattr(appointment, "location") and appointment.location:
        location = appointment.location
    else:
        location = "To be confirmed"

    variables = {
        "appointment_date": appointment_date,
        "appointment_time": appointment_time,
        "appointment_location": location,
        "org_name": org.name if org else "",
        "org_logo_url": org_logo_url or "",
    }

    # Merge in surrogate variables if provided
    if surrogate:
        surrogate_vars = build_surrogate_template_variables(db, surrogate)
        variables.update(surrogate_vars)

    return variables


def resolve_surrogate_email_attachments(
    db: Session,
    org_id: UUID,
    surrogate_id: UUID,
    attachment_ids: list[UUID] | None,
) -> list[Attachment]:
    """Resolve and validate selected surrogate attachments for outbound email."""
    ordered_ids = list(dict.fromkeys(attachment_ids or []))
    if not ordered_ids:
        return []

    if len(ordered_ids) > EMAIL_ATTACHMENT_MAX_COUNT:
        raise EmailAttachmentValidationError(
            f"You can attach at most {EMAIL_ATTACHMENT_MAX_COUNT} files per email."
        )

    attachments = (
        db.query(Attachment)
        .filter(
            Attachment.organization_id == org_id,
            Attachment.id.in_(ordered_ids),
            Attachment.deleted_at.is_(None),
        )
        .all()
    )
    attachments_by_id = {attachment.id: attachment for attachment in attachments}

    resolved: list[Attachment] = []
    for attachment_id in ordered_ids:
        attachment = attachments_by_id.get(attachment_id)
        if not attachment or attachment.surrogate_id != surrogate_id:
            raise EmailAttachmentNotFoundError("Attachment not found")

        if attachment.quarantined or attachment.scan_status != "clean":
            raise EmailAttachmentValidationError(
                f"Attachment '{attachment.filename}' is not ready for sending. "
                "Only clean attachments can be emailed."
            )
        resolved.append(attachment)

    total_bytes = sum(attachment.file_size for attachment in resolved)
    if total_bytes > EMAIL_ATTACHMENT_MAX_TOTAL_BYTES:
        limit_mb = EMAIL_ATTACHMENT_MAX_TOTAL_BYTES // (1024 * 1024)
        raise EmailAttachmentValidationError(
            f"Total attachment size exceeds {limit_mb} MiB email limit."
        )

    return resolved


def link_attachments_to_email_log(
    db: Session,
    org_id: UUID,
    email_log_id: UUID,
    attachments: list[Attachment],
) -> None:
    """Persist attachment links for an EmailLog."""
    unique_attachments = list({attachment.id: attachment for attachment in attachments}.values())
    for attachment in unique_attachments:
        db.add(
            EmailLogAttachment(
                organization_id=org_id,
                email_log_id=email_log_id,
                attachment_id=attachment.id,
            )
        )
    db.flush()


def list_email_log_attachments(
    db: Session,
    org_id: UUID,
    email_log_id: UUID,
) -> list[Attachment]:
    """Return linked attachments for an EmailLog in insertion order."""
    rows = (
        db.query(Attachment)
        .join(EmailLogAttachment, EmailLogAttachment.attachment_id == Attachment.id)
        .filter(
            EmailLogAttachment.organization_id == org_id,
            EmailLogAttachment.email_log_id == email_log_id,
            Attachment.organization_id == org_id,
            Attachment.deleted_at.is_(None),
        )
        .order_by(EmailLogAttachment.created_at.asc())
        .all()
    )
    return rows


def load_email_log_provider_attachments(
    db: Session,
    org_id: UUID,
    email_log_id: UUID,
) -> list[ProviderAttachment]:
    """Load linked email attachments as provider-ready byte payloads."""
    from app.services import attachment_service

    attachments = list_email_log_attachments(db, org_id, email_log_id)
    if not attachments:
        return []

    if len(attachments) > EMAIL_ATTACHMENT_MAX_COUNT:
        raise EmailAttachmentValidationError(
            f"Email has too many attachments ({len(attachments)}). "
            f"Max allowed is {EMAIL_ATTACHMENT_MAX_COUNT}."
        )

    total_bytes = 0
    provider_attachments: list[ProviderAttachment] = []
    for attachment in attachments:
        if attachment.quarantined or attachment.scan_status != "clean":
            raise EmailAttachmentValidationError(
                f"Attachment '{attachment.filename}' is not clean and cannot be sent."
            )
        total_bytes += int(attachment.file_size)
        provider_attachments.append(
            ProviderAttachment(
                filename=attachment.filename,
                content_type=attachment.content_type,
                content_bytes=attachment_service.load_file_bytes(attachment.storage_key),
            )
        )

    if total_bytes > EMAIL_ATTACHMENT_MAX_TOTAL_BYTES:
        limit_mb = EMAIL_ATTACHMENT_MAX_TOTAL_BYTES // (1024 * 1024)
        raise EmailAttachmentValidationError(
            f"Total attachment size exceeds {limit_mb} MiB email limit."
        )

    return provider_attachments


def send_email(
    db: Session,
    org_id: UUID,
    template_id: UUID | None,
    recipient_email: str,
    subject: str,
    body: str,
    surrogate_id: UUID | None = None,
    attachments: list[Attachment] | None = None,
    schedule_at: datetime | None = None,
    commit: bool = True,
    ignore_opt_out: bool = False,
) -> tuple[EmailLog, Job | None]:
    """
    Queue an email for sending.

    Creates an EmailLog record and schedules a job to send it.
    Returns (email_log, job).
    """
    if is_email_suppressed(db, org_id, recipient_email, ignore_opt_out=ignore_opt_out):
        email_log = EmailLog(
            organization_id=org_id,
            template_id=template_id,
            surrogate_id=surrogate_id,
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            status=EmailStatus.SKIPPED.value,
            error="suppressed",
        )
        db.add(email_log)
        if commit:
            db.commit()
            db.refresh(email_log)
        else:
            db.flush()
        return email_log, None

    # Create email log
    email_log = EmailLog(
        organization_id=org_id,
        template_id=template_id,
        surrogate_id=surrogate_id,
        recipient_email=recipient_email,
        subject=subject,
        body=body,
        status=EmailStatus.PENDING.value,
    )
    db.add(email_log)
    db.flush()  # Get ID before creating job

    if attachments:
        link_attachments_to_email_log(
            db=db,
            org_id=org_id,
            email_log_id=email_log.id,
            attachments=attachments,
        )

    # Schedule job to send
    job = enqueue_job(
        db=db,
        org_id=org_id,
        job_type=JobType.SEND_EMAIL,
        payload={"email_log_id": str(email_log.id)},
        run_at=schedule_at,
        commit=commit,
    )

    # Link job to email log
    email_log.job_id = job.id
    if commit:
        db.commit()
        db.refresh(email_log)
    else:
        db.flush()

    return email_log, job


async def send_immediate_email(
    db: Session,
    org_id: UUID,
    recipient_email: str,
    subject: str,
    body: str,
    *,
    from_email: str | None = None,
    text: str | None = None,
    template_id: UUID | None = None,
    surrogate_id: UUID | None = None,
    idempotency_key: str | None = None,
    sender_user_id: UUID | None = None,
    prefer_platform: bool = True,
    attachments: list[ProviderAttachment] | None = None,
) -> JsonObject:
    """
    Send an email immediately via the configured sender (platform or Gmail).

    This bypasses the queued SEND_EMAIL job and is intended for system/admin flows.
    """
    if is_email_suppressed(db, org_id, recipient_email):
        email_log = EmailLog(
            organization_id=org_id,
            template_id=template_id,
            surrogate_id=surrogate_id,
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            status=EmailStatus.SKIPPED.value,
            error="suppressed",
        )
        db.add(email_log)
        db.commit()
        db.refresh(email_log)
        return {"success": False, "error": "Email suppressed", "email_log_id": email_log.id}

    selection = email_sender.select_sender(
        prefer_platform=prefer_platform,
        sender_user_id=sender_user_id,
    )
    if selection.error:
        return {"success": False, "error": selection.error}

    return await selection.sender.send_email_logged(
        db=db,
        org_id=org_id,
        to_email=recipient_email,
        subject=subject,
        from_email=from_email,
        html=body,
        text=text,
        template_id=template_id,
        surrogate_id=surrogate_id,
        idempotency_key=idempotency_key,
        attachments=attachments,
    )


def send_from_template(
    db: Session,
    org_id: UUID,
    template_id: UUID,
    recipient_email: str,
    variables: dict[str, str],
    surrogate_id: UUID | None = None,
    schedule_at: datetime | None = None,
    sender_user_id: UUID | None = None,
) -> tuple[EmailLog, Job | None] | None:
    """
    Queue an email using a template.

    Renders the template with variables and queues for sending.
    Returns (email_log, job) or None if template not found.
    """
    template = get_template(db, template_id, org_id)
    if not template:
        return None

    from app.services import system_email_template_service

    if (
        template.system_key
        and template.system_key in system_email_template_service.DEFAULT_SYSTEM_TEMPLATES
    ):
        raise PermissionError(
            f"Platform system template '{template.system_key}' cannot be sent from org endpoints. "
            "Invites and other platform templates must be sent via the platform/system sender."
        )

    from app.services import email_composition_service

    cleaned_body_template = email_composition_service.strip_legacy_unsubscribe_placeholders(
        template.body
    )
    subject, body = render_template(template.subject, cleaned_body_template, variables)

    signature_user_id: UUID | None = None
    if template.scope == "personal":
        signature_user_id = sender_user_id or template.owner_user_id

    from app.services import org_service

    org = org_service.get_org_by_id(db, org_id)
    portal_base_url = org_service.get_org_portal_base_url(org)

    body = email_composition_service.compose_template_email_html(
        db=db,
        org_id=org_id,
        recipient_email=recipient_email,
        rendered_body_html=body,
        scope="personal" if template.scope == "personal" else "org",
        sender_user_id=signature_user_id,
        portal_base_url=portal_base_url,
    )
    return send_email(
        db=db,
        org_id=org_id,
        template_id=template_id,
        recipient_email=recipient_email,
        subject=subject,
        body=body,
        surrogate_id=surrogate_id,
        schedule_at=schedule_at,
    )


def mark_email_sent(db: Session, email_log: EmailLog) -> EmailLog:
    """Mark an email as sent."""
    email_log.status = EmailStatus.SENT.value
    email_log.sent_at = datetime.now(timezone.utc)
    email_log.error = None
    db.commit()
    db.refresh(email_log)
    _sync_campaign_recipient(db, email_log, EmailStatus.SENT.value)
    return email_log


def mark_email_failed(db: Session, email_log: EmailLog, error: str) -> EmailLog:
    """Mark an email as failed."""
    email_log.status = EmailStatus.FAILED.value
    email_log.error = error
    db.commit()
    db.refresh(email_log)
    _sync_campaign_recipient(db, email_log, EmailStatus.FAILED.value, error=error)
    return email_log


def mark_email_skipped(db: Session, email_log: EmailLog, reason: str) -> EmailLog:
    """Mark an email as skipped (suppressed)."""
    email_log.status = EmailStatus.SKIPPED.value
    email_log.error = reason
    db.commit()
    db.refresh(email_log)
    _sync_campaign_recipient(db, email_log, EmailStatus.SKIPPED.value, error=reason)
    return email_log


def get_email_log(db: Session, email_id: UUID, org_id: UUID) -> EmailLog | None:
    """Get email log by ID, scoped to org."""
    return (
        db.query(EmailLog)
        .filter(
            EmailLog.id == email_id,
            EmailLog.organization_id == org_id,
        )
        .first()
    )


def list_email_logs(
    db: Session,
    org_id: UUID,
    surrogate_id: UUID | None = None,
    status: EmailStatus | None = None,
    limit: int = 50,
) -> list[EmailLog]:
    """List email logs for an organization with optional filters."""
    query = db.query(EmailLog).filter(EmailLog.organization_id == org_id)
    if surrogate_id:
        query = query.filter(EmailLog.surrogate_id == surrogate_id)
    if status:
        query = query.filter(EmailLog.status == status.value)
    return query.order_by(EmailLog.created_at.desc()).limit(limit).all()


def _sync_campaign_recipient(
    db: Session,
    email_log: EmailLog,
    status: str,
    error: str | None = None,
) -> None:
    """Update campaign recipient/run stats when an email log changes."""
    from app.db.models import CampaignRecipient, CampaignRun, Campaign
    from app.db.enums import CampaignRecipientStatus, CampaignStatus

    cr = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.external_message_id == str(email_log.id))
        .first()
    )
    if not cr:
        return

    if status == EmailStatus.SENT.value:
        cr.status = CampaignRecipientStatus.SENT.value
        if not cr.sent_at:
            cr.sent_at = datetime.now(timezone.utc)
        cr.error = None
    elif status == EmailStatus.SKIPPED.value:
        cr.status = CampaignRecipientStatus.SKIPPED.value
        cr.skip_reason = (error or "suppressed")[:100]
    else:
        cr.status = CampaignRecipientStatus.FAILED.value
        cr.error = (error or email_log.error or "Send failed")[:500]

    db.commit()

    run = db.query(CampaignRun).filter(CampaignRun.id == cr.run_id).first()
    if not run:
        return

    status_rows = (
        db.query(CampaignRecipient.status, func.count(CampaignRecipient.id))
        .filter(CampaignRecipient.run_id == run.id)
        .group_by(CampaignRecipient.status)
        .all()
    )
    status_counts = {status: count for status, count in status_rows}

    delivered_count = status_counts.get(CampaignRecipientStatus.DELIVERED.value, 0)
    run.sent_count = status_counts.get(CampaignRecipientStatus.SENT.value, 0) + delivered_count
    run.delivered_count = delivered_count
    run.failed_count = status_counts.get(CampaignRecipientStatus.FAILED.value, 0)
    run.skipped_count = status_counts.get(CampaignRecipientStatus.SKIPPED.value, 0)
    pending_count = status_counts.get(CampaignRecipientStatus.PENDING.value, 0)

    if pending_count == 0:
        run.completed_at = datetime.now(timezone.utc)
        run.status = "completed" if run.failed_count == 0 else "failed"
    else:
        run.status = "running"
        run.completed_at = None

    campaign = db.query(Campaign).filter(Campaign.id == run.campaign_id).first()
    if campaign:
        campaign.sent_count = run.sent_count
        campaign.delivered_count = run.delivered_count
        campaign.failed_count = run.failed_count
        campaign.skipped_count = run.skipped_count
        campaign.total_recipients = run.total_count
        if pending_count == 0:
            campaign.status = (
                CampaignStatus.COMPLETED.value
                if run.failed_count == 0
                else CampaignStatus.FAILED.value
            )
        else:
            campaign.status = CampaignStatus.SENDING.value

    db.commit()
