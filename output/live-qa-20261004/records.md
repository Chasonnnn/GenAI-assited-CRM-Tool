# Records browser QA

Revision `65bca746e`; Chrome dedicated tab, shared synthetic admin, disposable local database, provider guard. Browser actions only for mutations. Lane completed with explicit coverage gaps below.

## Confirmed finding

- **R1 — donor education accepted by form renders Unknown in detail (P2).** Create Sperm Donor or open Edit Donor; Education is free-text, placeholder `Highest level, degree, or field of study`. Enter `QA Bachelor Degree`, Save Changes. Overview Education and Eligibility Education level both render `Unknown`; inline Education selector also renders `Unknown`. Reload and reopen Edit: stored free text remains. Donor table displays the stored text correctly. Reproduced on donor `cca9d2b9-5656-43ec-913c-573f66e822f6` / D10004. Screenshot `donor-education-unknown.jpg`. No app console error accompanied the mismatch.

## Executed checks

- Surrogates populated list 81 records and pagination controls rendered. Create blank: name/email validation. Invalid `.test` email rejected; example.com accepted. Created `QA Records Surrogate` / S10084 / `cda48d9d-6c6f-4558-a06b-805a979553db`; claim succeeded.
- Medical sections created successfully: Insurance, PCP Provider, Lab Clinic, IVF Clinic, Monitoring Clinic, OB Provider, Delivery Hospital. Empty insurance name rejected. PCP `New York` normalized to `NY`.
- Insurance saved, reload preserved data. Identity change prompt cancel preserved original; correction saved; correction history showed actor, old value, new value. New record copy selector displayed human names and copied details. Current/replacement/past records retained.
- Native date keyboard change to Oct 5 produced Scheduled record, current preserved; history selector and Back to current worked. **Tool limitation:** CUA `.fill` on native date changes DOM value but not React state. Earlier date probes saved Oct 4, confirmed by environment agent. Native click + ArrowRight + ArrowUp worked. Those probe records are disposable test data, not a product defect.
- Medical archive cancel, archive current record, archived-section expansion, reload, Restore PCP Provider passed. Future insurance record remains scheduled when current is archived; no data loss observed.
- Seeded imported insurance missing company rendered plan/member and Imported/Date unknown. Filling missing company saved as correction and survived reload.
- Seeded PCP current/past/future history displayed correct date ranges and labels; past warning and Back to current worked.
- Donor Egg/Sperm tabs scoped lists. New Sperm Donor blank validation passed; created D10004 with phone normalization to +12125550133.
- Donor Edit saved and persisted (R1 display issue). Change Stage New→Contacted succeeded. Note creation persisted and note-delete cancel preserved it. Record task creation/complete passed; calendar rendered; Applications empty state; History contained stage, note, task-created/completed and edit entries.
- Donor archive removed from active list. More Filters→Archived Donors showed record; reopened archive read-only; Notes remained readable. Restore re-enabled controls.
- Egg donor imported PCP with missing provider/name retained phone/city/state and Imported/Date unknown. Filled provider, reload preserved; archive/history/restore passed, restore created current record while retaining imported history.

## Console

- No error/warning observed through surrogate medical lifecycle.
- Later donor pass had `[WS] Handshake rejected - notifications will use polling fallback` at 2026-10-04T20:05:22.825Z; app remained functional. Root informed for environment correlation.

## Coverage status

- Additional executed coverage and remaining gaps are recorded below; successful uploads/import are not claimed.

## Extended executed coverage

### Intended parents

- New Intended Parent blank required validation passed. Created `QA Records Parent` / I10014 / `109fc99a-1466-42b5-8045-06a0f2ddd34a` with partner name/email; list and detail displayed partner values.
- Trust provider inline edit saved `QA Trust Provider`. Funding selector options were human labels; saved `Funded`. Added Medical Information→IVF Clinic section and inline name `QA Parent IVF Clinic`.
- Change Stage New→Ready to Match succeeded. Reload preserved stage, trust provider, funding status and IVF clinic.
- Propose Match dialog surrogate branch showed clear no-ready-surrogate state. Donor branch exposed Match Kind, Donor Type, and donor selector; not submitted from this branch.

### Matches

- Moved own surrogate S10084 to Ready to Match. Propose Match from surrogate showed intended-parent picker with human name/number, selected own I10014, created match M10021 / `459b7ff5-a0cd-4c6a-97b0-8580ec432f11`.
- Matches list showed proposal Under Review. Detail linked correct surrogate/IP, displayed current stages, notes/files/tasks/activity tabs, All Sources filter.
- Accept Match confirmation listed both stage transitions and competing-match behavior. Cancel left Under Review; confirm changed match Accepted and both surrogate/IP Matched.
- Added `QA match note` and `QA Match Task`. Activity rendered note/task/proposal/acceptance plus source labels. Files empty state and upload control rendered. Calendar rendered Month, previous/next, Today, source filters and Add Task.
- Cancel Match required reason; empty reason left Request Cancellation disabled. Submitted `QA cancellation lifecycle`; result Cancellation Pending and requester Withdraw Cancellation control. Pending state removed Add Task.
- Environment agent independently approved with second synthetic primary-org admin `QA Review Admin`, through Tasks→Pending Approvals. Reported match Cancelled and both records Ready to Match; screenshot `roles-match-cancellation-approved.jpg` belongs to that lane. This lane then observed surrogate Ready to Match in refreshed list and stage-change note attributed QA Review Admin. No requester self-approval used.

