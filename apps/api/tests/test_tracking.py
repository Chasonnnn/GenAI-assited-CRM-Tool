"""
Tests for email tracking service.

Tests token generation, link wrapping, pixel injection,
and open/click event recording.
"""

import pytest
from datetime import datetime, timezone

from app.services import tracking_service


# =============================================================================
# Token Generation Tests
# =============================================================================


def test_generate_tracking_token():
    """Test that tokens are generated with correct format."""
    token = tracking_service.generate_tracking_token()
    assert len(token) == 43  # Base64 URL-safe encoding of 32 bytes
    assert isinstance(token, str)


def test_generate_tracking_token_unique():
    """Test that tokens are unique."""
    tokens = [tracking_service.generate_tracking_token() for _ in range(100)]
    assert len(set(tokens)) == 100


# =============================================================================
# URL Generation Tests
# =============================================================================


def test_get_tracking_pixel_url():
    """Test tracking pixel URL generation."""
    token = "test-token-123"
    url = tracking_service.get_tracking_pixel_url(token)
    assert "/tracking/open/test-token-123" in url


def test_get_tracked_link_url():
    """Test tracked link URL generation."""
    token = "test-token-123"
    original_url = "https://example.com/page?foo=bar"
    url = tracking_service.get_tracked_link_url(token, original_url)
    assert "/tracking/click/test-token-123" in url
    assert "url=" in url
    # URL should be encoded
    assert "https%3A%2F%2F" in url


# =============================================================================
# Email Content Transformation Tests
# =============================================================================


def test_inject_tracking_pixel_with_body_tag():
    """Test pixel injection before </body> tag."""
    html = "<html><body><p>Hello</p></body></html>"
    token = "test-token"
    result = tracking_service.inject_tracking_pixel(html, token)
    
    assert "/tracking/open/test-token" in result
    assert "<img " in result
    assert "</body>" in result
    # Pixel should be before </body>
    assert result.index("<img ") < result.index("</body>")


def test_inject_tracking_pixel_without_body_tag():
    """Test pixel injection when no </body> tag exists."""
    html = "<p>Hello</p>"
    token = "test-token"
    result = tracking_service.inject_tracking_pixel(html, token)
    
    assert "/tracking/open/test-token" in result
    assert result.endswith('alt="" />')


def test_wrap_links_in_email():
    """Test that all links are wrapped with tracking."""
    html = '<a href="https://example.com/page1">Link 1</a> <a href="https://example.com/page2">Link 2</a>'
    token = "test-token"
    result = tracking_service.wrap_links_in_email(html, token)
    
    # Both links should be wrapped
    assert result.count("/tracking/click/test-token") == 2
    assert "https://example.com/page1" not in result.split('url=')[0]
    assert "https://example.com/page2" not in result.split('url=')[0]


def test_wrap_links_skips_mailto():
    """Test that mailto: links are not wrapped."""
    html = '<a href="mailto:test@example.com">Email</a>'
    token = "test-token"
    result = tracking_service.wrap_links_in_email(html, token)
    
    assert "/tracking/click/" not in result
    assert 'href="mailto:test@example.com"' in result


def test_wrap_links_skips_tel():
    """Test that tel: links are not wrapped."""
    html = '<a href="tel:+1234567890">Call</a>'
    token = "test-token"
    result = tracking_service.wrap_links_in_email(html, token)
    
    assert "/tracking/click/" not in result
    assert 'href="tel:+1234567890"' in result


def test_wrap_links_skips_anchor():
    """Test that anchor links are not wrapped."""
    html = '<a href="#section">Jump</a>'
    token = "test-token"
    result = tracking_service.wrap_links_in_email(html, token)
    
    assert "/tracking/click/" not in result
    assert 'href="#section"' in result


def test_wrap_links_skips_template_vars():
    """Test that template variable links are not wrapped."""
    html = '<a href="{{unsubscribe_link}}">Unsubscribe</a>'
    token = "test-token"
    result = tracking_service.wrap_links_in_email(html, token)
    
    assert "/tracking/click/" not in result
    assert 'href="{{unsubscribe_link}}"' in result


def test_prepare_email_for_tracking():
    """Test full email preparation with pixel and link wrapping."""
    html = '<html><body><a href="https://example.com">Link</a></body></html>'
    token = "test-token"
    result = tracking_service.prepare_email_for_tracking(html, token)
    
    # Should have both pixel and wrapped link
    assert "/tracking/open/test-token" in result
    assert "/tracking/click/test-token" in result


# =============================================================================
# Event Recording Tests
# =============================================================================


