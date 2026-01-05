"""Application constants."""

import uuid

# System user UUID for workflow-created entities (tasks, etc.)
# This user represents automated system actions and is used for audit clarity.
# The actual user row is seeded via Alembic migration.
SYSTEM_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
SYSTEM_USER_EMAIL = "system@internal"
SYSTEM_USER_DISPLAY_NAME = "System"

# Workflow approval constants
WORKFLOW_APPROVAL_TIMEOUT_HOURS = 48  # Business hours
BUSINESS_HOURS_START = 8  # 8:00 AM
BUSINESS_HOURS_END = 18  # 6:00 PM (18:00)