### Surrogate notes, tasks, interviews, applications, journey

- Added surrogate note `QA surrogate note with local evidence`; note appeared alongside automatic match stage notes. Global-search lane independently found this note and correct surrogate link.
- Created `QA Surrogate Follow Up` task. Tasks count became2 (including QA Match Task); list and Calendar rendered.
- Created completed Phone interview at current date/time, duration30, synthetic transcript. Added general note. Edit transcript saved Version2; Version History showed v2 Current and v1, Manual Edit, Test Admin and timestamps. Interview transcript contents rendered.
- Application tab showed No Application Submitted, configured published default form, Advanced override and Send Form Link. Did not send externally. Profile tab showed No application submitted and Open Application.
- Journey rendered all milestone cards, completed dates for prior milestones, Set Image controls. Export menu showed Internal Use (Full) and Client Share (Redacted) choices. Match Confirmed image dialog showed default image and no uploaded images; Cancel returned safely. Print/export output itself not executed.
- AI tab showed AI turned off for organization and AI settings link.
- Full surrogate Edit dialog changed phone twice; saved phone visible in list. This reproducibly generated R2 below.

### Surrogate list controls

- Search `QA Records` returned own surrogate only and Search chip. Filter Ready to Match produced human-readable trigger and chip. Reset removed active filters.
- Selected own surrogate; bulk toolbar showed Assign to, Change stage, Archive, Clear. Bulk Change stage dialog opened with target selector, Cancel returned without mutation; Clear deselected.
- Intelligent Suggestions button applied filter/chip and returned31 records with pagination. Clicked Next but navigated away before verifying final second-page row, so second-page result is not claimed.
- Import, list sorting/board/export and further bulk flows delegated to automation QA lane.

## Additional confirmed finding

- **R2 — surrogate full Edit save logs Base UI uncontrolled-field error (P3).** Detail→More actions→Edit→change Phone→Save Changes. Saved phone persists, but console logs `Base UI: A component is changing the default value state of an uncontrolled FieldControl after being initialized. To suppress this warning opt to use a controlled FieldControl.` Reproduced twice on S10084 at `2026-10-04T20:21:54.611Z` and `2026-10-04T20:23:32.243Z`. No visible crash or failed save. Source has phone `defaultValue={surrogate.phone ?? ""}` at `apps/web/components/surrogates/detail/SurrogateDetailLayout/dialogs/EditDialog.tsx:304`; adjacent full-name/email/state/date/weight inputs use same pattern. This is a source pointer, not proof of exact internal cause.

## Source pointers for R1

- `apps/web/components/donors/DonorFormFields.tsx:126` — Education label and free-text Input.
- `apps/web/components/donors/DonorOverviewTab.tsx:449` — Education uses InlineSelectField when profile options exist.
- `apps/web/components/donors/DonorEligibilityChecklist.tsx:60` — same education options branch in eligibility.

## Limits and remaining gaps

- Attachment upload was attempted through supported browser file chooser with generated synthetic PDF `/private/tmp/qa-records-attachment-20261004.pdf`. The tool stalled about11minutes and was interrupted; no completed upload or attachment persistence is claimed. Root reports native Mac picker unavailable/locked. No further chooser attempts.
- No provider messages, form-link sends, AI generation, OAuth or production actions. No donor/IP documents, interview media/transcription, file search, import execution or successful downloads verified in this lane.
- Donor eligibility multi-choice and donor assignment not fully mutated. Surrogate demographics/personal-info edits, queue release/claim by another role, archive/restore and print not completed here. The approved profile follow-up is recorded below. Other lanes cover roles and import/bulk.
- No production code changed. Artifacts only; root owns commit and service cleanup.

## Approved application and profile follow-up

- Read approved fixture `QA Form Approved` / S10088 / `ea2de73d-5e0d-49e0-a478-a9bb4338067e`. Application tab displayed Approved, submission time, mapped identity, fixed table with three row labels/No/Synthetic QA, repeating table with two columns and QA row values, Uploaded Files(0).
- **R3 — profile card renders table answers as object strings (P2).** Open Profile on same approved record: `Table` displays `[object Object], [object Object], [object Object]`; `Repeating Table` displays `[object Object]`. Application tab renders these data correctly. Reload preserved the defect. Screenshot `profile-table-object-values.jpg`.
- Profile Edit→Edit Table exposes a plain text input whose value is `[object Object],[object Object],[object Object]`. Cancel field and Cancel profile returned to view; nothing saved. Structured-table editing therefore also lacks a meaningful control, but corruption after saving was not tested.
- Source `apps/web/components/surrogates/profile/ProfileCard/FieldRow.tsx:115` treats all arrays with choice-label join; `:59` stringifies any editing value. No table-specific branch present in inspected component.
- Profile Export button clicked; no in-page result or agent-owned new tab observed. Download/print result unverified. No additional app console errors during approved application/profile pass.
