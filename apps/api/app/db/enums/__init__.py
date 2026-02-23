"""Enum definitions for application constants."""

from app.db.enums.appointments import (
    AppointmentEmailType,
    AppointmentStatus,
    DEFAULT_APPOINTMENT_STATUS,
    MeetingMode,
)
from app.db.enums.audit import AuditEventType
from app.db.enums.auth import AuthProvider, Role
from app.db.enums.campaigns import CampaignRecipientStatus, CampaignStatus
from app.db.enums.defaults import (
    DEFAULT_EMAIL_STATUS,
    DEFAULT_IP_STATUS,
    DEFAULT_JOB_STATUS,
    DEFAULT_SURROGATE_SOURCE,
    DEFAULT_SURROGATE_STATUS,
    DEFAULT_TASK_TYPE,
)
from app.db.enums.email import EmailStatus, SuppressionReason
from app.db.enums.entities import EntityType
from app.db.enums.forms import (
    FormPurpose,
    FormStatus,
    FormSubmissionStatus,
    FormLinkMode,
    FormSubmissionMatchStatus,
    IntakeLeadStatus,
)
from app.db.enums.integration_health import (
    AlertSeverity,
    AlertStatus,
    AlertType,
    ConfigStatus,
    IntegrationStatus,
    IntegrationType,
)
from app.db.enums.intended_parents import IntendedParentStatus
from app.db.enums.jobs import JobStatus, JobType
from app.db.enums.matches import MatchEventPerson, MatchEventType, MatchStatus
from app.db.enums.notifications import NotificationType
from app.db.enums.permissions import (
    ROLES_CAN_ARCHIVE,
    ROLES_CAN_ASSIGN,
    ROLES_CAN_HARD_DELETE,
    ROLES_CAN_INVITE,
    ROLES_CAN_MANAGE_INTEGRATIONS,
    ROLES_CAN_MANAGE_SETTINGS,
    ROLES_CAN_VIEW_ALERTS,
    ROLES_CAN_VIEW_AUDIT,
)
from app.db.enums.surrogates import (
    ContactMethod,
    ContactOutcome,
    ContactStatus,
    OwnerType,
    SurrogateActivityType,
    SurrogateSource,
    SurrogateStatus,
)
from app.db.enums.tasks import TaskStatus, TaskType
from app.db.enums.ticketing import (
    EmailDirection,
    EmailOccurrenceState,
    LinkConfidence,
    MailboxKind,
    MailboxProvider,
    RecipientSource,
    SurrogateEmailContactSource,
    TicketLinkStatus,
    TicketPriority,
    TicketStatus,
)
from app.db.enums.workflows import (
    RecurrenceMode,
    WorkflowActionType,
    WorkflowConditionOperator,
    WorkflowEventSource,
    WorkflowExecutionStatus,
    WorkflowTriggerType,
)

__all__ = [
    "AlertSeverity",
    "AlertStatus",
    "AlertType",
    "AppointmentEmailType",
    "AppointmentStatus",
    "AuditEventType",
    "AuthProvider",
    "CampaignRecipientStatus",
    "CampaignStatus",
    "ConfigStatus",
    "ContactMethod",
    "ContactOutcome",
    "ContactStatus",
    "DEFAULT_APPOINTMENT_STATUS",
    "DEFAULT_EMAIL_STATUS",
    "DEFAULT_IP_STATUS",
    "DEFAULT_JOB_STATUS",
    "DEFAULT_SURROGATE_SOURCE",
    "DEFAULT_SURROGATE_STATUS",
    "DEFAULT_TASK_TYPE",
    "EmailStatus",
    "EntityType",
    "EmailDirection",
    "EmailOccurrenceState",
    "FormPurpose",
    "FormStatus",
    "FormSubmissionStatus",
    "FormLinkMode",
    "FormSubmissionMatchStatus",
    "IntakeLeadStatus",
    "IntegrationStatus",
    "IntegrationType",
    "IntendedParentStatus",
    "JobStatus",
    "JobType",
    "MatchEventPerson",
    "MatchEventType",
    "MatchStatus",
    "MeetingMode",
    "LinkConfidence",
    "MailboxKind",
    "MailboxProvider",
    "NotificationType",
    "OwnerType",
    "RecipientSource",
    "RecurrenceMode",
    "Role",
    "ROLES_CAN_ARCHIVE",
    "ROLES_CAN_ASSIGN",
    "ROLES_CAN_HARD_DELETE",
    "ROLES_CAN_INVITE",
    "ROLES_CAN_MANAGE_INTEGRATIONS",
    "ROLES_CAN_MANAGE_SETTINGS",
    "ROLES_CAN_VIEW_ALERTS",
    "ROLES_CAN_VIEW_AUDIT",
    "SuppressionReason",
    "SurrogateActivityType",
    "SurrogateSource",
    "SurrogateEmailContactSource",
    "SurrogateStatus",
    "TaskStatus",
    "TaskType",
    "TicketLinkStatus",
    "TicketPriority",
    "TicketStatus",
    "WorkflowActionType",
    "WorkflowConditionOperator",
    "WorkflowEventSource",
    "WorkflowExecutionStatus",
    "WorkflowTriggerType",
]