def test_record_open_creates_event(db, test_org, test_user):
    """Test that recording an open creates an event and updates counters."""
    from app.db.models import CampaignRecipient, CampaignRun, Campaign, EmailTemplate
    from datetime import datetime, timezone
    
    # Create email template first (required by Campaign)
    template = EmailTemplate(
        organization_id=test_org.id,
        name="Test Template",
        subject="Test",
        body="Test body",
    )
    db.add(template)
    db.flush()
    
    # Create campaign structure
    campaign = Campaign(
        organization_id=test_org.id,
        name="Test Campaign",
        recipient_type="case",
        email_template_id=template.id,
    )
    db.add(campaign)
    db.flush()
    
    run = CampaignRun(
        organization_id=test_org.id,
        campaign_id=campaign.id,
        status="running",
    )
    db.add(run)
    db.flush()
    
    token = tracking_service.generate_tracking_token()
    recipient = CampaignRecipient(
        run_id=run.id,
        entity_type="case",
        entity_id=test_org.id,  # Just use org ID for test
        recipient_email="test@example.com",
        status="sent",
        tracking_token=token,
    )
    db.add(recipient)
    db.commit()
    
    # Record open
    result = tracking_service.record_open(
        db=db,
        token=token,
        ip_address="127.0.0.1",
        user_agent="TestAgent/1.0",
    )
    
    assert result is True
    
    db.refresh(recipient)
    assert recipient.open_count == 1
    assert recipient.opened_at is not None
    
    db.refresh(run)
    assert run.opened_count == 1


def test_record_open_increments_count(db, test_org, test_user):
    """Test that multiple opens increment count but only set opened_at once."""
    from app.db.models import CampaignRecipient, CampaignRun, Campaign, EmailTemplate
    
    # Create email template first
    template = EmailTemplate(
        organization_id=test_org.id,
        name="Test Template 2",
        subject="Test",
        body="Test body",
    )
    db.add(template)
    db.flush()
    
    # Create campaign structure
    campaign = Campaign(
        organization_id=test_org.id,
        name="Test Campaign 2",
        recipient_type="case",
        email_template_id=template.id,
    )
    db.add(campaign)
    db.flush()
    
    run = CampaignRun(
        organization_id=test_org.id,
        campaign_id=campaign.id,
        status="running",
    )
    db.add(run)
    db.flush()
    
    token = tracking_service.generate_tracking_token()
    recipient = CampaignRecipient(
        run_id=run.id,
        entity_type="case",
        entity_id=test_org.id,
        recipient_email="test@example.com",
        status="sent",
        tracking_token=token,
    )
    db.add(recipient)
    db.commit()
    
    # Record multiple opens
    tracking_service.record_open(db, token)
    first_opened_at = recipient.opened_at
    
    tracking_service.record_open(db, token)
    tracking_service.record_open(db, token)
    
    db.refresh(recipient)
    assert recipient.open_count == 3
    assert recipient.opened_at == first_opened_at  # Should not change
    
    db.refresh(run)
    assert run.opened_count == 1  # Only increments on first open


def test_record_open_invalid_token(db):
    """Test that invalid token returns False."""
    result = tracking_service.record_open(db, "invalid-token-xyz")
    assert result is False


def test_record_click_creates_event(db, test_org, test_user):
    """Test that recording a click creates an event and updates counters."""
    from app.db.models import CampaignRecipient, CampaignRun, Campaign, EmailTemplate
    
    # Create email template first
    template = EmailTemplate(
        organization_id=test_org.id,
        name="Test Template 3",
        subject="Test",
        body="Test body",
    )
    db.add(template)
    db.flush()
    
    # Create campaign structure
    campaign = Campaign(
        organization_id=test_org.id,
        name="Test Campaign 3",
        recipient_type="case",
        email_template_id=template.id,
    )
    db.add(campaign)
    db.flush()
    
    run = CampaignRun(
        organization_id=test_org.id,
        campaign_id=campaign.id,
        status="running",
    )
    db.add(run)
    db.flush()
    
    token = tracking_service.generate_tracking_token()
    recipient = CampaignRecipient(
        run_id=run.id,
        entity_type="case",
        entity_id=test_org.id,
        recipient_email="test@example.com",
        status="sent",
        tracking_token=token,
    )
    db.add(recipient)
    db.commit()
    
    # Record click
    original_url = "https://example.com/page"
    result = tracking_service.record_click(
        db=db,
        token=token,
        url=original_url,
        ip_address="127.0.0.1",
        user_agent="TestAgent/1.0",
    )
    
    assert result == original_url
    
    db.refresh(recipient)
    assert recipient.click_count == 1
    assert recipient.clicked_at is not None
    
    db.refresh(run)
    assert run.clicked_count == 1


def test_record_click_invalid_token(db):
    """Test that invalid token returns None."""
    result = tracking_service.record_click(db, "invalid-token-xyz", "https://example.com")
    assert result is None
