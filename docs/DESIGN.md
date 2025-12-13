# Design Documentation — CRM Platform Backend

This document describes the design decisions, patterns, and features implemented in the backend API.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Authentication & Authorization](#authentication--authorization)
3. [Multi-Tenancy](#multi-tenancy)
4. [Cases Module](#cases-module)
5. [Data Normalization](#data-normalization)
6. [Soft Delete & Archiving](#soft-delete--archiving)
7. [Status History](#status-history)
8. [Notes & Tasks](#notes--tasks)
9. [Pagination & Search](#pagination--search)
10. [Meta Lead Integration](#meta-lead-integration)

---

## Architecture Overview

### Tech Stack
- **Framework**: FastAPI with Pydantic v2
- **ORM**: SQLAlchemy 2.0 with async support
- **Database**: PostgreSQL 16 with CITEXT extension
- **Migrations**: Alembic

### Project Structure
```
apps/api/app/
├── core/           # Config, security, dependencies
├── db/             # Models, enums, session
├── routers/        # API endpoints
├── schemas/        # Pydantic DTOs
├── services/       # Business logic
└── utils/          # Normalization, pagination
```

### Design Principles
1. **Routers are thin** — Business logic lives in services
2. **Schemas validate** — Pydantic handles input validation
3. **Models define truth** — SQLAlchemy models are the schema source
4. **Dependencies inject** — FastAPI Depends for auth, DB, permissions

---

## Authentication & Authorization

### Session Management
- **JWT in HTTP-only cookies** (not Authorization header)
- Cookie name: `session`
- SameSite: `Lax` (CSRF protection)
- Secure: `true` in production

### Token Structure
```python
{
    "sub": "user_uuid",
    "org": "org_uuid",
    "role": "manager",
    "ver": 1,  # Token version for revocation
    "exp": timestamp
}
```

### Key Rotation
- `JWT_SECRET` — Current signing key
- `JWT_SECRET_PREVIOUS` — Previous key (for graceful rotation)
- Tokens signed with either key are valid during rotation

### CSRF Protection
All mutations require: `X-Requested-With: XMLHttpRequest` header

### Roles (4 total)
| Role | Description |
|------|-------------|
| `intake_specialist` | Handles initial lead intake |
| `case_manager` | Manages cases through workflow |
| `manager` | Full access, can assign/archive |
| `developer` | Platform admin, elevated access |

### Permission Sets
```python
ROLES_CAN_ASSIGN = {MANAGER, DEVELOPER}
ROLES_CAN_ARCHIVE = {MANAGER, DEVELOPER}
ROLES_CAN_HARD_DELETE = {MANAGER, DEVELOPER}
ROLES_CAN_MANAGE = {MANAGER, DEVELOPER}
```

---

## Multi-Tenancy

### Model
- **Shared database, shared schema**
- Every domain table has `organization_id` column
- All queries MUST be scoped by `organization_id`

### One Org Per User
- `Membership` table has `UNIQUE(user_id)` constraint
- No org-switcher UI needed
- Tenant context derived from JWT, never from client headers

### Query Scoping
```python
# In every service function:
def list_cases(db, org_id, ...):
    return db.query(Case).filter(
        Case.organization_id == org_id
    ).all()
```

---

## Cases Module

### Terminology
- **Cases** = Surrogate applicants (renamed from "Leads")
- **Meta Leads** = Raw data from Meta Lead Ads, converted to Cases

### Case Number Generation
- Sequential per organization: `00001`, `00002`, etc.
- 5-digit zero-padded string
- Never reused (even for archived cases)
- Unique constraint: `(organization_id, case_number)`

### Case Status Flow
```
Stage A: Intake Pipeline
├── new_unread (default)
├── contacted
├── phone_screen_scheduled
├── phone_screened
├── pending_questionnaire
├── questionnaire_received
├── pending_records
├── pending_approval
├── approved ────────────┐
└── disqualified          │
                          │
Stage B: Post-Approval    │
├── pending_match ◄───────┘
├── matched
├── pre_screening
├── synced
├── pregnant
└── delivered

Pseudo-statuses (for history only):
├── archived
└── restored
```

### Source Tracking
```python
class CaseSource(str, Enum):
    MANUAL = "manual"    # Created via UI
    META = "meta"        # From Meta Lead Ads
    IMPORT = "import"    # Bulk import
```

---

## Data Normalization

### Phone Numbers (E.164)
- Input: `"(555) 123-4567"` or `"5551234567"`
- Output: `"+15551234567"`
- Validation: Exactly 10 digits (US) or 11 starting with 1
- Invalid input → `422 Unprocessable Entity`

### State Codes
- Input: `"California"` or `"CA"` or `"ca"`
- Output: `"CA"` (2-letter uppercase)
- Maps full names to codes (all 50 states + DC)
- Invalid input → `422 Unprocessable Entity`

### Email
- Lowercased and stripped
- CITEXT column for case-insensitive uniqueness

### Names
- Extra whitespace stripped
- Leading/trailing whitespace removed

---

## Soft Delete & Archiving

### Design
Cases use **soft delete** instead of hard delete:
- `is_archived` boolean flag
- `archived_at` timestamp
- `archived_by_user_id` FK

### Archive Flow
1. Set `case.status = ARCHIVED`
2. Set `is_archived = True`
3. Record timestamp and user
4. Add status history entry with prior status

### Restore Flow
1. Check email not taken by another active case
2. Retrieve prior status from archive history
3. Set `case.status = prior_status`
4. Set `is_archived = False`
5. Add status history entry

### Hard Delete
- Only allowed if `is_archived = True`
- Requires `manager+` role
- Permanently removes all data

### Email Uniqueness
- Partial unique index: `UNIQUE(organization_id, email) WHERE is_archived = FALSE`
- Archived cases don't block email reuse

---

## Status History

### Purpose
Track all status changes for audit and timeline display.

### Table: `case_status_history`
```sql
id              UUID PRIMARY KEY
case_id         UUID NOT NULL → cases.id
organization_id UUID NOT NULL → organizations.id
from_status     VARCHAR(50) NOT NULL
to_status       VARCHAR(50) NOT NULL
changed_by_user_id UUID → users.id
reason          TEXT
changed_at      TIMESTAMP DEFAULT now()
```

### When Recorded
- Any status change via `/cases/{id}/status`
- Archive operation (transition to `archived`)
- Restore operation (transition from `archived` to prior status)

---

## Notes & Tasks

### Notes (`case_notes`)
- Attached to a specific case
- Author tracking for permission checks
- Body: 2-4000 characters
- Delete: author or manager+

### Tasks (`tasks`)
- Optionally linked to a case
- Assignee (can be different from creator)
- Due date + due time (optional)
- Completion tracking (`is_completed`, `completed_at`, `completed_by`)

### Task Permissions
| Action | Who Can |
|--------|---------|
| Create | Any authenticated user |
| Update | Creator, assignee, or manager+ |
| Complete | Creator, assignee, or manager+ |
| Delete | Creator or manager+ (not assignee) |

---

## Pagination & Search

### Defaults
- Page: 1 (1-indexed)
- Per page: 20
- Max per page: **100** (capped)

### Response Format
```json
{
  "items": [...],
  "total": 150,
  "page": 1,
  "per_page": 20,
  "pages": 8
}
```

### Search (`q` parameter)
Searches across multiple fields using `ILIKE`:
- `full_name`
- `email`
- `phone`
- `case_number`

### Filters
- `status` — Filter by CaseStatus enum
- `source` — Filter by CaseSource enum
- `assigned_to` — Filter by user UUID
- `include_archived` — Include archived cases (default: false)

---

## Meta Lead Integration

### Overview
Raw leads from Meta Lead Ads → stored in `meta_leads` → converted to `cases`

### Table: `meta_leads`
- Stores raw `field_data` (JSONB)
- Stores optional `raw_payload` (JSONB)
- Tracks conversion status

### Conversion Flow
1. Webhook receives Meta event
2. Store raw data in `meta_leads`
3. Convert to normalized `Case` (separate step)
4. Mark `is_converted = True`, link `converted_case_id`

### Deduplication
- Unique constraint: `(organization_id, meta_lead_id)`
- Prevents double-processing of same Meta lead

### Field Mapping
Meta Lead Ads fields are mapped to Case fields:
- `full_name` or `name` → `full_name`
- `email` → `email`
- `phone_number` or `phone` → `phone` (normalized)
- `state` → `state` (normalized)
- Various eligibility questions → boolean fields

---

## Database Indexes

### Cases
- `idx_cases_org_status` — (org_id, status)
- `idx_cases_org_assigned` — (org_id, assigned_to)
- `idx_cases_org_created` — (org_id, created_at)
- `idx_cases_org_active` — (org_id) WHERE is_archived=FALSE

### Tasks
- `idx_tasks_org_assigned` — (org_id, assigned_to, is_completed)
- `idx_tasks_due` — (org_id, due_date) WHERE is_completed=FALSE

### Meta Leads
- `idx_meta_unconverted` — (org_id) WHERE is_converted=FALSE

---

## FK Constraints

### Deletion Behavior
| Column | ondelete |
|--------|----------|
| `organization_id` | CASCADE |
| `case_id` | CASCADE |
| `assigned_to_user_id` | SET NULL |
| `created_by_user_id` (nullable) | SET NULL |
| `created_by_user_id` (NOT NULL) | RESTRICT |
| `author_id` (NOT NULL) | RESTRICT |

**RESTRICT** prevents user deletion if they have notes/tasks.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `JWT_SECRET` | Current JWT signing key |
| `JWT_SECRET_PREVIOUS` | Previous key (rotation) |
| `JWT_EXPIRES_HOURS` | Session duration (default: 4) |
| `GOOGLE_CLIENT_ID` | OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret |
| `GOOGLE_REDIRECT_URI` | OAuth callback URL |
| `ALLOWED_EMAIL_DOMAINS` | Comma-separated domain allowlist |
| `CORS_ORIGINS` | Allowed frontend origins |
| `FRONTEND_URL` | Frontend URL for redirects |
| `DEV_SECRET` | Dev endpoint protection |
| `META_VERIFY_TOKEN` | Meta webhook verification |

---

*Last updated: 2025-12-13*
