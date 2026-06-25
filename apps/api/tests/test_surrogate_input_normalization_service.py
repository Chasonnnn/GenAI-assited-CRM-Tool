from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.db.enums import SurrogateSource
from app.services import surrogate_input_normalization_service


def test_build_surrogate_create_from_mapped_payload_normalizes_shared_fields():
    surrogate, dropped = surrogate_input_normalization_service.build_surrogate_create_from_payload(
        {
            "full_name": "  Jane   Doe  ",
            "email": "JANE.DOE@EXAMPLE.COM",
            "phone": "(555) 222-3333",
            "state": "California",
            "height_ft": "5 feet 4 inches",
            "weight_lb": "Weight: 160 lbs",
            "num_deliveries": "One",
            "num_csections": "No",
            "journey_timing_preference": "Still deciding",
            "source": "Website",
        }
    )

    assert dropped == []
    assert surrogate.full_name == "Jane Doe"
    assert surrogate.email == "jane.doe@example.com"
    assert surrogate.phone == "+15552223333"
    assert surrogate.state == "CA"
    assert surrogate.height_ft == Decimal("5.33")
    assert surrogate.weight_lb == 160
    assert surrogate.num_deliveries == 1
    assert surrogate.num_csections == 0
    assert surrogate.journey_timing_preference == "still_deciding"
    assert surrogate.source == SurrogateSource.WEBSITE


def test_build_surrogate_create_lenient_drops_invalid_optional_fields():
    surrogate, dropped = surrogate_input_normalization_service.build_surrogate_create_from_payload(
        {
            "full_name": "Jane Doe",
            "email": "jane@example.com",
            "state": "Not A State",
            "height_ft": "not a height",
        },
        lenient=True,
    )

    assert surrogate.email == "jane@example.com"
    assert surrogate.state is None
    assert surrogate.height_ft is None
    assert dropped == ["height_ft", "state"]


def test_build_surrogate_create_lenient_keeps_required_identity_strict():
    with pytest.raises(ValidationError):
        surrogate_input_normalization_service.build_surrogate_create_from_payload(
            {
                "full_name": "Jane Doe",
                "email": "not-an-email",
                "state": "CA",
            },
            lenient=True,
        )
