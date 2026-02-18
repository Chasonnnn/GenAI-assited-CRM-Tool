"""Permission registry with metadata for UI and validation.

All permissions are defined here with labels, descriptions, and categories.
Developer-only permissions cannot be granted via overrides by non-developers.

Precedence: revoke > grant > role_default
Developer role: always has all permissions (immutable)
"""

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class PermissionDef:
    """Permission definition with metadata."""

    key: str
    label: str
    description: str
    category: str
    developer_only: bool = False  # Cannot be granted by Managers


class PermissionCategory(str, Enum):
    """Permission categories for UI grouping."""

    NAVIGATION = "Navigation"
    SURROGATES = "Surrogates"
    INTENDED_PARENTS = "Intended Parents"
    TASKS = "Tasks"
    APPOINTMENTS = "Appointments"
    TEAM = "Team"
    SETTINGS = "Settings"
    AI = "AI Assistant"
    COMPLIANCE = "Compliance"


class PermissionKey(str, Enum):
    """Canonical permission keys (resource_action naming in code)."""

    VIEW_DASHBOARD = "view_dashboard"

    SURROGATES_VIEW = "view_surrogates"
    SURROGATES_EDIT = "edit_surrogates"
    SURROGATES_DELETE = "delete_surrogates"
    SURROGATES_VIEW_POST_APPROVAL = "view_post_approval_surrogates"
    SURROGATES_CHANGE_STATUS = "change_surrogate_status"
    SURROGATES_ASSIGN = "assign_surrogates"
    SURROGATES_VIEW_NOTES = "view_surrogate_notes"
    SURROGATES_EDIT_NOTES = "edit_surrogate_notes"
    SURROGATES_ARCHIVE = "archive_surrogates"
    SURROGATES_IMPORT = "import_surrogates"

    INTENDED_PARENTS_VIEW = "view_intended_parents"
    INTENDED_PARENTS_EDIT = "edit_intended_parents"
    MATCHES_PROPOSE = "propose_matches"
    MATCHES_VIEW = "view_matches"

    TASKS_VIEW = "view_tasks"
    TASKS_CREATE = "create_tasks"
    TASKS_EDIT = "edit_tasks"
    TASKS_DELETE = "delete_tasks"

    APPOINTMENTS_MANAGE = "manage_appointments"

    TEAM_MANAGE = "manage_team"
    ROLES_VIEW = "view_roles"
    ROLES_MANAGE = "manage_roles"

    AUDIT_VIEW = "view_audit_log"
    ORG_MANAGE = "manage_org"
    INTEGRATIONS_MANAGE = "manage_integrations"
    AUTOMATION_MANAGE = "manage_automation"
    PIPELINES_MANAGE = "manage_pipelines"
    QUEUES_MANAGE = "manage_queues"
    REPORTS_VIEW = "view_reports"
    AI_USE = "use_ai_assistant"
    AI_APPROVE_ACTIONS = "approve_ai_actions"
    AI_SETTINGS_MANAGE = "manage_ai_settings"
    AI_USAGE_VIEW = "view_ai_usage"
    AI_CONVERSATIONS_VIEW_ALL = "view_ai_conversations_all"

    EXPORT_DATA = "export_data"
    COMPLIANCE_MANAGE = "manage_compliance"
    COMPLIANCE_PURGE = "purge_compliance_data"

    META_LEADS_MANAGE = "manage_meta_leads"
    EMAIL_TEMPLATES_VIEW = "view_email_templates"
    EMAIL_TEMPLATES_MANAGE = "manage_email_templates"
    OPS_MANAGE = "manage_ops"
    JOBS_MANAGE = "manage_jobs"
    FORMS_MANAGE = "manage_forms"
    ADMIN_EXPORTS_MANAGE = "manage_admin_exports"
    ADMIN_IMPORTS_MANAGE = "manage_admin_imports"
    ADMIN_VERSIONS_MANAGE = "manage_admin_versions"
    APPROVE_STATUS_CHANGE_REQUESTS = "approve_status_change_requests"


# =============================================================================
# Permission Registry
# =============================================================================

