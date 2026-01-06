"""Signature Template Service.

Renders email-safe HTML signatures using org branding and user profile data.
All templates use table layouts with inline styles for maximum email client compatibility.
"""

import html
import re
import uuid
from urllib.parse import urlparse
from typing import Literal

from sqlalchemy.orm import Session

from app.db.models import Organization, User
from app.services import org_service, user_service


# Template types
TemplateType = Literal["classic", "modern", "minimal", "professional", "creative"]

# Default template when org.signature_template is null
DEFAULT_TEMPLATE: TemplateType = "classic"

# Validation patterns
HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
HTTPS_URL_PATTERN = re.compile(r"^https://")


def validate_hex_color(color: str | None) -> str | None:
    """Validate hex color format, return None if invalid."""
    if not color:
        return None
    return color if HEX_COLOR_PATTERN.match(color) else None


def validate_url(url: str | None) -> str | None:
    """Validate HTTPS URL and return an escaped value for safe HTML usage."""
    if not url:
        return None
    if url.strip() != url:
        return None
    if any(char.isspace() for char in url):
        return None
    if any(char in url for char in ['"', "'", "<", ">"]):
        return None
    if not HTTPS_URL_PATTERN.match(url):
        return None
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    return html.escape(url, quote=True)


def escape_text(text: str | None) -> str:
    """HTML-escape text to prevent injection."""
    if not text:
        return ""
    return html.escape(text, quote=True)


