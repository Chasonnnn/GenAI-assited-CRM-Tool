"""Email composition helpers.

Centralizes signature + unsubscribe footer injection so preview/test-send/sends
all match and templates no longer need to embed {{unsubscribe_url}} directly.
"""

from __future__ import annotations

import html
import re
import uuid
from typing import Literal

from sqlalchemy.orm import Session

from app.services import signature_template_service, unsubscribe_service


TemplateScope = Literal["org", "personal"]

# Match {{ unsubscribe_url }} with optional whitespace.
_UNSUB_TOKEN_RE = re.compile(r"{{\s*unsubscribe_url\s*}}", flags=re.IGNORECASE)

# Match <a ... href="{{unsubscribe_url}}" ...>...</a> (quote type can vary, whitespace allowed).
_UNSUB_ANCHOR_RE = re.compile(
    r"""<a\b[^>]*\bhref\s*=\s*(?P<q>['"])\s*{{\s*unsubscribe_url\s*}}\s*(?P=q)[^>]*>.*?</a>""",
    flags=re.IGNORECASE | re.DOTALL,
)


def strip_legacy_unsubscribe_placeholders(body_template_html: str) -> str:
    """Remove legacy unsubscribe placeholders from stored template HTML.

    This is done pre-render so {{unsubscribe_url}} never expands into an ugly
    long URL in the body.
    """
    if not body_template_html:
        return ""

    cleaned = _UNSUB_ANCHOR_RE.sub("", body_template_html)
    cleaned = _UNSUB_TOKEN_RE.sub("", cleaned)
    return cleaned


def _build_unsubscribe_footer_html(*, unsubscribe_url: str, include_divider: bool) -> str:
    """Build a small, email-safe unsubscribe footer."""
    url = html.escape(unsubscribe_url or "", quote=True)
    if not url:
        return ""

    # Keep the footer unobtrusive and email-client friendly (tables + inline styles).
    divider_style = (
        "padding-top: 16px; border-top: 1px solid #e5e7eb;"
        if include_divider
        else "padding-top: 8px;"
    )
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"'
        ' style="margin-top: 14px;">'
        "<tr>"
        f'<td style="font-family: Arial, sans-serif; font-size: 11px; line-height: 16px;'
        f' color: #6b7280; {divider_style}">'
        "If you no longer wish to receive these emails, you can "
        f'<a href="{url}" target="_blank" rel="noopener noreferrer"'
        ' style="color: #6b7280; text-decoration: underline;">'
        "Unsubscribe"
        "</a>."
        "</td>"
        "</tr>"
        "</table>"
    )


def _insert_before_closing_tag(html_body: str, insertion: str) -> str:
    """Insert HTML inside the document if it contains </body> or </html>.

    Some system templates are full HTML documents. Appending after </body> can
    make the signature/footer disappear in many email clients.
    """
    if not insertion:
        return html_body

    # Prefer inserting before </body>.
    body_close = re.search(r"</body\s*>", html_body, flags=re.IGNORECASE)
    if body_close:
        idx = body_close.start()
        return f"{html_body[:idx]}{insertion}{html_body[idx:]}"

    # Next best: insert before </html>.
    html_close = re.search(r"</html\s*>", html_body, flags=re.IGNORECASE)
    if html_close:
        idx = html_close.start()
        return f"{html_body[:idx]}{insertion}{html_body[idx:]}"

    return f"{html_body}{insertion}"


def _wrap_body_html(html_body: str) -> str:
    """Apply a sane default typography baseline for fragment templates.

    Many templates are stored as HTML fragments (no <html>/<body>). In clients
    like Gmail, unstyled fragments can inherit default UI styles that make the
    body text look like part of the signature/footer. A wrapper gives consistent,
    enterprise-looking typography without preventing per-element inline styles.
    """
    if not html_body:
        return ""

    # If the content looks like a full HTML document, do not wrap; let the
    # template control its own root styles.
    if re.search(r"<!doctype|<html\\b|<body\\b", html_body, flags=re.IGNORECASE):
        return html_body

    return (
        '<div style="font-family: Arial, sans-serif; font-size: 16px;'
        ' line-height: 24px; color: #111827;">'
        f"{html_body}"
        "</div>"
    )


def compose_template_email_html(
    db: Session,
    *,
    org_id: uuid.UUID,
    recipient_email: str,
    rendered_body_html: str,
    scope: TemplateScope,
    sender_user_id: uuid.UUID | None = None,
    portal_base_url: str | None = None,
) -> str:
    """Compose final HTML for a template email (body + signature + unsubscribe footer)."""
    body = _wrap_body_html(rendered_body_html or "")

    signature_html = ""
    if scope == "personal":
        if sender_user_id:
            signature_html = signature_template_service.render_signature_html(
                db=db,
                org_id=org_id,
                user_id=sender_user_id,
            )
    else:
        signature_html = signature_template_service.render_org_signature_html(
            db=db,
            org_id=org_id,
        )

    unsubscribe_url = ""
    if (recipient_email or "").strip():
        unsubscribe_url = unsubscribe_service.build_unsubscribe_url(
            org_id=org_id,
            email=recipient_email,
            base_url=portal_base_url,
        )

    footer_html = _build_unsubscribe_footer_html(
        unsubscribe_url=unsubscribe_url,
        include_divider=not bool(signature_html),
    )

    insertion = f"{signature_html}{footer_html}"
    return _insert_before_closing_tag(body, insertion)
