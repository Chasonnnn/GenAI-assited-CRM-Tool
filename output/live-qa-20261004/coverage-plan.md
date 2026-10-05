# Local browser QA coverage

Revision: `65bca746e` (2026-10-04). This is a source-derived plan; checkboxes do not assert execution.

## Fixtures and limits

- [ ] Disposable organization; admin, intake, case-manager, developer, and second-organization accounts.
- [ ] Synthetic surrogate, donor, intended parent, match, and task records; current and ended medical records.
- [ ] Draft/published surrogate and donor forms; multi-section form; all field types; options whose labels differ from stored values; conditional fields; file and table fields; SMS consent enabled/disabled.
- [ ] Submission queues: pending, approved, rejected, exact match, several matches, no match, failed routing, clean/quarantined upload, linked donor/surrogate.
- [ ] Phone, in-person, Google Meet, Zoom, auto-approved, and approval-required appointment types; future/past/cancelled/no-show/pending appointments.
- [ ] Synthetic Google binding, fresh/stale availability, existing event, failed/pending delivery, conflicting schedules, recurring and zero-duration events.
- [ ] Organization/personal/system email templates, HTML legacy template, block design template, stale draft, inactive template, variables, attachment, workflow executions, notifications.
- [ ] Provider calls remain synthetic or disabled. No real email/SMS/campaign invitations, Google/Zoom OAuth, billing actions, or production changes.
- [ ] Record unavailable local providers separately from application failures. Browser success alone does not verify provider delivery.

## Common checks

- [ ] Record page, dialog, action, result, screenshot, and console/network errors for each defect.
- [ ] Inspect console after navigation, mutation, opening/closing dialogs, and changing tabs. Distinguish caught API errors from uncaught exceptions and hydration warnings.
- [ ] Verify saved changes after reload; check cancellation leaves data unchanged and repeated submission does not duplicate records.
- [ ] Inspect desktop and 390px phone layouts; dialog body scroll, reachable footer, no horizontal overflow, focus return, Escape, tab order, keyboard submit.
- [ ] Exercise empty, loading, populated, denied, unavailable, and recoverable-error states where they can be simulated locally.
- [ ] Select triggers, chips, badges, summaries, tables, and defaults show labels rather than IDs/slugs/sentinels.
- [ ] Use a second organization for protected detail URLs and relationship selectors; confirm missing/denied responses do not expose records.

## Forms

- [ ] `/automation/forms`: Forms/Templates tab counts; search/case/whitespace/no results; All/Published/Drafts/Archived filters; submission counts; just-saved relative timestamp; card/menu navigation.
- [ ] Create New Form: blank required name, valid name, optional description, each lead type, cancel, successful creation.
- [ ] Existing card menu: edit, share, delete confirmation/cancel/confirm on disposable form. Template card: use template, create new form, template permissions.
- [ ] `/automation/forms/[id]` Edit: rename/autosave/manual save/reload; add/search/filter field library; page add/rename/duplicate/move/delete; field select/duplicate/remove/reorder/drag insertion.
- [ ] Field inspector: required switch, labels/options, distinct option labels/values, choice add/remove, validation limits, mapped field, conditional show/hide, table rows/columns/min/max, donor sensitivity.
- [ ] Publish readiness: missing required mappings/fields, add missing field, mark required, disabled reason; save/publish/republish and published-versus-draft behavior.
- [ ] Preview: all pages stacked in one scroll, section labels, logo/header clipping, phone/desktop width, Yes/No pairs, short choices, conditional fields, table and date controls, consent absent when disabled.
- [ ] Settings: lead type/purpose, internal/public fields, privacy notice, logo URL/upload/remove, default application template, default surrogate application, file limits and MIME types, save/reload.
- [ ] Share dialog: choose link, copy, open local link, SVG/PNG QR download, close/reopen; only published public content is visible.
- [ ] Routing: exact-match mode, ambiguous-match review, no-match intake-lead switch/source, donor photo-scan creation switch, dirty Save, reload; linked workflow list/new workflow/type defaults.
- [ ] Submissions: pending/processed/all filters, counts, expand answers, human option labels, file links/scan state/rescan, linked record navigation, approve/reject confirmation.
- [ ] Routing review: run match, search/link existing surrogate/donor, create intake lead, promote lead, dismiss review, retry failed routing; verify assigned review task can be opened by its owner.
- [ ] `/automation/form-submissions`: form selector labels, routing queue selection, empty/no permission state, exact form deep link.
- [ ] `/intake/[slug]`: all sections/section index, required validation, email/phone/date/number validation, conditional visibility, options, table rows, upload type/size/count, consent, back/edit after review, single submit, success, reload.
- [ ] `/embed/forms/[slug]`: public form loads and submits with correct dimensions; invalid/unpublished slug is safe.
- [ ] Public intake duplicate email paths: exact match, ambiguous match, no match; verify final queue/record and list submission count.

## Scheduling

