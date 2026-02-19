from app.services import email_composition_service


def test_compose_template_email_html_uses_emoji_fallback_font_stack_for_body(db, test_org):
    html = email_composition_service.compose_template_email_html(
        db=db,
        org_id=test_org.id,
        recipient_email="recipient@example.com",
        rendered_body_html="<p>Hello 😀</p>",
        scope="org",
        sender_user_id=None,
        portal_base_url="https://app.example.com",
    )

    assert "Apple Color Emoji" in html
    assert "Segoe UI Emoji" in html
    assert "Noto Color Emoji" in html


def test_compose_template_email_html_uses_emoji_fallback_font_stack_for_footer(db, test_org):
    html = email_composition_service.compose_template_email_html(
        db=db,
        org_id=test_org.id,
        recipient_email="recipient@example.com",
        rendered_body_html="<p>Body</p>",
        scope="org",
        sender_user_id=None,
        portal_base_url="https://app.example.com",
    )

    # Footer keeps small text styles but must support color emoji rendering on iOS/macOS.
    assert "font-size: 11px" in html
    assert "Apple Color Emoji" in html
