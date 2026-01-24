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