PERMISSION_REGISTRY: dict[str, PermissionDef] = {
    # Navigation
    "view_dashboard": PermissionDef(
        "view_dashboard",
        "View Dashboard",
        "Access the main dashboard",
        PermissionCategory.NAVIGATION,
    ),
    # Surrogates
    "view_surrogates": PermissionDef(
        "view_surrogates",
        "View Surrogates",
        "See surrogate list and details",
        PermissionCategory.SURROGATES,
    ),
    "edit_surrogates": PermissionDef(
        "edit_surrogates",
        "Edit Surrogates",
        "Modify surrogate information",
        PermissionCategory.SURROGATES,
    ),
    "delete_surrogates": PermissionDef(
        "delete_surrogates",
        "Delete Surrogates",
        "Soft-delete surrogates",
        PermissionCategory.SURROGATES,
    ),
    "view_post_approval_surrogates": PermissionDef(
        "view_post_approval_surrogates",
        "View Post-Approval Surrogates",
        "See Stage B (post-approval) surrogates",
        PermissionCategory.SURROGATES,
    ),
    "change_surrogate_status": PermissionDef(
        "change_surrogate_status",
        "Change Surrogate Status",
        "Move surrogates between pipeline stages",
        PermissionCategory.SURROGATES,
    ),
    "assign_surrogates": PermissionDef(
        "assign_surrogates",
        "Assign Surrogates",
        "Assign surrogates to users or queues",
        PermissionCategory.SURROGATES,
    ),
    "view_surrogate_notes": PermissionDef(
        "view_surrogate_notes",
        "View Surrogate Notes",
        "Read surrogate notes",
        PermissionCategory.SURROGATES,
    ),
    "edit_surrogate_notes": PermissionDef(
        "edit_surrogate_notes",
        "Edit Surrogate Notes",
        "Add and modify surrogate notes",
        PermissionCategory.SURROGATES,
    ),
    "import_surrogates": PermissionDef(
        "import_surrogates",
        "Import Surrogates",
        "Import surrogates via CSV",
        PermissionCategory.SURROGATES,
    ),
    # Intended Parents
    "view_intended_parents": PermissionDef(
        "view_intended_parents",
        "View Intended Parents",
        "Access intended parents list",
        PermissionCategory.INTENDED_PARENTS,
    ),
    "edit_intended_parents": PermissionDef(
        "edit_intended_parents",
        "Edit Intended Parents",
        "Modify intended parent information",
        PermissionCategory.INTENDED_PARENTS,
    ),
    "propose_matches": PermissionDef(
        "propose_matches",
        "Propose Matches",
        "Create match proposals between surrogates and IPs",
        PermissionCategory.INTENDED_PARENTS,
    ),
    "view_matches": PermissionDef(
        "view_matches",
        "View Matches",
        "Access match list and details",
        PermissionCategory.INTENDED_PARENTS,
    ),
    # Tasks
    "view_tasks": PermissionDef(
        "view_tasks", "View Tasks", "See task list", PermissionCategory.TASKS
    ),
    "create_tasks": PermissionDef(
        "create_tasks", "Create Tasks", "Create new tasks", PermissionCategory.TASKS
    ),
    "edit_tasks": PermissionDef(
        "edit_tasks", "Edit Tasks", "Modify task details", PermissionCategory.TASKS
    ),
    "delete_tasks": PermissionDef(
        "delete_tasks", "Delete Tasks", "Delete tasks", PermissionCategory.TASKS
    ),
    # Appointments
    "manage_appointments": PermissionDef(
        "manage_appointments",
        "Manage Appointments",
        "Configure appointment types, availability, and bookings",
        PermissionCategory.APPOINTMENTS,
    ),
    # Team & Settings
    "manage_team": PermissionDef(
        "manage_team",
        "Manage Team",
        "Invite members and change roles",
        PermissionCategory.TEAM,
    ),
    "view_roles": PermissionDef(
        "view_roles",
        "View Role Permissions",
        "View default permissions for each role",
        PermissionCategory.TEAM,
    ),
    "manage_roles": PermissionDef(
        "manage_roles",
        "Manage Role Permissions",
        "Edit default permissions per role",
        PermissionCategory.TEAM,
        developer_only=True,
    ),
    "view_audit_log": PermissionDef(
        "view_audit_log",
        "View Audit Log",
        "Access audit trail",
        PermissionCategory.SETTINGS,
    ),
    "manage_org": PermissionDef(
        "manage_org",
        "Manage Organization",
        "Update organization profile settings",
        PermissionCategory.SETTINGS,
    ),
    "manage_integrations": PermissionDef(
        "manage_integrations",
        "Manage Integrations",
        "Connect Gmail, Zoom, Meta",
        PermissionCategory.SETTINGS,
    ),
    "manage_automation": PermissionDef(
        "manage_automation",
        "Manage Automation",
        "Create and edit workflows",
        PermissionCategory.SETTINGS,
    ),
    "manage_pipelines": PermissionDef(
        "manage_pipelines",
        "Manage Pipelines",
        "Edit pipeline stages",
        PermissionCategory.SETTINGS,
    ),
    "manage_queues": PermissionDef(
        "manage_queues",
        "Manage Queues",
        "Create and configure case queues",
        PermissionCategory.SETTINGS,
    ),
    "manage_forms": PermissionDef(
        "manage_forms",
        "Manage Forms",
        "Create and publish application forms",
        PermissionCategory.SETTINGS,
    ),
    "view_reports": PermissionDef(
        "view_reports",
        "View Reports",
        "Access analytics and reports",
        PermissionCategory.SETTINGS,
    ),
    "use_ai_assistant": PermissionDef(
        "use_ai_assistant",
        "Use AI Assistant",
        "Chat with AI and view suggestions",
        PermissionCategory.AI,
    ),
    "approve_ai_actions": PermissionDef(
        "approve_ai_actions",
        "Approve AI Actions",
        "Execute AI-proposed actions (send email, create task, etc.)",
        PermissionCategory.AI,
    ),
    "manage_ai_settings": PermissionDef(
        "manage_ai_settings",
        "Manage AI Settings",
        "Enable AI and configure providers/models",
        PermissionCategory.AI,
    ),
    "view_ai_usage": PermissionDef(
        "view_ai_usage",
        "View AI Usage",
        "Access AI usage analytics and summaries",
        PermissionCategory.AI,
    ),
    "view_ai_conversations_all": PermissionDef(
        "view_ai_conversations_all",
        "View All AI Conversations",
        "Audit AI conversations across users",
        PermissionCategory.AI,
        developer_only=True,
    ),
    # Compliance
    "export_data": PermissionDef(
        "export_data",
        "Export Data",
        "Download data exports",
        PermissionCategory.COMPLIANCE,
    ),
    "manage_compliance": PermissionDef(
        "manage_compliance",
        "Manage Compliance",
        "Legal holds, purge requests, HIPAA exports",
        PermissionCategory.COMPLIANCE,
    ),
    "purge_compliance_data": PermissionDef(
        "purge_compliance_data",
        "Purge Compliance Data",
        "Execute retention-based data purges",
        PermissionCategory.COMPLIANCE,
        developer_only=True,
    ),
    # New granular permissions
    "manage_meta_leads": PermissionDef(
        "manage_meta_leads",
        "Manage Meta Leads",
        "Configure Meta leadgen integration and webhooks",
        PermissionCategory.SETTINGS,
    ),
    "view_email_templates": PermissionDef(
        "view_email_templates",
        "View Email Templates",
        "List and preview email templates",
        PermissionCategory.SETTINGS,
    ),
    "manage_email_templates": PermissionDef(
        "manage_email_templates",
        "Manage Email Templates",
        "Create, edit and delete email templates",
        PermissionCategory.SETTINGS,
    ),
    "manage_ops": PermissionDef(
        "manage_ops",
        "Manage Operations",
        "View alerts, queue stats, system monitoring",
        PermissionCategory.SETTINGS,
    ),
    "manage_jobs": PermissionDef(
        "manage_jobs",
        "Manage Background Jobs",
        "Trigger and view job status",
        PermissionCategory.SETTINGS,
        developer_only=True,
    ),
    "manage_admin_exports": PermissionDef(
        "manage_admin_exports",
        "Manage Admin Exports",
        "Generate developer-only data exports",
        PermissionCategory.SETTINGS,
        developer_only=True,
    ),
    "manage_admin_imports": PermissionDef(
        "manage_admin_imports",
        "Manage Admin Imports",
        "Restore org data from admin imports",
        PermissionCategory.SETTINGS,
        developer_only=True,
    ),
    "manage_admin_versions": PermissionDef(
        "manage_admin_versions",
        "Manage Admin Versions",
        "View and roll back versioned configs",
        PermissionCategory.SETTINGS,
        developer_only=True,
    ),
    "archive_surrogates": PermissionDef(
        "archive_surrogates",
        "Archive Surrogates",
        "Archive and restore surrogates",
        PermissionCategory.SURROGATES,
    ),
    "approve_status_change_requests": PermissionDef(
        "approve_status_change_requests",
        "Approve Status Change Requests",
        "Approve or reject stage/status regression requests",
        PermissionCategory.SURROGATES,
    ),
}


