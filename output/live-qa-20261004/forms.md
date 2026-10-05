# Forms local browser QA

Revision: `65bca746e`. Date: 2026-10-04. Environment: isolated local database, synthetic organization and applicants, shared Chrome admin, external provider calls blocked. Browser interactions used CUA; server responses were inspected through browser CDP only for diagnosis.

## Confirmed findings

### F1 — P2: Partially completed fixed tables disable draft autosave

Reproduction:
1. Open the published `qa-comprehensive-intake-20261004` intake form with a fresh draft.
2. Enter a name and answer only Item1 of the optional fixed table. Each table row has a required Response column.
3. Wait for autosave: the header changes to `Autosave unavailable`.
4. Browser Network shows draft PUT HTTP400: `Missing required value: Item 2 / Response`.
5. Complete Item2 and Item3: the header changes to `Saved`; reload restores the completed answers and name.

Expected: draft storage accepts incomplete answers and preserves progress; final submission enforces required cells. Actual: one partially completed table prevents the entire current draft from saving. This can lose unrelated edits on reload.

Source corroboration: `apps/api/app/services/form_intake_service.py:3091` loops over provided draft answers and calls the full `_validate_field_value` validator before saving. The environment agent separately reproduced the validation failure with a rolled-back service call. No Redis or external provider dependency caused this result.

### F2 — P2: Standalone submission queue omits mapped applicant identity

Reproduction:
1. Create a form with the builder's Full Name and Email presets. These get UUID field keys mapped to identity fields.
2. Submit through hosted intake or the real iframe embed.
3. Open the form builder's Submissions tab: applicant name/email are present.
4. Open `/automation/form-submissions`, select the same form: name/email/phone/DOB display `—` in history and lead promotion cards.

Reproduced for both all-field hosted intake and two-field embedded lead capture. This prevents reviewers from identifying applicants in the standalone queue. Form selector labels and `?form=` navigation work.

Source corroboration: `apps/web/app/(app)/automation/form-submissions/page.tsx:113` spreads the presentation helper without supplying field mappings. `apps/web/lib/forms/submission-presentation.ts:5` defaults mappings to an empty list. The builder explicitly supplies mappings at `apps/web/lib/forms/use-automation-form-builder-page.ts:1144`.

Evidence: `screenshots/forms-standalone-missing-identity.jpg`, `screenshots/forms-builder-identity-present.jpg`.

## Passed browser scenarios

| Surface | Executed checks and observed result |
| --- | --- |
| Form list | Empty state; create name blank/whitespace blocked; optional description; Surrogate/Egg Donor/Sperm Donor option labels; count changes; Draft/Published/Default badges; submission count6; just-saved relative timestamp. Case-insensitive whitespace-trimmed search, no-match state, All/Published/Drafts/Archived filters. |
| Templates | Four published templates loaded; search/no-match state; Use Surrogate Pre-Screening Questionnaire creates editable draft with its mapped fields and human choice labels. Renamed the disposable copy. |
| Deletion | Duplicated template page; Delete Page cancel and confirm; remaining original page preserved. Draft form menu disables Share. Delete form cancel and confirm removes only the disposable template copy and decrements count2→1. |
| Builder fields | Empty form Publish disabled with missing identity list; readiness Add inserts mapped field. Added full name/email/phone/DOB and all general types: text, textarea, number, select, multiselect, radio, checkbox, date, address, height, file, fixed table, repeating table. Renamed page and added second page. Library search no-match state. |
| Field settings | Edited choice labels, removed/added options. Configured Long Text to show when Select=Alpha label, min5/max40. Repeating table min1/max3, add/remove column. Autosave and manual Save observed; saved settings survived navigation/reload. |
| Preview | Both sections in one scroll; conditional textarea hidden then revealed by Alpha label. Desktop/Mobile Preview toggles. Repeating minimum disables removal; maximum3 disables Add Row. Screenshot `forms-builder-mobile-preview.jpg`. |
| Form settings | Saved public eyebrow/title/subtitle, privacy notice, upload size1MB/count2/MIME application/pdf,image/png. Correct disabled no-org-logo/default-before-publish controls. First published surrogate application becomes Default Active. |
| Routing | Changed Review first→Link automatically, After review→Automatically, Default→Website. Dirty Save routing becomes enabled; save toast and disabled clean control. New workflow menu exposes submitted/approved/rejected triggers. Donor photo-scan auto-create switch saved off. |
| Publish/share | Publish confirmation and published state; generated hosted URL; Copy Link success. Hosted/QR/Embed tabs. SVG4237bytes and PNG3913bytes downloads verified on filesystem. Wrong-purpose application embed health blocked; missing origin prevented enabling. |
| Hosted validation | Empty submit reports required name/email/phone/DOB and focuses first invalid field. Invalid email/phone errors. Date picker month/year/day. Identity Complete when valid. Conditional min5 failure and recovery. Choices, multiselect, radio, checkbox, address, number, height5ft6in. Fixed table No/Yes/No; repeating row values/add/remove/max3/min1. |
| Hosted submission | Valid example.com synthetic email submitted successfully. Confirmation `Application Submitted!`; screenshot `forms-public-submitted.jpg`. Reload returns a fresh reusable intake form. Exactly one new result appeared in staff history for the successful action. |
| Draft persistence | After completing fixed table, Saved timestamp and Restored saved progress appeared after reload with name/table preserved. Independent coverage agent verified390px public draft autosave/reload. |
| Routing review | Seeded ambiguous submission shows2 candidates; empty manual-ID action reports Enter a surrogate ID. Linked first candidate with reviewer notes; ambiguous count1→0. Create lead from no-match routing review succeeds; review count1→0. Public lead promoted to surrogate with correct detail link. |
| Submission history | All/Pending/Processed filters and empty pending state. Review status and matching outcome displayed separately. Counts updated after mutations. |
| Application review | Promoted surrogate application shows submitted choices by labels, all scalar answers, fixed/repeating table content. Reject blank/whitespace blocked; Cancel preserved pending. Approve dialog previews mapped updates; notes and confirmation yield Approved. Separate pending fixture rejected with reason and displayed Rejected. |
| Application editing | Edit Select Alpha→Beta; Save Changes1 succeeded; Beta persisted after reload. Screenshot `forms-approved-application.jpg` was captured before that edit. |
| Donor form | Egg Donor creation changes palette and requires name/email/profile photo. Removing Required from photo blocks Publish; readiness Mark required restores eligibility. Published successfully. Donor Embed tab explicitly permits hosted link only. |
| Real iframe embed | Created Lead Capture form with required name/email; enabled exact localhost:3000 origin, Internal Only tracking, synthetic consent. Health Ready to embed. Temporary host on existing3000 loaded iframe and handshake. Empty/invalidemail validations passed. Valid submit→Request received. Screenshot `forms-embed-submitted.jpg`. Staff queue persisted one new submission. Run match→No match, Dismiss review, Keep As Lead all succeeded. Temporary host removed. |
| Standalone queue | Form selector human labels and URL query selection work; same submission counts/statuses load. Identity display fails as F2. |
| Phone layout | Coverage agent separately verified390px public form: section layout, conditional show/hide, choice controls, height, repeat minimum/add/remove, autosave/reload. Screenshot `public-intake-mobile.jpg`. |

