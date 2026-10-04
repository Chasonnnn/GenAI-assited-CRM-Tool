"""Render unsaved email template content the way sends render it (ADR 0006).

Previews never write unsubscribe tokens and never send. The result is a standalone
document with a restrictive CSP for a sandboxed iframe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Organization, Surrogate
from app.services import (
    email_composition_service,
    email_service,
    email_test_send_service,
    system_email_template_service,
)

VariableMode = Literal["sample", "names", "record"]
TemplateScope = Literal["org", "personal"]

PREVIEW_RECIPIENT = "recipient@example.com"
PREVIEW_UNSUBSCRIBE_URL = "#unsubscribe"
SAMPLE_ORG_NAME = "Example Agency"

_PREVIEW_CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; img-src https: data:; "
    "base-uri 'none'; form-action 'none'"
)


@dataclass(frozen=True)
class EmailPreview:
    subject: str
    html: str
    unresolved_variables: list[str]


def wrap_preview_document(html: str) -> str:
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<meta http-equiv="Content-Security-Policy" content="{_PREVIEW_CSP}">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'</head><body style="margin:0">{html}</body></html>'
    )


def _variable_names(subject: str, body: str) -> set[str]:
    return email_test_send_service.extract_variables(subject, body)


def _name_variables(names: set[str]) -> dict[str, str]:
    return {name: "{{" + name + "}}" for name in names}


def _sample_variables(
    db: Session,
    *,
    org_id: UUID | None,
    actor_display_name: str | None,
) -> dict[str, str]:
    variables = email_test_send_service.build_sample_variables(
        db,
        org_id=org_id,
        to_email=PREVIEW_RECIPIENT,
        actor_display_name=actor_display_name,
        unsubscribe_url=PREVIEW_UNSUBSCRIBE_URL,
    )
    if not variables["org_name"]:
        variables["org_name"] = SAMPLE_ORG_NAME
    return variables


def _resolve_variables(
    *,
    mode: VariableMode,
    names: set[str],
    available: dict[str, str],
    texts: list[str],
) -> tuple[dict[str, str], list[str]]:
    unresolved = email_service.find_unresolved_template_variables(texts, available)
    if mode == "names":
        return _name_variables(names), unresolved
    if mode == "sample":
        return (
            email_test_send_service.apply_unknown_variable_fallbacks(
                variables_used=names, variables=dict(available)
            ),
            unresolved,
        )
    return available, unresolved


def preview_org_template(
    db: Session,
    *,
    org_id: UUID,
    actor_user_id: UUID,
    actor_display_name: str | None,
    subject: str,
    body: str,
    scope: TemplateScope,
    variable_mode: VariableMode,
    surrogate: Surrogate | None = None,
) -> EmailPreview:
    """Preview org or personal template content with signature and unsubscribe footer."""
    from app.services import org_service

    body_template = email_composition_service.strip_legacy_unsubscribe_placeholders(
        email_service.sanitize_template_html(body)
    )
    names = _variable_names(subject, body_template)

    if variable_mode == "record":
        if surrogate is None or surrogate.organization_id != org_id:
            raise ValueError("record preview needs a surrogate in the session organization")
        available = email_service.build_surrogate_template_variables(
            db, surrogate, unsubscribe_url=PREVIEW_UNSUBSCRIBE_URL
        )
    else:
        available = _sample_variables(db, org_id=org_id, actor_display_name=actor_display_name)
    variables, unresolved = _resolve_variables(
        mode=variable_mode,
        names=names,
        available=available,
        texts=[subject, body_template],
    )

    rendered_subject, rendered_body = email_service.render_template(
        subject, body_template, variables
    )
    org = org_service.get_org_by_id(db, org_id)
    html = email_composition_service.compose_template_email_html(
        db=db,
        org_id=org_id,
        recipient_email=PREVIEW_RECIPIENT,
        rendered_body_html=rendered_body,
        scope=scope,
        sender_user_id=actor_user_id,
        portal_base_url=org_service.get_org_portal_base_url(org),
        unsubscribe_url=PREVIEW_UNSUBSCRIBE_URL,
    )
    return EmailPreview(
        subject=rendered_subject,
        html=wrap_preview_document(html),
        unresolved_variables=unresolved,
    )


def preview_platform_template(
    db: Session,
    *,
    subject: str,
    body: str,
    variable_mode: Literal["sample", "names"],
    org: Organization | None,
    actor_display_name: str | None,
) -> EmailPreview:
    """Preview platform library content as its test send renders it."""
    body_template = email_service.sanitize_template_html(body)
    names = _variable_names(subject, body_template)
    available = _sample_variables(
        db, org_id=org.id if org else None, actor_display_name=actor_display_name
    )
    variables, unresolved = _resolve_variables(
        mode=variable_mode,
        names=names,
        available=available,
        texts=[subject, body_template],
    )
    rendered_subject, rendered_body = email_service.render_template(
        subject, body_template, variables
    )
    return EmailPreview(
        subject=rendered_subject,
        html=wrap_preview_document(rendered_body),
        unresolved_variables=unresolved,
    )


def preview_system_template(
    db: Session,
    *,
    subject: str,
    body: str,
    variable_mode: Literal["sample", "names"],
    org: Organization | None,
) -> EmailPreview:
    """Preview platform system template content as its test send renders it."""
    body_template = email_service.sanitize_template_html(body)
    names = _variable_names(subject, body_template)
    available = system_email_template_service.build_sample_variables(db, org=org)
    variables, unresolved = _resolve_variables(
        mode=variable_mode,
        names=names,
        available=available,
        texts=[subject, body_template],
    )
    rendered_subject, rendered_body = email_service.render_template(
        subject,
        body_template,
        variables,
        safe_html_vars=set(system_email_template_service.SAFE_HTML_VARIABLES),
    )
    return EmailPreview(
        subject=rendered_subject,
        html=wrap_preview_document(rendered_body),
        unresolved_variables=unresolved,
    )
