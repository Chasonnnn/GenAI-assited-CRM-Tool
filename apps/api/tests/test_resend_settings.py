"""Tests for Resend settings service and email provider resolution."""

import httpx
import pytest


class TestResendSettingsEncryption:
    """Test encryption/decryption/masking functions."""

    def test_encrypt_decrypt_roundtrip(self):
        from app.services import resend_settings_service

        original = "re_test_api_key_12345"
        encrypted = resend_settings_service.encrypt_api_key(original)

        # Encrypted value should be different from original
        assert encrypted != original

        # Should decrypt back to original
        decrypted = resend_settings_service.decrypt_api_key(encrypted)
        assert decrypted == original

    def test_mask_api_key_shows_partial(self):
        from app.services import resend_settings_service

        original = "re_test_api_key_12345"
        encrypted = resend_settings_service.encrypt_api_key(original)
        masked = resend_settings_service.mask_api_key(encrypted)

        # Should show first 4 and last 4 chars
        assert masked == "re_t...2345"

    def test_mask_api_key_none_returns_none(self):
        from app.services import resend_settings_service

        assert resend_settings_service.mask_api_key(None) is None

    def test_mask_api_key_short_key(self):
        from app.services import resend_settings_service

        short_key = "abcd"
        encrypted = resend_settings_service.encrypt_api_key(short_key)
        masked = resend_settings_service.mask_api_key(encrypted)

        # Short keys should be fully masked
        assert masked == "****"


class TestResendSettingsCRUD:
    """Test settings CRUD operations."""

    def test_get_or_create_creates_new_settings(self, db, test_org):
        from app.services import resend_settings_service

        # Should not exist initially
        settings = resend_settings_service.get_resend_settings(db, test_org.id)
        assert settings is None

        # Create new settings
        settings = resend_settings_service.get_or_create_resend_settings(
            db, test_org.id, test_org.id
        )
        assert settings is not None
        assert settings.organization_id == test_org.id
        assert settings.email_provider is None  # Not configured
        assert settings.webhook_id is not None
        assert settings.current_version == 1

    def test_get_or_create_returns_existing(self, db, test_org):
        from app.services import resend_settings_service

        # Create initial settings
        settings1 = resend_settings_service.get_or_create_resend_settings(
            db, test_org.id, test_org.id
        )

        # Should return same settings
        settings2 = resend_settings_service.get_or_create_resend_settings(
            db, test_org.id, test_org.id
        )

        assert settings1.id == settings2.id

    def test_update_resend_settings(self, db, test_org):
        from app.services import resend_settings_service

        user_id = test_org.id  # Use org_id as placeholder user_id

        # Create initial settings
        settings = resend_settings_service.get_or_create_resend_settings(db, test_org.id, user_id)
        initial_version = settings.current_version

        # Update settings
        updated = resend_settings_service.update_resend_settings(
            db,
            test_org.id,
            user_id,
            email_provider="resend",
            api_key="re_test_key_123",
            from_email="no-reply@example.com",
            from_name="Test Org",
        )

        assert updated.email_provider == "resend"
        assert updated.api_key_encrypted is not None
        assert updated.from_email == "no-reply@example.com"
        assert updated.from_name == "Test Org"
        assert updated.current_version == initial_version + 1

    def test_update_clears_empty_values(self, db, test_org):
        from app.services import resend_settings_service

        user_id = test_org.id

        # Set initial values
        resend_settings_service.update_resend_settings(
            db,
            test_org.id,
            user_id,
            email_provider="resend",
            from_email="test@example.com",
        )

        # Clear email provider
        updated = resend_settings_service.update_resend_settings(
            db,
            test_org.id,
            user_id,
            email_provider="",
        )

        assert updated.email_provider is None


