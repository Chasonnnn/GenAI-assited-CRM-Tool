"""Tests for template variable builders."""

from app.services import email_service
from app.schemas.surrogate import SurrogateCreate
from app.services import surrogate_service
from app.db.enums import SurrogateSource


def test_build_surrogate_template_variables_includes_unsubscribe(db, test_org, test_user):
    surrogate = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Test User",
            email="user@example.com",
            source=SurrogateSource.MANUAL,
        ),
    )

    variables = email_service.build_surrogate_template_variables(db, surrogate)

    assert "unsubscribe_url" in variables
    assert "/email/unsubscribe/" in variables["unsubscribe_url"]
