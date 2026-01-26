"""Role permission helper sets."""

from app.db.enums.auth import Role

# Roles that can assign surrogates to other users
ROLES_CAN_ASSIGN = {Role.CASE_MANAGER, Role.ADMIN, Role.DEVELOPER}

# Roles that can archive/restore surrogates (all roles can archive their own surrogates)
ROLES_CAN_ARCHIVE = {
    Role.INTAKE_SPECIALIST,
    Role.CASE_MANAGER,
    Role.ADMIN,
    Role.DEVELOPER,
}

# Roles that can hard-delete surrogates (requires is_archived=true)
ROLES_CAN_HARD_DELETE = {Role.ADMIN, Role.DEVELOPER}

# Roles that can manage org settings
ROLES_CAN_MANAGE_SETTINGS = {Role.ADMIN, Role.DEVELOPER}

# Roles that can manage integrations (Meta, webhooks, etc.)
ROLES_CAN_MANAGE_INTEGRATIONS = {Role.DEVELOPER}

# Roles that can invite new members
ROLES_CAN_INVITE = {Role.ADMIN, Role.DEVELOPER}

# Roles that can view audit logs / diagnostics
ROLES_CAN_VIEW_AUDIT = {Role.ADMIN, Role.DEVELOPER}

# Roles that can view/manage ops alerts
ROLES_CAN_VIEW_ALERTS = {Role.ADMIN, Role.DEVELOPER}