class TestResendSettingsWebhook:
    """Test webhook ID lookup and rotation."""

    def test_get_settings_by_webhook_id(self, db, test_org):
        from app.services import resend_settings_service

        settings = resend_settings_service.get_or_create_resend_settings(
            db, test_org.id, test_org.id
        )
        webhook_id = settings.webhook_id

        # Should find settings by webhook_id
        found = resend_settings_service.get_settings_by_webhook_id(db, webhook_id)
        assert found is not None
        assert found.id == settings.id

    def test_get_settings_by_invalid_webhook_id(self, db, test_org):
        from app.services import resend_settings_service

        resend_settings_service.get_or_create_resend_settings(db, test_org.id, test_org.id)

        # Should not find settings with invalid webhook_id
        found = resend_settings_service.get_settings_by_webhook_id(db, "invalid-id")
        assert found is None

    def test_rotate_webhook_id(self, db, test_org):
        from app.services import resend_settings_service

        settings = resend_settings_service.get_or_create_resend_settings(
            db, test_org.id, test_org.id
        )
        initial_webhook_id = settings.webhook_id

        # Rotate webhook id
        updated = resend_settings_service.rotate_webhook_id(db, test_org.id, test_org.id)

        assert updated.webhook_id != initial_webhook_id


class TestFromEmailValidation:
    """Test from_email domain validation."""

    def test_validate_from_email_valid(self):
        from app.services import resend_settings_service

        is_valid, error = resend_settings_service.validate_from_email(
            "no-reply@example.com", "example.com"
        )
        assert is_valid is True
        assert error is None

    def test_validate_from_email_wrong_domain(self):
        from app.services import resend_settings_service

        is_valid, error = resend_settings_service.validate_from_email(
            "no-reply@other.com", "example.com"
        )
        assert is_valid is False
        assert "verified domain" in error.lower()

    def test_validate_from_email_no_domain(self):
        from app.services import resend_settings_service

        is_valid, error = resend_settings_service.validate_from_email("no-reply@example.com", None)
        assert is_valid is False
        assert "no verified domain" in error.lower()

    def test_validate_from_email_invalid_format(self):
        from app.services import resend_settings_service

        is_valid, error = resend_settings_service.validate_from_email(
            "invalid-email", "example.com"
        )
        assert is_valid is False
        assert "invalid" in error.lower()


class TestEmailProviderResolver:
    """Test email provider resolution."""

    def test_resolve_provider_not_configured(self, db, test_org):
        from app.services import email_provider_service, resend_settings_service

        # Create settings without provider
        resend_settings_service.get_or_create_resend_settings(db, test_org.id, test_org.id)

        with pytest.raises(email_provider_service.ConfigurationError) as exc:
            email_provider_service.resolve_campaign_provider(db, test_org.id)

        assert "not configured" in str(exc.value).lower()

    def test_resolve_resend_missing_api_key(self, db, test_org):
        from app.services import email_provider_service, resend_settings_service

        # Create settings with Resend but no API key
        resend_settings_service.update_resend_settings(
            db,
            test_org.id,
            test_org.id,
            email_provider="resend",
        )

        with pytest.raises(email_provider_service.ConfigurationError) as exc:
            email_provider_service.resolve_campaign_provider(db, test_org.id)

        assert "api key" in str(exc.value).lower()

    def test_resolve_resend_missing_from_email(self, db, test_org):
        from app.services import email_provider_service, resend_settings_service

        # Create settings with Resend and API key but no from_email
        resend_settings_service.update_resend_settings(
            db,
            test_org.id,
            test_org.id,
            email_provider="resend",
            api_key="re_test_key",
        )

        with pytest.raises(email_provider_service.ConfigurationError) as exc:
            email_provider_service.resolve_campaign_provider(db, test_org.id)

        assert "from email" in str(exc.value).lower()

    def test_resolve_resend_success(self, db, test_org):
        from app.services import email_provider_service, resend_settings_service

        # Create complete Resend settings
        resend_settings_service.update_resend_settings(
            db,
            test_org.id,
            test_org.id,
            email_provider="resend",
            api_key="re_test_key",
            from_email="no-reply@example.com",
            verified_domain="example.com",
        )

        provider_type, config = email_provider_service.resolve_campaign_provider(db, test_org.id)

        assert provider_type == "resend"
        assert config.from_email == "no-reply@example.com"

    def test_resolve_gmail_missing_sender(self, db, test_org):
        from app.services import email_provider_service, resend_settings_service

        # Create settings with Gmail but no sender
        resend_settings_service.update_resend_settings(
            db,
            test_org.id,
            test_org.id,
            email_provider="gmail",
        )

        with pytest.raises(email_provider_service.ConfigurationError) as exc:
            email_provider_service.resolve_campaign_provider(db, test_org.id)

        assert "sender not configured" in str(exc.value).lower()


