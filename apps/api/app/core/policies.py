"""Centralized RBAC policies for API resources."""

from dataclasses import dataclass

from app.core.permissions import PermissionKey as P


@dataclass(frozen=True)
class ResourcePolicy:
    """Default permission + per-action overrides for a resource."""

    default: P | None
    actions: dict[str, P]


POLICIES: dict[str, ResourcePolicy] = {
    "surrogates": ResourcePolicy(
        default=P.SURROGATES_VIEW,
        actions={
            "edit": P.SURROGATES_EDIT,
            "delete": P.SURROGATES_DELETE,
            "archive": P.SURROGATES_ARCHIVE,
            "assign": P.SURROGATES_ASSIGN,
            "change_status": P.SURROGATES_CHANGE_STATUS,
            "view_post_approval": P.SURROGATES_VIEW_POST_APPROVAL,
            "notes_view": P.SURROGATES_VIEW_NOTES,
            "notes_edit": P.SURROGATES_EDIT_NOTES,
            "import": P.SURROGATES_IMPORT,
        },
    ),
    "intended_parents": ResourcePolicy(
        default=P.INTENDED_PARENTS_VIEW,
        actions={"edit": P.INTENDED_PARENTS_EDIT},
    ),
    "matches": ResourcePolicy(
        default=P.MATCHES_VIEW,
        actions={"propose": P.MATCHES_PROPOSE},
    ),
    "tasks": ResourcePolicy(
        default=P.TASKS_VIEW,
        actions={
            "create": P.TASKS_CREATE,
            "edit": P.TASKS_EDIT,
            "delete": P.TASKS_DELETE,
        },
    ),
    "appointments": ResourcePolicy(default=P.APPOINTMENTS_MANAGE, actions={}),
    "reports": ResourcePolicy(default=P.REPORTS_VIEW, actions={}),
    "pipelines": ResourcePolicy(default=P.PIPELINES_MANAGE, actions={}),
    "queues": ResourcePolicy(default=P.QUEUES_MANAGE, actions={}),
    "automation": ResourcePolicy(default=P.AUTOMATION_MANAGE, actions={}),
    "email_templates": ResourcePolicy(
        default=P.EMAIL_TEMPLATES_VIEW,
        actions={"manage": P.EMAIL_TEMPLATES_MANAGE},
    ),
    "team": ResourcePolicy(
        default=P.TEAM_MANAGE,
        actions={
            "view_roles": P.ROLES_VIEW,
            "manage_roles": P.ROLES_MANAGE,
        },
    ),
    "audit": ResourcePolicy(
        default=P.AUDIT_VIEW,
        actions={"export": P.EXPORT_DATA},
    ),
    "ops": ResourcePolicy(default=P.OPS_MANAGE, actions={}),
    "jobs": ResourcePolicy(default=P.JOBS_MANAGE, actions={}),
    "integrations": ResourcePolicy(default=P.INTEGRATIONS_MANAGE, actions={}),
    "tickets": ResourcePolicy(
        default=P.TICKETS_VIEW,
        actions={
            "edit": P.TICKETS_EDIT,
            "reply": P.TICKETS_REPLY,
            "link_surrogates": P.TICKETS_LINK_SURROGATES,
        },
    ),
    "meta_leads": ResourcePolicy(default=P.META_LEADS_MANAGE, actions={}),
    "org_settings": ResourcePolicy(default=P.ORG_MANAGE, actions={}),
    "forms": ResourcePolicy(default=P.FORMS_MANAGE, actions={}),
    "status_change_requests": ResourcePolicy(
        default=P.APPROVE_STATUS_CHANGE_REQUESTS,
        actions={
            "view_requests": P.APPROVE_STATUS_CHANGE_REQUESTS,
            "approve_requests": P.APPROVE_STATUS_CHANGE_REQUESTS,
        },
    ),
}


def get_policy(resource: str) -> ResourcePolicy:
    """Fetch a resource policy or raise KeyError."""
    return POLICIES[resource]
