"""Centralized RBAC policies for API resources."""

from dataclasses import dataclass

from app.core.permissions import PermissionKey as P


@dataclass(frozen=True)
class ResourcePolicy:
    """Default permission + per-action overrides for a resource."""

    default: P | None
    actions: dict[str, P]


POLICIES: dict[str, ResourcePolicy] = {
    "cases": ResourcePolicy(
        default=P.CASES_VIEW,
        actions={
            "edit": P.CASES_EDIT,
            "delete": P.CASES_DELETE,
            "archive": P.CASES_ARCHIVE,
            "assign": P.CASES_ASSIGN,
            "change_status": P.CASES_CHANGE_STATUS,
            "view_post_approval": P.CASES_VIEW_POST_APPROVAL,
            "notes_view": P.CASES_VIEW_NOTES,
            "notes_edit": P.CASES_EDIT_NOTES,
            "import": P.CASES_IMPORT,
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
    "meta_leads": ResourcePolicy(default=P.META_LEADS_MANAGE, actions={}),
    "org_settings": ResourcePolicy(default=P.ORG_MANAGE, actions={}),
    "forms": ResourcePolicy(default=P.FORMS_MANAGE, actions={}),
}


def get_policy(resource: str) -> ResourcePolicy:
    """Fetch a resource policy or raise KeyError."""
    return POLICIES[resource]
