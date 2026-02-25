from app.services import activity_service


def test_redact_changes_preserves_height_and_weight():
    changes = {
        "height_ft": 5.5,
        "weight_lb": 140,
        "email": "test@example.com",
    }

    result = activity_service._redact_changes(changes)

    assert result["height_ft"] == 5.5
    assert result["weight_lb"] == 140
    assert result["email"] == activity_service.REDACTED_VALUE
