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

    divider_style = "padding-top: 16px; border-top: 1px solid #e5e7eb;" if include_divider else ""
    return (
        '<div style="margin-top: 14px; font-size: 12px; color: #6b7280;'
        f' {divider_style}">'
        '<p style="margin: 0;">'
        "Manage email preferences: "
        f'<a href="{url}" target="_blank" style="color: #2563eb; text-decoration: none;">'
        "Unsubscribe"
        "</a>"
        "</p>"
        "</div>"
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


def compose_template_email_html(
    db: Session,
    *,
    org_id: uuid.UUID,
    recipient_email: str,
    rendered_body_html: str,
    scope: TemplateScope,
    sender_user_id: uuid.UUID | None = None,
) -> str:
    """Compose final HTML for a template email (body + signature + unsubscribe footer)."""
    body = rendered_body_html or ""

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
        )

    footer_html = _build_unsubscribe_footer_html(
        unsubscribe_url=unsubscribe_url,
        include_divider=not bool(signature_html),
    )

    insertion = f"{signature_html}{footer_html}"
    return _insert_before_closing_tag(body, insertion)
