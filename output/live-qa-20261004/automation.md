# Automation live QA

- Revision: `65bca746e` (root-provided target).
- Environment: disposable local data, frontend `http://localhost:3000`, API `http://localhost:8000`, external HTTP blocked.
- Scope: email template list/studio/drafts/history/HTML conversion, workflow list/editor/test/history, campaigns, executions, AI pages.
- Method: live browser interactions through Codex computer-use browser, DOM/screenshot evidence and browser console.
- Production source changes: none.

## Coverage log

Completed coverage follows.

## Findings

One low-severity status-filter omission (AUT-01); no blocking application defect observed in exercised automation paths.

## Limits

External sends and AI provider generation require provider access and will not be represented as verified delivery/generation. Local rejection/disabled states are testable.

## Email template browser coverage

- Personal empty state, Organization seeded list, tab labels/counts; search no-match and exact-match states.
- Organization system-template action menu; send-test dialog opens with recipient field, opt-out switch, expandable variable inputs. No send executed (approval review blocked the outbound action).
- Copy organization template to personal succeeds; resulting `QA Automation Appointment Copy` appears in list.
- Personal editor loads existing HTML, conversion dialog displays original and block previews, applying blocks preserves content and variables.
- Subject editing, draft unsaved indicator, sample/variable-name/record preview; Layla Williams synthetic record resolves; desktop/mobile/both preview render.
- HTML source tab and Copy HTML show `Copied`.
- Save converted draft succeeds (Revision 2); published version remains 1. Reloaded list shows `Draft changes`.
- History opens and displays no saved versions for the copied template. Publish confirmation warns revision is untested; cancellation works. No template publication attempted.
- Unsaved edits prompt `Leave without saving?`; discard navigates back and retains prior saved draft.
- Empty new-template Save shows name, subject, and email-body required errors.
- New `QA Automation Blocks` draft created with text, heading, divider, button, section, columns, list, quote, and HTML blocks; button link editor accepts local QA URL; image dialog rejects insecure HTTP URL (`Add image` disabled).
- Variable search filters by full_name; insert variable updates body. Rich draft saves Revision 1 and renders both desktop/mobile previews.
- Email console checkpoints: no error/warning entries.

## Workflow browser coverage

- Organization list/stat cards load; seeded workflows disabled.
- Created `QA Automation Draft Workflow`, Status Changed trigger, Contacted target stage, State condition Texas; stage and state selectors display labels.
- Created task title/description/due-days, enabled approval, added note; moved note earlier, Undo and Redo reflect order. Draft saves disabled and persists after reopening.
- List dry-run record search finds synthetic Layla Williams. Negative condition result identifies state expected TX versus actual UT.
- Edited condition to Utah without saving. Editor dry-run uses current unsaved settings; result says filters matched, one of two steps would run then wait for approval. No actions executed.
- Run again, clear test run, step history `No runs yet`, collapse/expand steps, and Save changes pass.
- Details dialog shows organization scope, creator, date. Duplicate creates disabled copy.
- Delete menu opens native confirm; cancelled, no deletion confirmed. The native modal caused a browser control recovery timeout; this remains a tool limitation.
- Screenshot: `screenshots/automation-workflow-dry-run.jpg`.
- Workflow console checkpoint: no error/warning entries.

## Explicit authorization limit

Automatic approval review rejected clicking `Send test email`: it submits an outbound email request and comprehensive QA did not specifically authorize sending. No retry or indirect send was attempted. Dialog inspection and draft/preview QA continued. Local provider guard remains enabled.

## Campaign browser coverage

- Empty list and disabled Next on blank setup.
- Email wizard: name/description, stage group selection/clear, individual Application Submitted stage, state search/Utah, template selection, review labels and one matching synthetic recipient.
- Schedule-for-later reveals date-time picker. Past date returns `Choose a time in the future.`; final scheduling stays disabled. Returned to Save as draft and saved successfully; no scheduling/send action performed.
- Draft detail: stage/state filters persist, preview finds one recipient, refresh works; Details shows organization/creator/date. Overview distinguishes zero sent recipients from one current preview match.
- Edit dialog preserves audience/template; name update persists. Empty-name submission stays in dialog (source uses toast validation; transient toast was not captured reliably).
- Duplicate preserves audience/template and stays draft. Delete confirmation displays name and irreversible warning; cancelled.
- Draft/Scheduled tabs and Personal/Organization scope filters show correct populated/empty results and readable labels.
- SMS/MMS branch displays consent restriction, hides email opt-out override; Intended Parents selection works; no promotional SMS templates blocks Next.
- Screenshot: `screenshots/automation-campaign-draft.jpg`.
- Campaign console checkpoints: no error/warning entries.

## Additional workflow coverage

- Template-library empty state; Follow-up category shows category empty state and Clear filters.
- My Workflows empty state and personal creation.
- Scheduled trigger shows daily/weekday/weekly/custom-cron choices; weekly day selector changes to Wednesday; cron input revealed.
- Before or After Appointment switches Before start to After end; appointment type choices load current synthetic types and selected QA phone chip renders.
- Egg Donor target changes graph to linked egg donors and action field choices to donor fields; stage selector uses donor pipeline.
- Email action selector includes published personal copy and organization templates but excludes unpublished QA Automation Blocks draft; recipient selector includes donor/owner/creator/admin/user/queue/role/email-address.
- Specific User with no recipient shows validation `Select at least one email recipient.` and blocks save/test.
- Update Field stage action, notification title/body, action removal/Undo tested. Removed incomplete email action and saved disabled personal `QA Automation Donor Timing`.

## AI and execution coverage

- AI Builder workflow/email tabs correctly show organization AI disabled; generation/examples/scope controls disabled.
- AI Assistant direct route displays configured-off status and disabled quick actions/input/send/new-chat.
- AI Studio direct route: disabled creation settings and generator, empty Gallery, Studio settings dialog opens/cancels without credentials or changes.
- Executions seeded Paused rows load; expand/collapse reveals Trigger Event; Failed filter gives `No executions found`; workflow filter loads names.
- Usability finding AUT-01 (low): Paused executions cannot be selected in status filter. `/automation/executions` displays Paused rows, but filter options are only All Statuses, Running, Success, Failed, Skipped, Partial. Source confirms omission at `apps/web/app/(app)/automation/executions/page.tsx:471-476`. No data loss or console error observed.

## Signature and template safeguards

- Platform templates empty state loads.
- Signature tab loads defaults, personal and organization previews. Name override shows custom/unsaved state; Clear restores profile default. Copy HTML confirms clipboard copy; no signature changes persisted.
- Saved-draft template Set inactive action refuses direct status mutation and opens `Update status in Studio` with Open draft option.
- Share with Organization and Discard draft changes dialogs show appropriate explanations and cancel correctly.
- Screenshot: `screenshots/automation-email-preview.jpg`.

## Final scope and limitations

- No production code changes, external delivery, provider generation, workflow launch/toggle, template publication, scheduled campaign submission, irreversible delete, credential entry, or permission changes.
- Rich email preview, campaign drafts, disabled workflows, and dialogs are verified against live local frontend/API. Successful external delivery and provider output remain unverified.
- Local browser control froze only the old workflow tab after native confirm cancellation; fresh tab worked immediately. Classified as tooling/environment interruption, not application defect. Native confirm reported absent afterward.
- Three personal/org workflow drafts/copy and two personal email draft/copy records, plus two campaign drafts remain only in disposable QA database for inspection.
- No console errors/warnings observed at email, workflow, campaign, AI, and final checkpoints.
