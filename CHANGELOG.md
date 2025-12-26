# Changelog

All notable changes to this project will be documented in this file.

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