- [ ] `/settings/appointments?tab=availability`: weekday toggles, start/end labels, invalid intervals, timezone, Save/cancel/reload, empty/error/retry.
- [ ] `?tab=types`: create/edit/deactivate type; blank name, duration, buffer, each meeting format, multi-format selection, required address/phone, auto-approve, cancel/reload.
- [ ] Type client messages: Request received/Confirmed/Reminder/Rescheduled/Cancelled switches; default/custom template label; disabled controls; reminder timing; save/reopen.
- [ ] Type workflows: existing links show name/status; New workflow carries appointment type and record trigger; filter does not show unrelated type workflows.
- [ ] `?tab=link`: copy booking link, preview, booking permissions, disabled/retry states.
- [ ] `/appointments`: Today/previous/next, day/week/month/list/calendar period, task and appointment events, overflow items, timezone, booking-link dialog/settings link.
- [ ] Appointment details: status, contact links, linked records edit/unlink/save/cancel, host/type/timezone/notes, provider status, approve, no-show, completed, cancel and reschedule.
- [ ] Reschedule: available slot, unavailable/empty day, retry same date, manual time with required reason, timezone conversion, stale revision, successful persistence and one provider update.
- [ ] Cancellation: blank/filled reason, cancel dialog dismissal, successful cancellation, intentional API failure displays error and preserves appointment; retry succeeds.
- [ ] Surrogate interview: create from stage transition and explicit button; preview creates no record; upcoming/manage; cancel to Reschedule Needed; keep-current-stage alternative; replacement interview.
- [ ] Intended-parent/donor/match appointment creation: host/type, record links, match/attempt fields, normal slot and manual override.
- [ ] `/book/[slug]`: type/format/date/month/time/timezone selection, Back, full name/email/phone validation, notes, duplicate click, confirmation, Add to Calendar.
- [ ] Public booking occupied/expired slot: sanitized visible error, retained contact form, choose fresh slot and retry.
- [ ] `/book/self-service/[orgId]/manage|reschedule|cancel/[token]`: permitted actions only; valid/invalid/expired token; date/timezone display; successful reschedule/cancel; old token invalid after rotation.
- [ ] `/settings/integrations` Google calendar Manage: binding selection, booking destination replacement, conflict/display toggles, dirty Save, Sync queued vs completed timestamp, disconnect confirmation/cancel.
- [ ] Synthetic Google: pending conference, failure/retry, incoming remote edit without echo, both conflict resolutions, stale availability recovery, cancel before event creation, existing event deletion, recurring busy slots and point-event import.

## Email and automation

- [ ] `/automation/email-templates`: organization/personal/library tabs, counts/search/empty state, draft chips, create/edit/duplicate/history/status/delete menus, permissions.
- [ ] `/automation/email-templates/org|personal/new|[id]`: name/subject/from settings, active switch, block insert/edit/remove/reorder, rich text and links/images, variables, undo, save/reload.
- [ ] Studio Edit/Preview/HTML: legacy HTML compatibility, HTML/block conversion, desktop/mobile preview, preview record picker/search, signature/composition, checks/missing variables/links, server preview error/retry.
- [ ] Draft controls: save/resume/discard, stale draft conflict/reload/discard, test dialog validation, publish confirmation and cancel, history/rollback. Keep delivery synthetic.
- [ ] `/automation`: org/personal tabs, create/from template, search/filter, enable/disable, duplicate/delete confirmation, row navigation, executions.
- [ ] `/automation/workflows/[id]`: name/scope/trigger/record type, action palette, insert after selection, drag into first/middle/last slot, reorder/remove, undo/redo, collapsed panels, mobile Add/Configure sheets.
- [ ] Workflow action inspector: all locally available action types, validation and dependent selectors, conditions/grouping, before/after timing, appointment type filters, save/reload.
- [ ] Workflow Test Run: search/select each supported record type, test unsaved draft, per-step outcomes, changed-since-test badge, clear/retest, unavailable record, no mutation or external delivery.
- [ ] Workflow history: executions and per-step history show correct surrogate name or other record type/ID; exact-record links work.
- [ ] `/automation/templates` and `/automation/ai-builder`: template selection and editor hydration; provider-missing/error handling; generated artifact save path only if simulated.
- [ ] `/automation/campaigns` and `[id]`: scope/status filters, create email/SMS draft, name/template/audience/recipient controls, edit, schedule, pause/cancel/delete confirmations and cancel paths; send confirmation is inspected without external send.
- [ ] `/automation/executions`: filters, pagination, details, failure display and record links.
- [ ] `/ops/templates`: form/email/system/workflow libraries, edit/publish/republish with synthetic platform admin; system email block editor and preview.

## Records and tasks

