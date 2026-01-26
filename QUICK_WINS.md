# Quick Wins Checklist (each < 1 day)

- [x] Extract `apply_surrogate_status_change` into `apps/api/app/services/surrogate_status_service.py` and update `apps/api/app/services/status_change_request_service.py` to stop calling the private helper in `apps/api/app/services/surrogate_service.py`.
- [x] Move direct model reads from `apps/api/app/routers/journey.py` into `apps/api/app/services/journey_service.py` (add small service methods, keep router thin).
- [x] Remove direct `FormSubmission` access from `apps/api/app/routers/profile.py` by adding `profile_service.get_latest_submission_id()` in `apps/api/app/services/profile_service.py`.
- [x] Introduce `apps/api/app/services/dashboard_events.py` and call it from `apps/api/app/services/surrogate_service.py` and `apps/api/app/services/task_service.py` instead of pushing dashboard stats in routers.
- [x] Create `apps/web/lib/hooks/use-unified-calendar-data.ts` and refactor `apps/web/components/appointments/UnifiedCalendar.tsx` to render data only.
- [x] Extract due‑category helpers from `apps/web/app/(app)/tasks/page.tsx` into `apps/web/lib/utils/task-due.ts` to shrink the page file.
- [x] Split `apps/web/app/(app)/surrogates/[id]/page.tsx` into tab components under `apps/web/components/surrogates/tabs/` (Notes + Tasks tabs).
- [x] Add `apps/api/app/services/task_events.py` with a `task_assigned` helper; update `apps/api/app/services/task_service.py` to call it instead of formatting notifications inline.
