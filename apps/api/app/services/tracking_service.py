"""
Email Tracking Service.

Handles tracking pixel generation, link wrapping, and recording
open/click events for campaign analytics.
"""

import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote, unquote
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import CampaignRecipient, CampaignTrackingEvent


logger = logging.getLogger(__name__)


# =============================================================================
# Token Generation
# =============================================================================


def generate_tracking_token() -> str:
    """Generate a unique tracking token for a recipient."""
    return secrets.token_urlsafe(32)


# =============================================================================
# URL Generation
# =============================================================================


def get_tracking_base_url() -> str:
    """Get the base URL for tracking endpoints."""
    # Use API_BASE_URL from settings, or construct from known values
    base = getattr(settings, "API_BASE_URL", None)
    if base:
        return base.rstrip("/")
    # Fallback for development
    return "http://localhost:8000"


def get_tracking_pixel_url(token: str) -> str:
    """Get the URL for the tracking pixel (open tracking)."""
    base = get_tracking_base_url()
    return f"{base}/tracking/open/{token}"


def get_tracked_link_url(token: str, original_url: str) -> str:
    """Get the tracking URL for a link (click tracking)."""
    base = get_tracking_base_url()
    encoded_url = quote(original_url, safe="")
    return f"{base}/tracking/click/{token}?url={encoded_url}"


# =============================================================================
# Email Content Transformation
# =============================================================================


def inject_tracking_pixel(html_body: str, token: str) -> str:
    """
    Inject a 1x1 tracking pixel into the email body.

    Adds the pixel just before the closing </body> tag,
    or at the end if no </body> tag exists.
    """
    pixel_url = get_tracking_pixel_url(token)
    pixel_html = f'<img src="{pixel_url}" width="1" height="1" style="display:block;width:1px;height:1px;border:0;" alt="" />'

    # Try to insert before </body>
    body_close_pattern = re.compile(r"(</body>)", re.IGNORECASE)
    if body_close_pattern.search(html_body):
        return body_close_pattern.sub(f"{pixel_html}\\1", html_body, count=1)

    # No </body> tag, append to end
    return html_body + pixel_html


def wrap_links_in_email(html_body: str, token: str) -> str:
    """
    Replace all links in the email with tracking links.

    Finds all <a href="..."> tags and wraps the URLs
    through the click tracking endpoint.
    """

    def replace_link(match):
        original_url = match.group(2)

        # Skip mailto:, tel:, and anchor links
        if original_url.startswith(("mailto:", "tel:", "#", "{{")):
            return match.group(0)

        # Skip tracking URLs (avoid double-wrapping)
        if "/tracking/click/" in original_url:
            return match.group(0)

        tracked_url = get_tracked_link_url(token, original_url)
        return f'{match.group(1)}"{tracked_url}"'

    # Match <a href="..." or <a href='...'
    link_pattern = re.compile(
        r'(<a\s+[^>]*href\s*=\s*)["\']([^"\']+)["\']', re.IGNORECASE
    )
    return link_pattern.sub(replace_link, html_body)


def prepare_email_for_tracking(html_body: str, token: str) -> str:
    """
    Prepare an email body for tracking.

    Injects tracking pixel and wraps all links.
    """
    # First wrap links, then inject pixel
    body = wrap_links_in_email(html_body, token)
    body = inject_tracking_pixel(body, token)
    return body


# =============================================================================
# Event Recording
# =============================================================================


def record_open(
    db: Session,
    token: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> bool:
    """
    Record an email open event.

    Returns True if the event was recorded, False if token not found.
    """
    recipient = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.tracking_token == token)
        .first()
    )

    if not recipient:
        return False

    # Record the event
    event = CampaignTrackingEvent(
        recipient_id=recipient.id,
        event_type="open",
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(event)

    # Update recipient counters
    recipient.open_count += 1
    if not recipient.opened_at:
        recipient.opened_at = datetime.now(timezone.utc)

        # Update run opened_count (first open only)
        run = recipient.run
        if run:
            run.opened_count += 1

    db.commit()
    return True


def record_click(
    db: Session,
    token: str,
    url: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Optional[str]:
    """
    Record a link click event.

    Returns the original URL to redirect to, or None if token not found.
    """
    recipient = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.tracking_token == token)
        .first()
    )

    if not recipient:
        return None

    # Decode the URL
    original_url = unquote(url)

    # Record the event
    event = CampaignTrackingEvent(
        recipient_id=recipient.id,
        event_type="click",
        url=original_url,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(event)

    # Update recipient counters
    recipient.click_count += 1
    if not recipient.clicked_at:
        recipient.clicked_at = datetime.now(timezone.utc)

        # Update run clicked_count (first click only)
        run = recipient.run
        if run:
            run.clicked_count += 1

    db.commit()
    return original_url


# =============================================================================
# Analytics
# =============================================================================


def get_recipient_events(
    db: Session,
    recipient_id: UUID,
    limit: int = 100,
) -> list[CampaignTrackingEvent]:
    """Get tracking events for a specific recipient."""
    return (
        db.query(CampaignTrackingEvent)
        .filter(CampaignTrackingEvent.recipient_id == recipient_id)
        .order_by(CampaignTrackingEvent.created_at.desc())
        .limit(limit)
        .all()
    )


def get_run_events(
    db: Session,
    run_id: UUID,
    event_type: Optional[str] = None,
    limit: int = 1000,
) -> list[CampaignTrackingEvent]:
    """Get all tracking events for a campaign run."""
    query = (
        db.query(CampaignTrackingEvent)
        .join(
            CampaignRecipient,
            CampaignTrackingEvent.recipient_id == CampaignRecipient.id,
        )
        .filter(CampaignRecipient.run_id == run_id)
    )

    if event_type:
        query = query.filter(CampaignTrackingEvent.event_type == event_type)

    return query.order_by(CampaignTrackingEvent.created_at.desc()).limit(limit).all()
