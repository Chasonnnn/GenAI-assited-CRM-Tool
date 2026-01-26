import pytest

from app.services import org_service


def test_validate_slug_allows_two_characters():
    assert org_service.validate_slug("EC") == "ec"


def test_validate_slug_rejects_one_character():
    with pytest.raises(ValueError):
        org_service.validate_slug("e")


def test_validate_slug_rejects_reserved_slug():
    with pytest.raises(ValueError):
        org_service.validate_slug("ops")


def test_validate_slug_allows_hyphen():
    assert org_service.validate_slug("ewi-global") == "ewi-global"


def test_validate_slug_rejects_underscore():
    with pytest.raises(ValueError):
        org_service.validate_slug("ewi_global")


def test_validate_slug_normalizes_lowercase():
    assert org_service.validate_slug("EWI") == "ewi"


def test_validate_slug_rejects_invalid_chars():
    with pytest.raises(ValueError):
        org_service.validate_slug("acme!")


def test_get_org_by_host_matches_slug(db, test_org, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PLATFORM_BASE_DOMAIN", "surrogacyforce.com", raising=False)
    test_org.slug = "ewi"
    db.commit()

    org = org_service.get_org_by_host(db, "ewi.surrogacyforce.com")
    assert org is not None
    assert org.id == test_org.id


def test_get_org_by_host_rejects_non_base_domain(db, test_org, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PLATFORM_BASE_DOMAIN", "surrogacyforce.com", raising=False)
    test_org.slug = "ewi"
    db.commit()

    org = org_service.get_org_by_host(db, "ewi.example.com")
    assert org is None
