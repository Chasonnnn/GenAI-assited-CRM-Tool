"""Contracts for managing a surrogate's initial interview appointment."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, model_validator


class InterviewAppointmentRead(BaseModel):
    id: UUID
    scheduled_start: datetime
    scheduled_end: datetime
    client_timezone: str
    status: str
    meeting_started_at: datetime | None
    meeting_ended_at: datetime | None


class InterviewStageRead(BaseModel):
    id: UUID
    label: str
    color: str


class SurrogateInterviewAppointmentState(BaseModel):
    appointment: InterviewAppointmentRead | None
    can_manage: bool
    external_sync_status: (
        Literal["pending", "completed", "failed", "conflict", "unlinked"] | None
    ) = None
    scheduled_stage: InterviewStageRead | None
    reschedule_stage: InterviewStageRead | None


class InterviewGoogleSyncCheck(BaseModel):
    expected_appointment_id: UUID


class SurrogateInterviewAppointmentAction(BaseModel):
    action: Literal["schedule", "reschedule", "cancel"]
    scheduled_start: datetime | None = None
    move_stage: bool
    expected_stage_id: UUID
    expected_appointment_id: UUID | None
    expected_scheduled_start: datetime | None

    @model_validator(mode="after")
    def validate_action(self):
        if self.action in {"schedule", "reschedule"}:
            if self.scheduled_start is None:
                raise ValueError("scheduled_start is required")
            if self.scheduled_start.utcoffset() is None:
                raise ValueError("scheduled_start must include a timezone")
        elif self.scheduled_start is not None:
            raise ValueError("scheduled_start is not allowed when cancelling")
        if (
            self.expected_scheduled_start is not None
            and self.expected_scheduled_start.utcoffset() is None
        ):
            raise ValueError("expected_scheduled_start must include a timezone")
        return self
