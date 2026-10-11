"""Email composition helpers.

Centralizes signature + unsubscribe footer injection so preview/test-send/sends
all match and templates no longer need to embed {{unsubscribe_url}} directly.
"""

from __future__ import annotations

import html
import re
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.core.email_layout import EmailLayout, default_layout
from app.services import media_service, org_service, signature_template_service, unsubscribe_service

TemplateScope = Literal["org", "personal"]
# Single quotes: the stack goes inside double-quoted style attributes.
EMAIL_FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Apple Color Emoji', "
    "'Segoe UI Emoji', 'Noto Color Emoji', Arial, sans-serif"
)

EMAIL_COLUMN_WIDTH = 600
DEFAULT_ACCENT_COLOR = "#111827"
PLAIN_LAYOUT = EmailLayout(kind="plain")

_FULL_DOCUMENT_RE = re.compile(r"<!doctype|<html\b|<body\b", flags=re.IGNORECASE)

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
        f'<td style="font-family: {EMAIL_FONT_STACK}; font-size: 11px; line-height: 16px;'
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
    if _FULL_DOCUMENT_RE.search(html_body):
        return html_body

    return (
        f'<div style="font-family: {EMAIL_FONT_STACK}; font-size: 16px;'
        ' line-height: 24px; color: #111827;">'
        f"{html_body}"
        "</div>"
    )


def _logo_img(logo: EmailLogo, *, centered: bool) -> str:
    margin = " margin: 0 auto;" if centered else ""
    return (
        f'<img src="{html.escape(logo.url, quote=True)}" alt="{html.escape(logo.alt, quote=True)}"'
        f' style="display: block;{margin} border: 0; outline: none;'
        ' max-width: 200px; max-height: 64px; width: auto; height: auto;" />'
    )


def _centered_column(inner_rows: str, *, column_style: str = "", column_bgcolor: str = "") -> str:
    """A full-width table that centers a column of at most EMAIL_COLUMN_WIDTH.

    Tables and the Outlook-only fixed-width table keep the column in clients
    that ignore max-width.
    """
    bgcolor = f' bgcolor="{column_bgcolor}"' if column_bgcolor else ""
    return (
        f'<!--[if mso]><table role="presentation" width="{EMAIL_COLUMN_WIDTH}" cellpadding="0"'
        ' cellspacing="0" border="0" align="center"><tr><td><![endif]-->'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"{bgcolor}'
        f' style="max-width: {EMAIL_COLUMN_WIDTH}px; margin: 0 auto;{column_style}">'
        f"{inner_rows}"
        "</table>"
        "<!--[if mso]></td></tr></table><![endif]-->"
    )


def _wrap_layout(
    content_html: str, *, layout: EmailLayout, logo: EmailLogo | None, accent: str
) -> str:
    """Draw the layout frame around body + signature + footer."""
    if layout.kind == "plain":
        return (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            '<tr><td align="center" style="padding: 24px 24px 32px;">'
            + _centered_column(f"<tr><td>{content_html}</td></tr>")
            + "</td></tr></table>"
        )

    centered = layout.logo_position == "center"
    align = "center" if centered else "left"
    if layout.kind == "card":
        logo_row = (
            f'<tr><td align="{align}" style="padding: 32px 24px 0;">'
            f"{_logo_img(logo, centered=centered)}</td></tr>"
            if logo
            else ""
        )
        card = _centered_column(
            f'{logo_row}<tr><td style="padding: 28px 24px 32px;">{content_html}</td></tr>',
            column_style=" background-color: #ffffff; border-radius: 8px;",
            column_bgcolor="#ffffff",
        )
        background = layout.page_background
        return (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' bgcolor="{background}" style="background-color: {background};">'
            f'<tr><td align="center" style="padding: 24px 12px;">{card}</td></tr></table>'
        )

    # Letterhead: logo, an accent rule, then the content; no box.
    logo_row = (
        f'<tr><td align="{align}" style="padding: 24px 0 16px;">'
        f"{_logo_img(logo, centered=centered)}</td></tr>"
        if logo
        else ""
    )
    column = _centered_column(
        f"{logo_row}"
        f'<tr><td style="border-top: 3px solid {accent}; font-size: 0; line-height: 0;">&nbsp;</td></tr>'
        f'<tr><td style="padding: 20px 0 32px;">{content_html}</td></tr>'
    )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td align="center" style="padding: 0 16px;">{column}</td></tr></table>'
    )


