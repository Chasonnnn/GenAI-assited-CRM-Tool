from uuid import uuid4


def test_select_sender_prefers_platform_when_configured(monkeypatch):
    from app.services import email_sender, platform_email_service

    monkeypatch.setattr(platform_email_service, "platform_sender_configured", lambda: True)

    selection = email_sender.select_sender(prefer_platform=True, sender_user_id=None)

    assert selection.error is None
    assert selection.integration_key == "resend"
    assert selection.sender is not None
    assert selection.sender.key == "resend"


def test_select_sender_requires_user_when_platform_unavailable(monkeypatch):
    from app.services import email_sender, platform_email_service

    monkeypatch.setattr(platform_email_service, "platform_sender_configured", lambda: False)

    selection = email_sender.select_sender(prefer_platform=True, sender_user_id=None)

    assert selection.sender is None
    assert selection.integration_key is None
    assert selection.error == "No inviter to send from"


def test_select_sender_falls_back_to_gmail_with_user(monkeypatch):
    from app.services import email_sender, platform_email_service

    monkeypatch.setattr(platform_email_service, "platform_sender_configured", lambda: False)

    selection = email_sender.select_sender(prefer_platform=True, sender_user_id=uuid4())

    assert selection.error is None
    assert selection.integration_key == "gmail"
    assert selection.sender is not None
    assert selection.sender.key == "gmail"