class TestResendEmailService:
    """Test Resend email sending service."""

    @pytest.mark.asyncio
    async def test_send_email_direct_success(self, monkeypatch):
        from app.services import resend_email_service

        async def fake_request_with_retries(request_fn, **kwargs):
            return httpx.Response(200, json={"id": "msg_123"})

        monkeypatch.setattr(resend_email_service, "request_with_retries", fake_request_with_retries)

        success, error, message_id = await resend_email_service.send_email_direct(
            api_key="re_test_key",
            to_email="recipient@example.com",
            subject="Test Subject",
            body="<p>Test body</p>",
            from_email="sender@example.com",
            from_name="Sender Name",
        )

        assert success is True
        assert error is None
        assert message_id == "msg_123"

    @pytest.mark.asyncio
    async def test_send_email_direct_treats_409_as_success(self, monkeypatch):
        from app.services import resend_email_service

        async def fake_request_with_retries(request_fn, **kwargs):
            return httpx.Response(409, json={"id": "msg_dup"})

        monkeypatch.setattr(resend_email_service, "request_with_retries", fake_request_with_retries)

        success, error, message_id = await resend_email_service.send_email_direct(
            api_key="re_test_key",
            to_email="recipient@example.com",
            subject="Test Subject",
            body="<p>Test body</p>",
            from_email="sender@example.com",
            idempotency_key="dup-key",
        )

        # 409 (idempotency conflict) should be treated as success
        assert success is True
        assert error is None

    @pytest.mark.asyncio
    async def test_send_email_direct_failure(self, monkeypatch):
        from app.services import resend_email_service

        async def fake_request_with_retries(request_fn, **kwargs):
            return httpx.Response(401, json={"error": "Invalid API key"})

        monkeypatch.setattr(resend_email_service, "request_with_retries", fake_request_with_retries)

        success, error, message_id = await resend_email_service.send_email_direct(
            api_key="re_invalid_key",
            to_email="recipient@example.com",
            subject="Test Subject",
            body="<p>Test body</p>",
            from_email="sender@example.com",
        )

        assert success is False
        assert error is not None
        assert "401" in error
        assert message_id is None

    @pytest.mark.asyncio
    async def test_send_email_direct_generates_text(self, monkeypatch):
        from app.services import resend_email_service

        captured_payload = {}

        async def fake_request_with_retries(request_fn, **kwargs):
            # Call the request function to capture the payload
            response = httpx.Response(200, json={"id": "msg_text"})
            return response

        # Patch at httpx.AsyncClient level to capture the request
        async def capture_post(self, url, **kwargs):
            captured_payload.update(kwargs.get("json", {}))
            return httpx.Response(200, json={"id": "msg_text"})

        monkeypatch.setattr(httpx.AsyncClient, "post", capture_post)

        await resend_email_service.send_email_direct(
            api_key="re_test_key",
            to_email="recipient@example.com",
            subject="Test Subject",
            body="<p>Hello <strong>World</strong></p>",
            from_email="sender@example.com",
        )

        # Should have generated text version
        assert "text" in captured_payload
        assert "Hello" in captured_payload["text"]
        assert "World" in captured_payload["text"]
        assert "<" not in captured_payload["text"]  # No HTML tags

    @pytest.mark.asyncio
    async def test_send_email_direct_sets_list_unsubscribe(self, monkeypatch):
        from app.services import resend_email_service

        captured_payload = {}

        async def capture_post(self, url, **kwargs):
            captured_payload.update(kwargs.get("json", {}))
            return httpx.Response(200, json={"id": "msg_unsub"})

        monkeypatch.setattr(httpx.AsyncClient, "post", capture_post)

        await resend_email_service.send_email_direct(
            api_key="re_test_key",
            to_email="recipient@example.com",
            subject="Test Subject",
            body="<p>Hello World</p>",
            from_email="sender@example.com",
            unsubscribe_url="https://example.com/email/unsubscribe/abc123",
        )

        headers = captured_payload.get("headers") or {}
        assert headers.get("List-Unsubscribe") == "<https://example.com/email/unsubscribe/abc123>"
        assert headers.get("List-Unsubscribe-Post") == "List-Unsubscribe=One-Click"
