"""Owner choices for record editors."""

from uuid import UUID

from pydantic import BaseModel


class RecordUserOption(BaseModel):
    id: UUID
    display_name: str


class RecordQueueOption(BaseModel):
    id: UUID
    name: str


class RecordOwnerOptions(BaseModel):
    users: list[RecordUserOption]
    queues: list[RecordQueueOption]