def render_signature_html(
    db: Session,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> str:
    """
    Render email-safe HTML signature.
    
    This is the single source of truth for signature rendering.
    Uses org branding + user profile + user social links.
    
    Args:
        db: Database session
        org_id: Organization ID
        user_id: User ID
        
    Returns:
        HTML string with inline styles, table layout (email-safe)
    """
    org = org_service.get_org_by_id(db, org_id)
    user = user_service.get_user_by_id(db, user_id)
    
    if not org or not user:
        return ""
    
    template = org.signature_template or DEFAULT_TEMPLATE
    
    # Get rendering function
    renderer = TEMPLATE_RENDERERS.get(template, _render_classic)
    return renderer(org, user)


def _get_base_data(org: Organization, user: User) -> dict:
    """Extract and escape signature data from org and user.

    Signature override fields (signature_name, etc.) take precedence if set,
    otherwise falls back to profile values (display_name, etc.).
    """
    primary_color = validate_hex_color(org.signature_primary_color) or "#0066cc"

    # Parse org social links from JSONB
    org_social_links = []
    if org.signature_social_links:
        for link in org.signature_social_links:
            platform = escape_text(link.get("platform", ""))
            url = validate_url(link.get("url"))
            if platform and url:
                org_social_links.append({"platform": platform, "url": url})

    # Use signature overrides with fallback to profile values
    effective_name = getattr(user, "signature_name", None) or user.display_name
    effective_title = getattr(user, "signature_title", None) or getattr(user, "title", None)
    effective_phone = getattr(user, "signature_phone", None) or getattr(user, "phone", None)
    effective_photo = getattr(user, "signature_photo_url", None) or user.avatar_url

    return {
        # Org branding (all HTML-escaped)
        "logo_url": escape_text(org.signature_logo_url),
        "primary_color": primary_color,
        "company_name": escape_text(org.signature_company_name or org.name),
        "address": escape_text(org.signature_address),
        "org_phone": escape_text(org.signature_phone),
        "website": validate_url(org.signature_website),
        "org_social_links": org_social_links,
        "disclaimer": escape_text(org.signature_disclaimer),

        # User info with signature override fallback (HTML-escaped)
        "name": escape_text(effective_name),
        "email": escape_text(user.email),  # Email is not overridable
        "user_phone": escape_text(effective_phone),
        "user_title": escape_text(effective_title),
        "phone": escape_text(effective_phone),  # Alias for templates that use "phone"
        "photo_url": effective_photo,  # Not escaped - it's a URL

        # User social links (validated)
        "linkedin": validate_url(user.signature_linkedin),
        "twitter": validate_url(user.signature_twitter),
        "instagram": validate_url(user.signature_instagram),
    }


def _get_sample_data(org: Organization) -> dict:
    """Get sample data for org-level preview (not using admin's personal info).

    Keys match _get_base_data() to prevent preview drift.
    """
    primary_color = validate_hex_color(org.signature_primary_color) or "#0066cc"

    # Parse org social links from JSONB
    org_social_links = []
    if org.signature_social_links:
        for link in org.signature_social_links:
            platform = escape_text(link.get("platform", ""))
            url = validate_url(link.get("url"))
            if platform and url:
                org_social_links.append({"platform": platform, "url": url})

    return {
        # Org branding (all HTML-escaped)
        "logo_url": escape_text(org.signature_logo_url),
        "primary_color": primary_color,
        "company_name": escape_text(org.signature_company_name or org.name),
        "address": escape_text(org.signature_address),
        "org_phone": escape_text(org.signature_phone),
        "website": validate_url(org.signature_website),
        "org_social_links": org_social_links,
        "disclaimer": escape_text(org.signature_disclaimer),

        # Sample user profile (not real admin data) - same keys as _get_base_data()
        "name": "Jane Doe",
        "email": "jane.doe@example.com",
        "user_phone": "(555) 123-4567",
        "user_title": "Case Manager",
        "phone": "(555) 123-4567",  # Alias for templates
        "photo_url": None,  # Sample has no photo

        # Sample user social links
        "linkedin": "https://linkedin.com/in/sample",
        "twitter": None,
        "instagram": None,
    }


def _render_social_links(data: dict, style: str = "") -> str:
    """Render text-only social links (user + org)."""
    links = []
    # User social links
    if data.get("linkedin"):
        links.append(f'<a href="{data["linkedin"]}" style="color: {data["primary_color"]}; text-decoration: none;">LinkedIn</a>')
    if data.get("twitter"):
        links.append(f'<a href="{data["twitter"]}" style="color: {data["primary_color"]}; text-decoration: none;">Twitter</a>')
    if data.get("instagram"):
        links.append(f'<a href="{data["instagram"]}" style="color: {data["primary_color"]}; text-decoration: none;">Instagram</a>')

    # Org social links
    for link in data.get("org_social_links", []):
        links.append(f'<a href="{link["url"]}" style="color: {data["primary_color"]}; text-decoration: none;">{link["platform"]}</a>')

    if not links:
        return ""

    return f'<p style="margin: 8px 0 0 0; font-size: 12px; {style}">' + " | ".join(links) + "</p>"


def _render_disclaimer(data: dict) -> str:
    """Render optional compliance disclaimer footer."""
    if not data.get("disclaimer"):
        return ""

    return f'''
    <p style="margin: 16px 0 0 0; font-size: 10px; color: #999999; border-top: 1px solid #e0e0e0; padding-top: 12px;">
        {data["disclaimer"]}
    </p>
    '''


def _render_classic(org: Organization, user: User) -> str:
    """
    Classic template: Traditional horizontal divider, stacked info, subtle colors.
    """
    data = _get_base_data(org, user)

    html_parts = [
        '<table cellpadding="0" cellspacing="0" border="0" style="font-family: Arial, sans-serif; font-size: 14px; color: #333333;">',
        "<tr><td>",
        '<div style="border-top: 2px solid #e0e0e0; padding-top: 16px; margin-top: 16px;">',
    ]

    # Logo
    if data["logo_url"]:
        html_parts.append(f'<img src="{data["logo_url"]}" alt="{data["company_name"]}" style="max-height: 50px; max-width: 200px; margin-bottom: 12px; display: block;" />')

    # Name and Title
    name_line = data["name"]
    if data.get("user_title"):
        name_line += f' | {data["user_title"]}'
    html_parts.append(f'<p style="margin: 0 0 4px 0; font-weight: 600; color: #1a1a1a;">{name_line}</p>')

    # Company
    if data["company_name"]:
        html_parts.append(f'<p style="margin: 0 0 8px 0; color: #666666;">{data["company_name"]}</p>')

    # Contact info (user phone + email)
    contact_parts = []
    if data.get("user_phone"):
        contact_parts.append(data["user_phone"])
    if data["email"]:
        contact_parts.append(f'<a href="mailto:{data["email"]}" style="color: {data["primary_color"]}; text-decoration: none;">{data["email"]}</a>')

    if contact_parts:
        html_parts.append(f'<p style="margin: 0 0 4px 0; color: #666666;">{" | ".join(contact_parts)}</p>')

    # Org phone (if different from user)
    if data.get("org_phone"):
        html_parts.append(f'<p style="margin: 0 0 4px 0; color: #666666; font-size: 12px;">Office: {data["org_phone"]}</p>')

    # Address
    if data["address"]:
        html_parts.append(f'<p style="margin: 0 0 4px 0; color: #666666; font-size: 12px;">{data["address"]}</p>')

    # Website
    if data["website"]:
        html_parts.append(f'<p style="margin: 0; color: #666666; font-size: 12px;"><a href="{data["website"]}" style="color: {data["primary_color"]}; text-decoration: none;">{data["website"]}</a></p>')

    # Social links
    html_parts.append(_render_social_links(data))

    # Disclaimer
    html_parts.append(_render_disclaimer(data))

    html_parts.extend([
        "</div>",
        "</td></tr>",
        "</table>",
    ])

    return "".join(html_parts)


def _render_modern(org: Organization, user: User) -> str:
    """
    Modern template: Logo left, info right, accent color bar.
    """
    data = _get_base_data(org, user)
    
    html_parts = [
        '<table cellpadding="0" cellspacing="0" border="0" style="font-family: Arial, sans-serif; font-size: 14px; color: #333333; margin-top: 16px;">',
        "<tr>",
        # Left: accent bar + logo
        f'<td style="border-left: 4px solid {data["primary_color"]}; padding-left: 16px; vertical-align: top;">',
    ]
    
    if data["logo_url"]:
        html_parts.append(f'<img src="{data["logo_url"]}" alt="{data["company_name"]}" style="max-height: 60px; max-width: 120px; display: block;" />')
    
    html_parts.extend([
        "</td>",
        # Right: contact info
        '<td style="padding-left: 16px; vertical-align: top;">',
        f'<p style="margin: 0 0 4px 0; font-weight: 600; font-size: 16px; color: #1a1a1a;">{data["name"]}</p>',
    ])
    
    if data["company_name"]:
        html_parts.append(f'<p style="margin: 0 0 8px 0; color: {data["primary_color"]}; font-weight: 500;">{data["company_name"]}</p>')
    
    # Contact
    if data["phone"]:
        html_parts.append(f'<p style="margin: 0 0 2px 0; color: #666666; font-size: 13px;">{data["phone"]}</p>')
    if data["email"]:
        html_parts.append(f'<p style="margin: 0 0 2px 0; font-size: 13px;"><a href="mailto:{data["email"]}" style="color: {data["primary_color"]}; text-decoration: none;">{data["email"]}</a></p>')
    if data["website"]:
        html_parts.append(f'<p style="margin: 0; font-size: 13px;"><a href="{data["website"]}" style="color: {data["primary_color"]}; text-decoration: none;">{data["website"]}</a></p>')
    
    html_parts.append(_render_social_links(data))
    
    html_parts.extend([
        "</td>",
        "</tr>",
        "</table>",
    ])
    
    return "".join(html_parts)


def _render_minimal(org: Organization, user: User) -> str:
    """
    Minimal template: Single line name | title | phone | email.
    """
    data = _get_base_data(org, user)
    
    parts = [data["name"]]
    if data["company_name"]:
        parts.append(data["company_name"])
    if data["phone"]:
        parts.append(data["phone"])
    if data["email"]:
        parts.append(f'<a href="mailto:{data["email"]}" style="color: {data["primary_color"]}; text-decoration: none;">{data["email"]}</a>')
    
    info_line = " | ".join(parts)
    
    social_parts = []
    if data["linkedin"]:
        social_parts.append(f'<a href="{data["linkedin"]}" style="color: {data["primary_color"]}; text-decoration: none;">LinkedIn</a>')
    if data["twitter"]:
        social_parts.append(f'<a href="{data["twitter"]}" style="color: {data["primary_color"]}; text-decoration: none;">Twitter</a>')
    if data["instagram"]:
        social_parts.append(f'<a href="{data["instagram"]}" style="color: {data["primary_color"]}; text-decoration: none;">Instagram</a>')
    
    social_line = " · ".join(social_parts) if social_parts else ""
    
    html = f'''
    <table cellpadding="0" cellspacing="0" border="0" style="font-family: Arial, sans-serif; font-size: 13px; color: #666666; margin-top: 16px; border-top: 1px solid #e0e0e0; padding-top: 12px;">
        <tr><td style="padding-top: 12px;">{info_line}</td></tr>
    '''
    
    if social_line:
        html += f'<tr><td style="padding-top: 4px;">{social_line}</td></tr>'
    
    html += "</table>"
    
    return html


def _render_professional(org: Organization, user: User) -> str:
    """
    Professional template: Full contact block with all details.
    """
    data = _get_base_data(org, user)
    
    html_parts = [
        '<table cellpadding="0" cellspacing="0" border="0" style="font-family: Arial, sans-serif; font-size: 14px; color: #333333; margin-top: 20px;">',
        "<tr>",
    ]
    
    # Logo column
    if data["logo_url"]:
        html_parts.append(f'''
            <td style="vertical-align: top; padding-right: 20px; border-right: 1px solid #e0e0e0;">
                <img src="{data["logo_url"]}" alt="{data["company_name"]}" style="max-height: 80px; max-width: 150px; display: block;" />
            </td>
        ''')
    
    # Info column
    html_parts.append('<td style="vertical-align: top; padding-left: 20px;">')
    html_parts.append(f'<p style="margin: 0 0 2px 0; font-weight: 700; font-size: 16px; color: #1a1a1a;">{data["name"]}</p>')
    
    if data["company_name"]:
        html_parts.append(f'<p style="margin: 0 0 12px 0; color: {data["primary_color"]}; font-size: 14px;">{data["company_name"]}</p>')
    
    # Contact table
    html_parts.append('<table cellpadding="0" cellspacing="0" border="0" style="font-size: 13px; color: #666666;">')
    
    if data["phone"]:
        html_parts.append(f'<tr><td style="padding: 2px 8px 2px 0; font-weight: 500;">Phone:</td><td>{data["phone"]}</td></tr>')
    if data["email"]:
        html_parts.append(f'<tr><td style="padding: 2px 8px 2px 0; font-weight: 500;">Email:</td><td><a href="mailto:{data["email"]}" style="color: {data["primary_color"]}; text-decoration: none;">{data["email"]}</a></td></tr>')
    if data["website"]:
        html_parts.append(f'<tr><td style="padding: 2px 8px 2px 0; font-weight: 500;">Web:</td><td><a href="{data["website"]}" style="color: {data["primary_color"]}; text-decoration: none;">{data["website"]}</a></td></tr>')
    if data["address"]:
        html_parts.append(f'<tr><td style="padding: 2px 8px 2px 0; font-weight: 500;">Address:</td><td>{data["address"]}</td></tr>')
    
    html_parts.append("</table>")
    html_parts.append(_render_social_links(data, "margin-top: 8px;"))
    
    html_parts.extend([
        "</td>",
        "</tr>",
        "</table>",
    ])
    
    return "".join(html_parts)


def _render_creative(org: Organization, user: User) -> str:
    """
    Creative template: Gradient accent, prominent logo, social pills.
    """
    data = _get_base_data(org, user)
    color = data["primary_color"]
    
    html_parts = [
        f'<table cellpadding="0" cellspacing="0" border="0" style="font-family: Arial, sans-serif; font-size: 14px; color: #333333; margin-top: 20px; background: linear-gradient(90deg, {color}10 0%, transparent 100%); padding: 16px; border-radius: 8px;">',
        "<tr><td>",
    ]
    
    # Logo
    if data["logo_url"]:
        html_parts.append(f'<img src="{data["logo_url"]}" alt="{data["company_name"]}" style="max-height: 60px; max-width: 200px; margin-bottom: 12px; display: block;" />')
    
    # Name with accent
    html_parts.append(f'<p style="margin: 0 0 4px 0; font-weight: 700; font-size: 18px; color: {color};">{data["name"]}</p>')
    
    if data["company_name"]:
        html_parts.append(f'<p style="margin: 0 0 12px 0; color: #666666; font-size: 14px;">{data["company_name"]}</p>')
    
    # Contact as horizontal pills
    contact_pills = []
    if data["phone"]:
        contact_pills.append(f'<span style="background: {color}15; padding: 4px 12px; border-radius: 16px; margin-right: 8px; display: inline-block;">{data["phone"]}</span>')
    if data["email"]:
        contact_pills.append(f'<a href="mailto:{data["email"]}" style="background: {color}15; padding: 4px 12px; border-radius: 16px; margin-right: 8px; display: inline-block; color: {color}; text-decoration: none;">{data["email"]}</a>')
    
    if contact_pills:
        html_parts.append(f'<p style="margin: 0 0 8px 0;">{"".join(contact_pills)}</p>')
    
    # Website
    if data["website"]:
        html_parts.append(f'<p style="margin: 0 0 8px 0;"><a href="{data["website"]}" style="color: {color}; text-decoration: underline;">{data["website"]}</a></p>')
    
    social_links = _render_social_links(data)
    if social_links:
        html_parts.append(social_links)
    
    html_parts.extend([
        "</td></tr>",
        "</table>",
    ])
    
    return "".join(html_parts)


# Template renderer registry
TEMPLATE_RENDERERS = {
    "classic": _render_classic,
    "modern": _render_modern,
    "minimal": _render_minimal,
    "professional": _render_professional,
    "creative": _render_creative,
}


def get_available_templates() -> list[dict]:
    """Get list of available templates with metadata."""
    return [
        {
            "id": "classic",
            "name": "Classic",
            "description": "Traditional horizontal divider with stacked info",
        },
        {
            "id": "modern",
            "name": "Modern",
            "description": "Logo left, info right with accent bar",
        },
        {
            "id": "minimal",
            "name": "Minimal",
            "description": "Clean single-line format",
        },
        {
            "id": "professional",
            "name": "Professional",
            "description": "Full contact block with labeled fields",
        },
        {
            "id": "creative",
            "name": "Creative",
            "description": "Vibrant style with gradient accent",
        },
    ]


def render_signature_preview(
    db: Session,
    org_id: uuid.UUID,
) -> str:
    """
    Render signature preview with sample user data.

    This is for org-level preview (admins configuring templates)
    and uses placeholder user data instead of the admin's personal info.

    Args:
        db: Database session
        org_id: Organization ID

    Returns:
        HTML string with inline styles, table layout (email-safe)
    """
    org = org_service.get_org_by_id(db, org_id)

    if not org:
        return ""

    template = org.signature_template or DEFAULT_TEMPLATE
    data = _get_sample_data(org)

    # Use a variant that works with raw data dict
    return _render_from_data(data, template)


def _render_from_data(data: dict, template: str) -> str:
    """Render signature from pre-built data dict (for preview)."""
    html_parts = [
        '<table cellpadding="0" cellspacing="0" border="0" style="font-family: Arial, sans-serif; font-size: 14px; color: #333333;">',
        "<tr><td>",
        '<div style="border-top: 2px solid #e0e0e0; padding-top: 16px; margin-top: 16px;">',
    ]

    # Logo
    if data.get("logo_url"):
        html_parts.append(f'<img src="{data["logo_url"]}" alt="{data.get("company_name", "")}" style="max-height: 50px; max-width: 200px; margin-bottom: 12px; display: block;" />')

    # Name and Title
    name_line = data.get("name", "")
    if data.get("user_title"):
        name_line += f' | {data["user_title"]}'
    html_parts.append(f'<p style="margin: 0 0 4px 0; font-weight: 600; color: #1a1a1a;">{name_line}</p>')

    # Company
    if data.get("company_name"):
        html_parts.append(f'<p style="margin: 0 0 8px 0; color: #666666;">{data["company_name"]}</p>')

    # Contact info (user phone + email)
    contact_parts = []
    if data.get("user_phone"):
        contact_parts.append(data["user_phone"])
    if data.get("email"):
        contact_parts.append(f'<a href="mailto:{data["email"]}" style="color: {data["primary_color"]}; text-decoration: none;">{data["email"]}</a>')

    if contact_parts:
        html_parts.append(f'<p style="margin: 0 0 4px 0; color: #666666;">{" | ".join(contact_parts)}</p>')

    # Org phone
    if data.get("org_phone"):
        html_parts.append(f'<p style="margin: 0 0 4px 0; color: #666666; font-size: 12px;">Office: {data["org_phone"]}</p>')

    # Address
    if data.get("address"):
        html_parts.append(f'<p style="margin: 0 0 4px 0; color: #666666; font-size: 12px;">{data["address"]}</p>')

    # Website
    if data.get("website"):
        html_parts.append(f'<p style="margin: 0; color: #666666; font-size: 12px;"><a href="{data["website"]}" style="color: {data["primary_color"]}; text-decoration: none;">{data["website"]}</a></p>')

    # Social links
    html_parts.append(_render_social_links(data))

    # Disclaimer
    html_parts.append(_render_disclaimer(data))

    html_parts.extend([
        "</div>",
        "</td></tr>",
        "</table>",
    ])

    return "".join(html_parts)