# =============================================================================
# Default Role Permissions
# =============================================================================

# Which permissions each role has by default (before overrides)
ROLE_DEFAULTS: dict[str, set[str]] = {
    "intake_specialist": {
        "view_dashboard",
        "view_surrogates",
        "edit_surrogates",
        "view_post_approval_surrogates",  # Allow following surrogates at all stages
        "change_surrogate_status",
        "view_surrogate_notes",
        "edit_surrogate_notes",
        "import_surrogates",
        "view_tasks",
        "create_tasks",
        "edit_tasks",
        "view_email_templates",
        "use_ai_assistant",
        "approve_ai_actions",
        "manage_ai_settings",
        "view_ai_usage",
    },
    "case_manager": {
        "view_dashboard",
        "view_surrogates",
        "edit_surrogates",
        "view_post_approval_surrogates",
        "change_surrogate_status",
        "assign_surrogates",
        "archive_surrogates",
        "view_surrogate_notes",
        "edit_surrogate_notes",
        "import_surrogates",
        "view_intended_parents",
        "edit_intended_parents",
        "propose_matches",
        "view_matches",
        "view_tasks",
        "create_tasks",
        "edit_tasks",
        "delete_tasks",
        "view_reports",
        "view_email_templates",
        "manage_appointments",
        "use_ai_assistant",
        "approve_ai_actions",
        "manage_ai_settings",
        "view_ai_usage",
    },
    "admin": {
        "view_dashboard",
        "view_surrogates",
        "edit_surrogates",
        "delete_surrogates",
        "view_post_approval_surrogates",
        "change_surrogate_status",
        "assign_surrogates",
        "archive_surrogates",
        "view_surrogate_notes",
        "edit_surrogate_notes",
        "import_surrogates",
        "approve_status_change_requests",
        "view_intended_parents",
        "edit_intended_parents",
        "propose_matches",
        "view_matches",
        "view_tasks",
        "create_tasks",
        "edit_tasks",
        "delete_tasks",
        "manage_team",
        "view_roles",
        "view_audit_log",
        "manage_org",
        "manage_integrations",
        "manage_automation",
        "manage_queues",
        "manage_forms",
        "view_reports",
        "use_ai_assistant",
        "approve_ai_actions",
        "manage_ai_settings",
        "view_ai_usage",
        "export_data",
        "manage_compliance",
        "manage_meta_leads",
        "view_email_templates",
        "manage_email_templates",
        "manage_ops",
        "manage_pipelines",
        "manage_appointments",
    },
    "developer": set(PERMISSION_REGISTRY.keys()),  # All permissions
}


