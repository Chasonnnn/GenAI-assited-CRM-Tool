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
    CASES = "Cases"
    INTENDED_PARENTS = "Intended Parents"
    TASKS = "Tasks"
    TEAM = "Team"
    SETTINGS = "Settings"
    COMPLIANCE = "Compliance"


# =============================================================================
# Permission Registry
# =============================================================================

PERMISSION_REGISTRY: dict[str, PermissionDef] = {
    # Navigation
    "view_dashboard": PermissionDef(
        "view_dashboard", "View Dashboard", 
        "Access the main dashboard", PermissionCategory.NAVIGATION
    ),
    
    # Cases
    "view_cases": PermissionDef(
        "view_cases", "View Cases", 
        "See case list and details", PermissionCategory.CASES
    ),
    "edit_cases": PermissionDef(
        "edit_cases", "Edit Cases", 
        "Modify case information", PermissionCategory.CASES
    ),
    "delete_cases": PermissionDef(
        "delete_cases", "Delete Cases", 
        "Soft-delete cases", PermissionCategory.CASES
    ),
    "view_post_approval_cases": PermissionDef(
        "view_post_approval_cases", "View Post-Approval Cases", 
        "See Stage B (post-approval) cases", PermissionCategory.CASES
    ),
    "change_case_status": PermissionDef(
        "change_case_status", "Change Case Status", 
        "Move cases between pipeline stages", PermissionCategory.CASES
    ),
    "assign_cases": PermissionDef(
        "assign_cases", "Assign Cases", 
        "Assign cases to users or queues", PermissionCategory.CASES
    ),
    "view_case_notes": PermissionDef(
        "view_case_notes", "View Case Notes", 
        "Read case notes", PermissionCategory.CASES
    ),
    "edit_case_notes": PermissionDef(
        "edit_case_notes", "Edit Case Notes", 
        "Add and modify case notes", PermissionCategory.CASES
    ),
    
    # Intended Parents
    "view_intended_parents": PermissionDef(
        "view_intended_parents", "View Intended Parents", 
        "Access intended parents list", PermissionCategory.INTENDED_PARENTS
    ),
    "edit_intended_parents": PermissionDef(
        "edit_intended_parents", "Edit Intended Parents", 
        "Modify intended parent information", PermissionCategory.INTENDED_PARENTS
    ),
    "propose_matches": PermissionDef(
        "propose_matches", "Propose Matches", 
        "Create match proposals between surrogates and IPs", PermissionCategory.INTENDED_PARENTS
    ),
    
    # Tasks
    "view_tasks": PermissionDef(
        "view_tasks", "View Tasks", 
        "See task list", PermissionCategory.TASKS
    ),
    "create_tasks": PermissionDef(
        "create_tasks", "Create Tasks", 
        "Create new tasks", PermissionCategory.TASKS
    ),
    "edit_tasks": PermissionDef(
        "edit_tasks", "Edit Tasks", 
        "Modify task details", PermissionCategory.TASKS
    ),
    "delete_tasks": PermissionDef(
        "delete_tasks", "Delete Tasks", 
        "Delete tasks", PermissionCategory.TASKS
    ),
    
    # Team & Settings
    "manage_team": PermissionDef(
        "manage_team", "Manage Team", 
        "Invite members and change roles", PermissionCategory.TEAM
    ),
    "view_roles": PermissionDef(
        "view_roles", "View Role Permissions", 
        "View default permissions for each role", PermissionCategory.TEAM
    ),
    "manage_roles": PermissionDef(
        "manage_roles", "Manage Role Permissions", 
        "Edit default permissions per role", PermissionCategory.TEAM,
        developer_only=True
    ),
    "view_audit_log": PermissionDef(
        "view_audit_log", "View Audit Log", 
        "Access audit trail", PermissionCategory.SETTINGS
    ),
    "manage_integrations": PermissionDef(
        "manage_integrations", "Manage Integrations", 
        "Connect Gmail, Zoom, Meta", PermissionCategory.SETTINGS
    ),
    "manage_automation": PermissionDef(
        "manage_automation", "Manage Automation", 
        "Create and edit workflows", PermissionCategory.SETTINGS
    ),
    "manage_pipelines": PermissionDef(
        "manage_pipelines", "Manage Pipelines", 
        "Edit pipeline stages", PermissionCategory.SETTINGS,
        developer_only=True
    ),
    "manage_queues": PermissionDef(
        "manage_queues", "Manage Queues", 
        "Create and configure case queues", PermissionCategory.SETTINGS
    ),
    "view_reports": PermissionDef(
        "view_reports", "View Reports", 
        "Access analytics and reports", PermissionCategory.SETTINGS
    ),
    "view_ai_assistant": PermissionDef(
        "view_ai_assistant", "Use AI Assistant", 
        "Access AI chat features", PermissionCategory.SETTINGS
    ),
    
    # Compliance
    "export_data": PermissionDef(
        "export_data", "Export Data", 
        "Download data exports", PermissionCategory.COMPLIANCE
    ),
    "manage_compliance": PermissionDef(
        "manage_compliance", "Manage Compliance", 
        "Legal holds, purge requests, HIPAA exports", PermissionCategory.COMPLIANCE
    ),
    
    # New granular permissions
    "manage_meta_leads": PermissionDef(
        "manage_meta_leads", "Manage Meta Leads", 
        "Configure Meta leadgen integration and webhooks", PermissionCategory.SETTINGS
    ),
    "view_email_templates": PermissionDef(
        "view_email_templates", "View Email Templates", 
        "List and preview email templates", PermissionCategory.SETTINGS
    ),
    "manage_email_templates": PermissionDef(
        "manage_email_templates", "Manage Email Templates", 
        "Create, edit and delete email templates", PermissionCategory.SETTINGS
    ),
    "manage_ops": PermissionDef(
        "manage_ops", "Manage Operations", 
        "View alerts, queue stats, system monitoring", PermissionCategory.SETTINGS
    ),
    "manage_jobs": PermissionDef(
        "manage_jobs", "Manage Background Jobs", 
        "Trigger and view job status", PermissionCategory.SETTINGS,
        developer_only=True
    ),
    "archive_cases": PermissionDef(
        "archive_cases", "Archive Cases", 
        "Archive and restore cases", PermissionCategory.CASES
    ),
}


