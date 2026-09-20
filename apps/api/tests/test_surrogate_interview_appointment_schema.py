"""Validation tests for the surrogate interview appointment mutation contract."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.interview_appointment import SurrogateInterviewAppointmentAction


def _payload(**overrides):
    payload = {
        "action": "reschedule",
        "scheduled_start": datetime(2027, 1, 2, 12, tzinfo=UTC),
        "move_stage": False,
        "expected_stage_id": uuid4(),
        "expected_appointment_id": uuid4(),
        "expected_scheduled_start": datetime(2027, 1, 1, 12, tzinfo=UTC),
    }
    payload.update(overrides)
    return payload


def test_schedule_and_reschedule_require_timezone_aware_start():
    with pytest.raises(ValidationError, match="must include a timezone"):
        SurrogateInterviewAppointmentAction.model_validate(
            _payload(scheduled_start=datetime(2027, 1, 2, 12))
        )


def test_cancel_rejects_a_new_start():
    with pytest.raises(ValidationError, match="not allowed when cancelling"):
        SurrogateInterviewAppointmentAction.model_validate(_payload(action="cancel"))


def test_cancel_accepts_nullable_appointment_expectations():
    action = SurrogateInterviewAppointmentAction.model_validate(
        _payload(
            action="cancel",
            scheduled_start=None,
            expected_appointment_id=None,
            expected_scheduled_start=None,
        )
    )
    assert action.action == "cancel"