## Fixtures and outcomes

| Fixture | ID or URL | Final state |
| --- | --- | --- |
| Comprehensive form | `0faa0607-0f97-4660-b7b5-f6b5b84f0bcb`; `/intake/qa-comprehensive-intake-20261004` | Published, default surrogate application,6 submissions (5 seeded +1 browser). |
| Public applicant | Surrogate `26d07429-13b9-48dc-a3bc-3a6c68884310` | Browser submit→lead→promote→approved; edited Select Beta persisted. |
| Pending fixture | Submission `bf13507f-7e2a-4d13-a3d9-815283715d6f` | Rejected through UI. |
| Ambiguous fixture | `44181caa-3186-43d2-b026-eed8414468c1` | Linked to first candidate through UI. |
| Routing fixture | `5e78c1d2-0d70-4554-a3d9-978f64a018c5` | Intake lead created through UI. |
| Donor form | `ccf88b40-06dd-463d-96b8-2fd2577975e3`; `/intake/qa-egg-donor-readiness` | Published, photo required, auto-create donor disabled; no upload/submission. |
| Embed form | `eaf8eedb-ad35-40b3-9d64-dbd348053a41`; `/intake/qa-lead-capture-embed` | Published, one real iframe submission retained as lead. |
| Template copy | `e2c66205-9d88-481e-bd80-75700e8deff7` | Created, page duplication/deletion tested, form deleted. |

## Console and non-defect diagnostics

- Final public and iframe warn/error lists were empty. Builder had one `Handshake rejected - notifications will use polling fallback` warning at20:04:09UTC, matching the local API diagnostic restart. No uncaught exception/hydration warning observed in forms flows.
- Initial `example.invalid` test email passed frontend format checks but backend rejected with HTTP400. Generic submit toast hid the field detail; switching to example.com succeeded. This was not a provider/runtime failure. The later F1 reproduction had no email and isolated table validation.
- SVG browser download-event wait timed out despite actual successful download. File chooser attempt hung and was interrupted; native Chrome inspection then reported the Mac locked. These are tooling limitations, not confirmed app defects.
- Direct embed route without a parent handshake showed unavailable-for-this-website, as expected. Application form was wrong-purpose for iframe; the separate valid Lead Capture fixture proved the real iframe path.

## Unverified scope

- File and logo uploads, invalid file type/size/count, scan/rescan/download/remove, donor uploaded-photo submission and photo-based donor creation. File picker blocked this path.
- Drag reorder/insertion, every field/table validation combination, every preset, every template, Sperm Donor creation, workflow creation from form menu, re-publish snapshot behavior, concurrent edits, double-click/race idempotency, every role/tenant denial case. No claim of exhaustive coverage.
- QR appearance/scannability was not decoded; downloads were verified by filename/nonzero size. No external email/SMS/provider delivery.

## Cleanup

- No production code changes. Removed temporary `apps/web/public/__qa-embed-20261004.html`. No extra server started.
- Root cleanup handoff: `/tmp/crm-forms-qa/invalid.txt`, `/tmp/crm-forms-qa/pixel.png`, `/tmp/crm-forms-qa/oversize.png`; `/Users/chason/Downloads/qa-comprehensive-intake-20261004-qr.svg`; `/Users/chason/Downloads/qa-comprehensive-intake-20261004-qr.png`.
- Browser task tabs closed after evidence capture. Shared admin authentication retained for other agents. Synthetic database fixtures remain until root environment cleanup.
