"""Centralized defaults for enums."""

from app.db.enums.email import EmailStatus
from app.db.enums.intended_parents import IntendedParentStatus
from app.db.enums.jobs import JobStatus
from app.db.enums.surrogates import SurrogateSource, SurrogateStatus
from app.db.enums.tasks import TaskType


DEFAULT_SURROGATE_STATUS: SurrogateStatus = SurrogateStatus.NEW_UNREAD
DEFAULT_SURROGATE_SOURCE: SurrogateSource = SurrogateSource.MANUAL
DEFAULT_TASK_TYPE: TaskType = TaskType.OTHER
DEFAULT_JOB_STATUS: JobStatus = JobStatus.PENDING
DEFAULT_EMAIL_STATUS: EmailStatus = EmailStatus.PENDING
DEFAULT_IP_STATUS: IntendedParentStatus = IntendedParentStatus.NEW
