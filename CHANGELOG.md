# Changelog

All notable changes to this project will be documented in this file.

## [2025-12-26] (Evening)

### Added
- **Multi-Factor Authentication (MFA)**
  - TOTP-based 2FA with QR code enrollment
  - 8 single-use recovery codes (hashed storage)
  - Duo Web SDK v4 integration
  - MFA enforcement during login flow
  - `/mfa/complete` endpoint upgrades session after verification
  - Security settings page at `/settings/security`
  
- **Calendar Tasks Integration**
  - UnifiedCalendar now displays tasks with due dates
  - Month/Week/Day views show tasks alongside appointments
  - Task filter support (My Tasks toggle)
  - Color-coded legend for appointments vs tasks
  
- **Intended Parents Date Filtering**
  - `created_after`/`created_before` API parameters
  - Frontend date range picker on IP list page

### Fixed
- **Schema Drift Issues**
  - MFA timestamps now use `DateTime(timezone=True)`
  - `tracking_token` unique index properly defined in model
  - Migration `d70f9ed6bfe6` uses `DROP INDEX IF EXISTS`
  
- **Base UI Button Warnings**
  - Standardized dropdown triggers to use native buttons
  - Replaced Button components with buttonVariants + spans
  - No more "not rendered as native button" warnings
  
- **Match Detail Page**
  - No longer fetches unfiltered tasks while loading
  - Rejection now invalidates match queries
  
- **Task Date Bucketing**
  - Uses local date parsing to avoid timezone skew
  
- **Cases Page**
  - Reset button clears date range filters
  - Shows Reset when date filter is active
  
- **Settings Page**
  - Hydrates org settings + user/org names on load
  - Removed unsupported profile phone field

### Security
- **Server-side HTML Sanitization**
  - Notes sanitized via `note_service.sanitize_html()` (uses nh3)
  - Match notes explicitly sanitized in create/accept/reject/update

### Test Coverage
- **Frontend**: 80 tests passing
- **Backend**: 241 tests passing (0 warnings)

---

## [2025-12-27] (Late Night)

### Added
- **Workflow Editor Validation**
  - Validates required fields before wizard step advancement
  - Checks trigger type, action types, email templates, task titles
  - Resets/hydrates state per edit session
  
- **Reports/Analytics Improvements**
  - Local date formatting for filters
  - Error states for funnel chart, map chart, and PDF export
  - Tooltip now renders zero values correctly
  - Campaign filter shows clearer labeling

### Fixed
- **Match Detail Improvements**
  - Notes use `updated_at` for accurate timestamp ordering
  - Files tab has "Upload File" action button
  - Add Note / Reject Match dialogs reset state on close (overlay/ESC)
  - Prevent IP task queries when ipId is missing
  - Local date parsing for DOB/due dates
  
- **Execution History**
  - Button now routes to `/automation/executions` global page
  - Pagination resets on filter changes
  
- **Email Templates**
  - DOMPurify sanitization for template/signature previews
  
- **Legacy Route Cleanup**
  - Removed `/matches/[id]` in favor of `/intended-parents/matches/[id]`
  
- **Intended Parents List**
  - Added `isError` handling with proper error UI
  
- **SQLAlchemy Test Warning**
  - Fixed "transaction already deassociated" warning in conftest.py

## [2025-12-26]

### Fixed
- **AI Bulk Tasks Permission**: Changed `require_permission("manage_tasks")` → `create_tasks`
  - `manage_tasks` didn't exist in PERMISSION_REGISTRY, causing 403 errors
  
- **Match Event Validation**: Added proper validation for all-day vs timed events
  - `all_day=True` now requires `start_date`
  - `end_date` must be >= `start_date`
  - Timed events require `starts_at`
  - `ends_at` must be >= `starts_at`
  
- **Match Event Date Filtering**: Multi-day all-day events now appear in date range queries
  - Uses overlap logic instead of start_date only
  
- **Campaign Wizard**: Restructured from 4 to 5 steps
  - Step 4: Preview Recipients (summary + RecipientPreviewCard)
  - Step 5: Schedule & Send (schedule options + confirm button)
  
- **Page Height Consistency**: Fixed IP list + Matches page scroll issues
  - Changed `min-h-screen` → `h-full overflow-hidden`
  
- **Campaign Recipient Preview**: Fixed `stage.name` → `stage.label` bug
  - PipelineStage uses `label` attribute, not `name`

### Added
- `test_match_events.py` - Event validation and range overlap tests
- `test_ai_bulk_tasks.py` - Case manager permission check tests
- Frontend templates page tests (4 new tests)

### Test Coverage
- **Frontend**: 78 tests passing
- **Backend**: 147 tests passing
- **Total**: 225 tests

---

## [2025-12-24]

### Added
- Template Marketplace with workflow templates
- Frontend template configuration modal for email action setup
- Campaign wizard improvements

### Fixed
- `send_notification` action kwargs mismatch
- Google Calendar integration field name (`provider` → `integration_type`)
- Cancelled campaigns still executing
- Campaign scheduling for "later" option
- Booking links org_id scoping
- Document upload trigger for intended-parent attachments
- `useDashboardSocket` re-render issue