# =============================================================================
# Default Role Permissions
# =============================================================================

# Which permissions each role has by default (before overrides)
ROLE_DEFAULTS: dict[str, set[str]] = {
    "intake_specialist": {
        "view_dashboard",
        "view_cases",
        "edit_cases",
        "change_case_status",
        "view_case_notes",
        "edit_case_notes",
        "view_tasks",
        "create_tasks",
        "edit_tasks",
        "view_email_templates",
    },
    "case_manager": {
        "view_dashboard",
        "view_cases",
        "edit_cases",
        "view_post_approval_cases",
        "change_case_status",
        "assign_cases",
        "archive_cases",
        "view_case_notes",
        "edit_case_notes",
        "view_intended_parents",
        "edit_intended_parents",
        "propose_matches",
        "view_tasks",
        "create_tasks",
        "edit_tasks",
        "delete_tasks",
        "view_reports",
        "view_email_templates",
    },
    "manager": {
        "view_dashboard",
        "view_cases",
        "edit_cases",
        "delete_cases",
        "view_post_approval_cases",
        "change_case_status",
        "assign_cases",
        "archive_cases",
        "view_case_notes",
        "edit_case_notes",
        "view_intended_parents",
        "edit_intended_parents",
        "propose_matches",
        "view_tasks",
        "create_tasks",
        "edit_tasks",
        "delete_tasks",
        "manage_team",
        "view_roles",
        "view_audit_log",
        "manage_integrations",
        "manage_automation",
        "manage_queues",
        "view_reports",
        "view_ai_assistant",
        "export_data",
        "manage_compliance",
        "manage_meta_leads",
        "view_email_templates",
        "manage_email_templates",
        "manage_ops",
    },
    "developer": set(PERMISSION_REGISTRY.keys()),  # All permissions
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


def get_permissions_by_category() -> dict[str, list[PermissionDef]]:
    """Group permissions by category for UI."""
    result: dict[str, list[PermissionDef]] = {}
    for perm in PERMISSION_REGISTRY.values():
        if perm.category not in result:
            result[perm.category] = []
        result[perm.category].append(perm)
    return result
