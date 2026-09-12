# Donor details and clinical records

Status: design proposal, September 7, 2026. Application implementation is not authorized.

## Proposed behavior

- Add Race, Height, Weight, and calculated BMI to donor details. Reuse surrogate options, formatting, height conversion, and BMI calculation. Retain donor Education and its existing free-text values. Do not add Education to surrogates in this scope.
- Authorized editors can edit clinical fields inline, as they can on surrogate medical sections today. Each save corrects the selected record and records the change in the restricted audit trail.
- “New record” creates another dated record for the selected clinic type. It preserves previous entries. Offer “Copy selected record” within the creation form for repeated clinic details; quantities and treatment outcomes must not carry forward automatically.
- Keep IVF Clinic, Monitoring Clinic, and Lab Clinic histories independent. Preserve surrogate-only provider, hospital, and insurance sections. Do not version the entire medical card when one clinic changes.
- Display the latest effective record by default. Sort by effective date, with creation order as a deterministic tie-breaker. Editing an older record does not change its effective date or make it current. Backdated entries remain in chronological order. Exclude future-effective records from the default until their date arrives.
- Select history by date and clinic name. Label the selected historical entry clearly. Permit corrections under the same edit permission; selection alone never restores it as current.
- Require explicit save for a new record. Cancel has no effect. Existing field saves keep their current loading/error behavior. A failed save preserves the input and selected record.
- Keep record history distinct from audit history: new records describe different dated states; audit revisions record corrections within one state. Do not create a user-visible version for every corrected phone digit.

## Treatment quantities: proposed, not confirmed

- Egg donor: eggs retrieved and mature eggs, per retrieval. Mature eggs cannot exceed eggs retrieved when both are known.
- Surrogate: embryos transferred, per embryo-transfer attempt.
- Sperm donor quantities remain undecided; do not label retrieval fields as applicable to sperm donors.
- Store quantities with the treatment attempt, including treatment date and the clinic used at that time. Preserve that clinic association when the current clinic changes.
- Display the same attempt on the profile and match workspace. Do not create independent copies or sum attempts into an ambiguous “Quantity” field. Distinguish zero from unknown.
- Current attempts require a match. Whether staff need to enter treatment history from before a match is an open scope decision. Do not create placeholder matches or silently exclude that workflow.

## Existing code

- `apps/web/components/surrogates/MedicalContactSection.tsx` already accepts generic record data and an update callback. It renders clinic/provider names, address, phone, fax, and optional email using inline editors.
- `apps/web/components/surrogates/AddressFields.tsx` supplies address editing.
- `apps/web/components/surrogates/CombinedMedicalInsuranceCard.tsx` defines section types but is coupled to `SurrogateRead` and flat surrogate fields. Adding a section does not create a historical record; deleting a section clears its current fields.
- `apps/web/components/intended-parents/IntendedParentClinicCard.tsx` is another consumer to inspect before moving shared medical components. Intended-parent behavior is outside this change.
- `apps/web/components/surrogates/detail/SurrogateDetailLayout/dialogs/EditDialog.tsx` contains Race options and height/weight editing. `apps/api/app/schemas/surrogate.py` exposes calculated BMI.
- `apps/web/app/(app)/donors/[id]/components/DonorDetailSections.tsx` contains the donor details layout. `apps/web/components/donors/DonorFormFields.tsx` contains donor editing fields.
- `apps/api/app/db/models/matches.py` and `apps/web/components/matches/MatchAttemptDialog.tsx` already support retrieval, collection, and embryo-transfer attempts, with dates/status/outcome but without structured clinic or quantity fields.
- `docs/layouts.md`, referenced by repository instructions, is absent. Existing components, theme tokens, and the synthetic donor screenshot are the visual references.

## Implementation sequence after design approval

1. Extract shared demographic fields/helpers with donor and surrogate adapters. Preserve Race aliases, labels, units, existing Education values, and null behavior. Keep donor layout consistent with its current light profile.
2. Move reusable medical contact rendering and section definitions into the shared records area. Separate contact field rendering from the surrogate-specific container. Preserve intended-parent consumers with focused checks; do not refactor unrelated record modules.
3. Add dated, organization-owned clinical records with explicit donor or surrogate ownership, effective dates, actor/timestamps, and concurrency protection. Enforce exactly one valid owner and tenant-safe relationships. Add a restricted correction audit within the same transaction.
4. Add authorized list/create/update access and a shared clinical section with per-type selection, latest-record default, inline editing, and new-record form. Preserve existing membership, record access, CSRF, archive, and permission rules. Shared UI must not grant access across record types.
5. Migrate existing nonempty surrogate clinic fields into initial records without fabricating historical clinical dates. Use an explicit imported/current baseline for unknown effective dates. Keep existing flat API outputs as read projections during the transition; route writes through one service. Trace imports, forms, print, exports, and other consumers before removing old storage. Never maintain two independently writable sources.
6. Extend existing treatment attempts with confirmed quantities and a stable clinic association. Add profile views over those same attempts. Resolve pre-match treatment history before committing to this data model.
7. Validate focused behavior and rendered donor/surrogate states, then review the complete change before any release request.

## Acceptance checks

- Editing the latest record changes that record without increasing the record count; its correction is auditable.
- Creating a new effective record retains older values and selects the current record correctly. Editing or adding a backdated entry does not unexpectedly replace the current clinic.
- IVF, monitoring, and lab histories do not change each other. Historical treatment attempts retain their clinic and counts.
- Race labels, height conversion, and calculated BMI agree between donor and surrogate; missing measurements never display BMI zero.
- Empty, loading, populated, historical, read-only, archived, validation-error, and failed-save states render correctly. Keyboard users can select records, edit, cancel, and recover focus.
- Denied access, cross-organization reads/writes/relationships, CSRF, stale-write conflicts, and retried creation requests are covered. Audit and record writes succeed or fail together.
- Migration preserves current values and unknown dates, creates no empty records, and leaves print/import/export behavior intact.

## Design review

Three image mockups compare an inline record selector, a history drawer, and a permanent record list. The inline selector is recommended because it preserves the existing compact card and keeps routine editing direct. A permanent list makes frequent history comparison easier but uses more space.

- [1: Inline selector](mockups/donor-clinical-records/01-inline-selector.png)
- [2: History drawer](mockups/donor-clinical-records/02-history-drawer.png)
- [3: Record list](mockups/donor-clinical-records/03-record-list.png)

These are generated concept images, not rendered application screens. The second image incorrectly shows a BMI edit icon; BMI must remain calculated and read-only. The third image omits field save/cancel controls; the interactive mockup must include them. All three focus on one IVF section; selectors belong to individual clinic types when multiple sections appear. Preserve existing contact and ownership content when integrating the selected layout.

After selection, build an isolated interactive HTML mockup covering donor details, surrogate clinical records, history selection, inline correction, and new-record creation. Application changes remain a separate approval step.
