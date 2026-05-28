from app.services import activity_service


def test_redact_changes_uses_action_summaries_for_sensitive_fields():
    changes = {
        "height_ft": 5.5,
        "weight_lb": 140,
        "email": "test@example.com",
        "ssn": "123-45-6789",
        "partner_date_of_birth": None,
        "phone": "",
    }

    result = activity_service._redact_changes(changes)

    assert result["height_ft"] == 5.5
    assert result["weight_lb"] == 140
    assert result["email"] == {"action": "updated"}
    assert result["ssn"] == {"action": "updated"}
    assert result["partner_date_of_birth"] == {"action": "cleared"}
    assert result["phone"] == {"action": "cleared"}