# =============================================================================
# Permission Bundles
# =============================================================================

# Bundles map UI toggles or policy shortcuts to sets of permissions.
PERMISSION_BUNDLES: dict[str, set[str]] = {
    "surrogates_manage": {
        "view_surrogates",
        "edit_surrogates",
        "change_surrogate_status",
        "assign_surrogates",
        "archive_surrogates",
        "view_surrogate_notes",
        "edit_surrogate_notes",
        "import_surrogates",
    },
    "tasks_manage": {
        "view_tasks",
        "create_tasks",
        "edit_tasks",
        "delete_tasks",
    },
    "intended_parents_manage": {
        "view_intended_parents",
        "edit_intended_parents",
        "view_matches",
        "propose_matches",
    },
    "email_templates_manage": {
        "view_email_templates",
        "manage_email_templates",
    },
    "team_manage": {
        "manage_team",
        "view_roles",
    },
}


# =============================================================================
# Helper Functions
# =============================================================================


def get_all_permissions() -> list[PermissionDef]:
    """Get all permissions sorted by category."""
    return sorted(PERMISSION_REGISTRY.values(), key=lambda p: (p.category, p.key))


def get_permission(key: str) -> PermissionDef | None:
    """Get permission by key."""
    return PERMISSION_REGISTRY.get(key)


def is_valid_permission(key: str) -> bool:
    """Check if permission key exists."""
    return key in PERMISSION_REGISTRY


def is_developer_only(key: str) -> bool:
    """Check if permission can only be modified by developers."""
    perm = PERMISSION_REGISTRY.get(key)
    return perm.developer_only if perm else False


def get_role_default_permissions(role: str) -> set[str]:
    """Get default permissions for a role."""
    return ROLE_DEFAULTS.get(role, set())


def get_permission_bundle(bundle_key: str) -> set[str]:
    """Get permissions for a named bundle."""
    return PERMISSION_BUNDLES.get(bundle_key, set())


def get_permissions_by_category() -> dict[str, list[PermissionDef]]:
    """Group permissions by category for UI."""
    result: dict[str, list[PermissionDef]] = {}
    for perm in PERMISSION_REGISTRY.values():
        if perm.category not in result:
            result[perm.category] = []
        result[perm.category].append(perm)
    return result