- [ ] `/surrogates`: search/filter/sort/pagination/list-board, selection/bulk assignment/stage, create validation, unassigned queue/claim, import mapping/preview/errors using synthetic CSV.
- [ ] `/surrogates/[id]`: header actions, assignment, stage transitions, contact attempt, details edit/cancel, duplicate/archive/restore confirmations where available.
- [ ] Surrogate tabs: overview, profile edit/preview/print, application/history, notes add/edit/delete, tasks add/edit/complete/delete/list-calendar, email compose/template/attachment draft, interviews/transcript/comments/version history, journey milestones/print/export, AI unavailable state.
- [ ] Medical records on surrogate/donor: add/edit each section, effective dates, imported record with missing name, long values wrap, end current record, confirm/cancel, archived history, current-only summary, reload.
- [ ] `/donors` and `[id]`: create/edit, filters/stage/assignment, eligibility, applications, notes/tasks/documents upload/remove, medical history, booking, record history.
- [ ] `/intended-parents` and `[id]`: create/edit/stage, clinic/trust fields, notes/tasks/documents, related matches, appointment and history.
- [ ] `/intended-parents/matches` and `[id]`: propose from each record, filters, accept/decline/cancel confirmations, stage/status, notes/tasks/files, appointment/attempt, related record links.
- [ ] `/tasks`: list/calendar filters/search, create/edit, due date/timezone/read-only date display, assignee/linked record, complete/reopen/delete, approval tasks, exact task query deep link.
- [ ] `/tickets` and `[ticketId]`: email/SMS tabs, search/status/priority, new ticket, assignment/status/priority, linked records, draft reply/attachments, internal notes, close/reopen, unavailable provider state.
- [ ] `/messages`: conversation selection/search, template/draft/attachment/consent state; no external send.

## Notifications, settings, reports, access

- [ ] Notification bell and `/notifications`: unread/all/filter, mark read/all, pagination, exact task/approval/appointment deep links, claim/complete/approve/deny, reason dialog/cancel/error, stale action state.
- [ ] `/settings/notifications`: each preference and daily digest setting saves/reloads without duplicate changes.
- [ ] `/settings`: profile/name/phone/photo, organization name, timezone, dirty save/cancel, signed-in user refresh without full-screen loader; email signature templates/colors/social links/logo preview/save.
- [ ] Sidebar logo: PNG/JPEG/WebP upload, phone JPEG, replacement, same file repeat, invalid type, >1MB rejection, remove confirmation/cancel; initials fallback and journey export logo.
- [ ] `/settings/pipelines`: entity switch, default-pipeline load, stage table and drawer, add/duplicate/remove/reorder, labels/slugs/colors, behavior/rules, system restrictions, used-by references, journey/funnel mapping, Save/Discard/invalid error navigation.
- [ ] Pipelines phone layout: open/back/close, focus after reorder/remove, Save error navigation, long slug truncation, milestone labels in removal dialog; version history expands correctly.
- [ ] Stage colors match across pipeline presets, badges/dots/selects/dashboard funnel/reports; light/dark contrast remains legible.
- [ ] `/settings/team`, roles, member detail: tabs/search/selection, invite dialog validation/cancel, role and module scope changes, denied routes, invitations revoke/resend simulated only.
- [ ] `/settings/queues`: create/edit/delete, membership add/remove, duplicate/blank validation, routing selectors and labels.
- [ ] `/settings/security` and `/settings/sessions`: MFA/setup state, session list/revoke confirmation; avoid revoking the active QA session before other checks.
- [ ] `/settings/integrations` and email/messaging/Meta/Zoom subroutes: load cards/settings/readiness, bounded dialogs, labels, failure/retry, configuration draft validation; synthetic disconnect paths only.
- [ ] `/settings/audit`, compliance, alerts: filters/search/range/pagination/details, denied role and no-data states, local export where supported.
- [ ] `/dashboard`: time-of-day greeting and name fallback, cards and links, stage chart, date/range controls, loading/error, updated count after local mutations.
- [ ] `/reports`: date/campaign/entity filters, charts/tables/export, no-data state, stage colors, donor section, responsive rendering.
- [ ] `/search`: each entity, blank/no-match, result links, denied records not returned.
- [ ] `/ai-assistant` and `/ai-studio`: navigation, history/artifact controls, draft UI and provider-unavailable errors; simulation boundaries recorded.
- [ ] Sidebar: all allowed links, active expansion, collapsed tooltips, phone open/close/Escape/focus return; workflow/executions links follow v2 permissions.
- [ ] Login/logout/welcome/invite/MFA, invalid record/form/booking URLs, terms/privacy/unsubscribe/consent token pages; public routes do not reveal protected records.

## Source references

- `apps/web/app/`, `apps/web/components/app-sidebar.tsx`
- `apps/web/components/forms/builder/`, `apps/web/components/appointments/`
- `apps/web/components/email/`, `apps/web/components/automation/workflow-editor/`
- `apps/web/components/pipelines/`, `apps/web/components/medical-records/`
- `apps/api/tests/support/README.md`, `apps/api/docs/scheduling-v2-qa.md`, `apps/api/docs/scheduling-ui-polish-qa.md`
- `git log a8faf1e51..65bca746e --no-merges` and prior 80 non-merge commits
