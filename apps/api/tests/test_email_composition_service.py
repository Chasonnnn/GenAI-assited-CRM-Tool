from app.core.email_layout import EmailLayout
from app.services import email_composition_service, media_service


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


S3_LOGO = "https://crm-attachments.s3.amazonaws.com/logos/org/logo.png"


def _compose(db, org, body, scope="org", layout=None, sender_user_id=None):
    return email_composition_service.compose_template_email_html(
        db=db,
        org_id=org.id,
        recipient_email="recipient@example.com",
        rendered_body_html=body,
        scope=scope,
        layout=layout,
        sender_user_id=sender_user_id,
        portal_base_url="https://app.example.com",
        unsubscribe_url="https://app.example.com/unsubscribe",
    )


def _with_logo(db, org, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "S3_BUCKET", "crm-attachments", raising=False)
    org.signature_logo_url = S3_LOGO
    org.signature_company_name = "Smith & Co"
    db.commit()
    return media_service.email_logo_url(org)


def test_org_email_defaults_to_a_card_with_one_logo_on_top(db, test_org, monkeypatch):
    logo_url = _with_logo(db, test_org, monkeypatch)

    html = _compose(db, test_org, "<p>Welcome</p>")

    assert html.startswith('<table role="presentation"')
    assert 'bgcolor="#f4f4f5"' in html and "max-width: 600px" in html
    assert html.count(logo_url) == 1
    assert html.index(logo_url) < html.index("Welcome") < html.index("Unsubscribe")
    assert 'alt="Smith &amp; Co"' in html


def test_card_has_no_logo_row_without_a_logo(db, test_org):
    test_org.signature_logo_url = None
    db.commit()

    html = _compose(db, test_org, "<p>Welcome</p>")

    assert 'bgcolor="#f4f4f5"' in html
    assert "<img" not in html


def test_card_settings_change_the_logo_and_page(db, test_org, monkeypatch):
    logo_url = _with_logo(db, test_org, monkeypatch)
    layout = EmailLayout(kind="card", logo_position="left", page_background="#e0f2fe")

    html = _compose(db, test_org, "<p>Welcome</p>", layout=layout)

    assert 'bgcolor="#e0f2fe"' in html and "#f4f4f5" not in html
    logo_tag = html[html.rindex("<td", 0, html.index(logo_url)) : html.index(logo_url)]
    assert 'align="left"' in logo_tag
    assert "margin: 0 auto" not in html[html.index(logo_url) - 40 : html.index(logo_url) + 200]


def test_hidden_layout_logo_leaves_the_signature_logo(db, test_org, monkeypatch):
    logo_url = _with_logo(db, test_org, monkeypatch)

    html = _compose(
        db, test_org, "<p>Welcome</p>", layout=EmailLayout(kind="card", show_logo=False)
    )

    # The org signature shows the logo again, below the body.
    assert html.count(logo_url) == 1
    assert html.index("Welcome") < html.index(logo_url)


def test_body_that_places_the_logo_keeps_its_own_placement(db, test_org, monkeypatch):
    logo_url = _with_logo(db, test_org, monkeypatch)

    html = _compose(db, test_org, f'<p>Hi</p><img src="{logo_url}" alt="">')

    # No header logo; the body and the signature keep their own logos.
    assert 'bgcolor="#f4f4f5"' in html
    assert html.index("Hi") < html.index(logo_url)


def test_personal_email_defaults_to_plain_with_side_space(db, test_org, monkeypatch):
    _with_logo(db, test_org, monkeypatch)

    html = _compose(db, test_org, "<p>Welcome</p>", scope="personal")

    assert html.startswith('<table role="presentation"')
    assert "padding: 24px 24px 32px" in html and "max-width: 600px" in html
    assert "#f4f4f5" not in html
    assert "<img" not in html


def test_plain_org_email_keeps_the_logo_in_the_signature(db, test_org, monkeypatch):
    logo_url = _with_logo(db, test_org, monkeypatch)

    html = _compose(db, test_org, "<p>Welcome</p>", layout=EmailLayout(kind="plain"))

    assert "#f4f4f5" not in html
    assert html.count(logo_url) == 1
    assert html.index("Welcome") < html.index(logo_url)


def test_personal_card_leaves_the_logo_out_of_the_sender_signature(
    db, test_org, test_user, monkeypatch
):
    logo_url = _with_logo(db, test_org, monkeypatch)

    html = _compose(
        db,
        test_org,
        "<p>Welcome</p>",
        scope="personal",
        layout=EmailLayout(kind="card"),
        sender_user_id=test_user.id,
    )

    assert html.count(logo_url) == 1
    assert html.index(logo_url) < html.index("Welcome")
    assert test_user.email in html


def test_letterhead_draws_an_accent_rule_under_the_logo(db, test_org, monkeypatch):
    logo_url = _with_logo(db, test_org, monkeypatch)

    html = _compose(db, test_org, "<p>Welcome</p>", layout=EmailLayout(kind="letterhead"))

    rule = "border-top: 3px solid #111827"
    assert "#f4f4f5" not in html
    assert html.index(logo_url) < html.index(rule) < html.index("Welcome")

    test_org.signature_primary_color = "#b8335f"
    db.commit()
    html = _compose(db, test_org, "<p>Welcome</p>", layout=EmailLayout(kind="letterhead"))
    assert "border-top: 3px solid #b8335f" in html

    layout = EmailLayout(kind="letterhead", accent_color="#0f766e")
    html = _compose(db, test_org, "<p>Welcome</p>", layout=layout)
    assert "border-top: 3px solid #0f766e" in html


def test_full_document_template_keeps_its_own_layout(db, test_org, monkeypatch):
    _with_logo(db, test_org, monkeypatch)

    html = _compose(db, test_org, "<html><body><p>Welcome</p></body></html>")

    assert html.startswith("<html><body><p>Welcome</p>")
    assert "#f4f4f5" not in html
    assert html.index("Unsubscribe") < html.index("</body>")


def test_body_and_footer_font_styles_parse_as_one_attribute(db, test_org):
    from html.parser import HTMLParser

    styles: list[str] = []

    class StyleCollector(HTMLParser):
        def handle_starttag(self, tag, attrs):
            styles.extend(value for name, value in attrs if name == "style" and value)

    html = _compose(db, test_org, "<p>Welcome</p>")
    StyleCollector().feed(html)

    body_style = next(style for style in styles if "font-size: 16px" in style)
    footer_style = next(style for style in styles if "font-size: 11px" in style)
    assert "sans-serif" in body_style and "color: #111827" in body_style
    assert "sans-serif" in footer_style and "color: #6b7280" in footer_style
