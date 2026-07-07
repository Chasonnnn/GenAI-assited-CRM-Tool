def test_get_duo_client_strips_and_parses_settings(monkeypatch):
    from app.core.config import settings
    from app.services import duo_service

    monkeypatch.setattr(
        settings,
        "DUO_CLIENT_ID",
        '"DI0PSKDRAH9LIS3Q53PW"' + chr(0x200B) + " \n",
    )
    monkeypatch.setattr(settings, "DUO_CLIENT_SECRET", "secret-with-newline\n")
    monkeypatch.setattr(settings, "DUO_API_HOST", "https://api-85d6198d.duosecurity.com/\n")
    monkeypatch.setattr(settings, "DUO_REDIRECT_URI", "https://app.example.com/auth/duo/callback")

    captured = {}

    class FakeClient:
        def __init__(self, client_id: str, client_secret: str, host: str, redirect_uri: str):
            captured["client_id"] = client_id
            captured["client_secret"] = client_secret
            captured["host"] = host
            captured["redirect_uri"] = redirect_uri

    monkeypatch.setattr(duo_service.duo_universal, "Client", FakeClient)

    duo_service.get_duo_client()

    assert captured["client_id"] == "DI0PSKDRAH9LIS3Q53PW"
    assert captured["client_secret"] == "secret-with-newline"
    assert captured["host"] == "api-85d6198d.duosecurity.com"
    assert captured["redirect_uri"] == "https://app.example.com/auth/duo/callback"


def test_verify_callback_applies_configured_sdk_request_timeout(monkeypatch):
    from pydantic import SecretStr

    from app.core.config import settings
    from app.services import duo_service

    monkeypatch.setattr(settings, "DUO_CLIENT_ID", "DI0PSKDRAH9LIS3Q53PW")
    monkeypatch.setattr(settings, "DUO_CLIENT_SECRET", SecretStr("s" * 40))
    monkeypatch.setattr(settings, "DUO_API_HOST", "api-85d6198d.duosecurity.com")
    monkeypatch.setattr(settings, "DUO_REDIRECT_URI", "https://app.example.com/auth/duo/callback")
    monkeypatch.setattr(settings, "DUO_TIMEOUT_SECONDS", 3.25)

    captured = {}

    class FakeResponse:
        status_code = 200
        content = b'{"stat":"OK"}'

        def json(self):
            return {}

    def fake_post(*_args, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        return FakeResponse()

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def exchange_authorization_code_for_2fa_result(self, *, duoCode, username):
            captured["duo_code"] = duoCode
            captured["username"] = username
            duo_service.duo_client.requests.post("https://duo.example.test/oauth/v1/token")
            return {"sub": "duo-user-1"}

    monkeypatch.setattr(duo_service.duo_universal, "Client", FakeClient)
    monkeypatch.setattr(duo_service.duo_client.requests, "post", fake_post)

    is_valid, auth_result = duo_service.verify_callback(
        code="duo-code",
        state="state-1",
        expected_state="state-1",
        username="admin@example.com",
    )

    assert is_valid is True
    assert auth_result == {"sub": "duo-user-1"}
    assert captured["duo_code"] == "duo-code"
    assert captured["username"] == "admin@example.com"
    assert captured["timeout"] == 3.25
    assert duo_service.duo_client.requests.post is fake_post