@dataclass(frozen=True, slots=True)
class EmailLogo:
    url: str
    alt: str


@dataclass(frozen=True, slots=True)
class LayoutFrame:
    """Everything a layout adds around the body, for sends and the editor canvas."""

    layout: EmailLayout
    logo: EmailLogo | None
    accent_color: str
    signature_html: str
    footer_html: str


def build_layout_frame(
    db: Session,
    *,
    org_id: uuid.UUID,
    scope: TemplateScope,
    layout: EmailLayout,
    sender_user_id: uuid.UUID | None,
    unsubscribe_url: str,
    body_html: str = "",
) -> LayoutFrame:
    """Resolve the logo, signature, and footer that ``layout`` draws around a body."""
    org = org_service.get_org_by_id(db, org_id)
    logo = None
    if layout.kind != "plain" and layout.show_logo:
        logo_url = media_service.email_logo_url(org)
        # A body that already places the logo keeps its own placement.
        if logo_url and logo_url not in body_html:
            logo = EmailLogo(url=logo_url, alt=org.signature_company_name or org.name)
    accent = (
        layout.accent_color
        or signature_template_service.validate_hex_color(
            org.signature_primary_color if org else None
        )
        or DEFAULT_ACCENT_COLOR
    )

    # The signature leaves out its own logo when the layout shows one.
    signature_html = ""
    if scope == "personal":
        if sender_user_id:
            signature_html = signature_template_service.render_signature_html(
                db=db,
                org_id=org_id,
                user_id=sender_user_id,
                include_logo=logo is None,
            )
    else:
        signature_html = signature_template_service.render_org_signature_html(
            db=db,
            org_id=org_id,
            include_logo=logo is None,
        )

    footer_html = _build_unsubscribe_footer_html(
        unsubscribe_url=unsubscribe_url,
        include_divider=not bool(signature_html),
    )
    return LayoutFrame(
        layout=layout,
        logo=logo,
        accent_color=accent,
        signature_html=signature_html,
        footer_html=footer_html,
    )


def compose_template_email_html(
    db: Session,
    *,
    org_id: uuid.UUID,
    recipient_email: str,
    rendered_body_html: str,
    scope: TemplateScope,
    layout: EmailLayout | None = None,
    sender_user_id: uuid.UUID | None = None,
    portal_base_url: str | None = None,
    unsubscribe_url: str | None = None,
) -> str:
    """Compose final HTML for a template email: layout, body, signature, and unsubscribe footer.

    ``layout`` None uses the scope default. A body that is a full HTML document
    controls its own frame, so it gets no layout.
    ``unsubscribe_url`` replaces the tokenized link; previews pass one so they write no token.
    """
    body = _wrap_body_html(rendered_body_html or "")
    is_document = bool(_FULL_DOCUMENT_RE.search(body))

    if unsubscribe_url is None:
        unsubscribe_url = ""
    if not unsubscribe_url and (recipient_email or "").strip():
        unsubscribe_url = unsubscribe_service.build_unsubscribe_url(
            db,
            org_id=org_id,
            email=recipient_email,
            base_url=portal_base_url,
        )

    frame = build_layout_frame(
        db,
        org_id=org_id,
        scope=scope,
        layout=PLAIN_LAYOUT if is_document else layout or default_layout(scope),
        sender_user_id=sender_user_id,
        unsubscribe_url=unsubscribe_url,
        body_html=body,
    )
    insertion = f"{frame.signature_html}{frame.footer_html}"
    if is_document or not body:
        return _insert_before_closing_tag(body, insertion)
    return _wrap_layout(
        f"{body}{insertion}", layout=frame.layout, logo=frame.logo, accent=frame.accent_color
    )
