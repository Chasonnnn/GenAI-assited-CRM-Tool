# Case Questionnaire Expansion (Draft Plan)

## Aims
- Expand the case detail view to show full questionnaire data with inline edits.
- Preserve questionnaire edits and visibility settings across exports/imports.
- Keep Meta lead ingestion and case conversion stable (no breaking changes).

## Methods
- Use `meta_leads.field_data_raw` as the base questionnaire source (multi-select preserved).
- Keep `meta_leads.field_data` for normalized scalar values used by case conversion.
- Reuse the profile overrides system (`case_profile_overrides`, `case_profile_hidden_fields`) to store edits and hidden fields.
- Use `meta_form_versions` to render labels and field types; fall back to raw keys when schema is missing.
- Add CSV export columns with JSON payloads:
  - `meta_lead_field_data_raw`
  - `case_profile_overrides`
  - `case_profile_hidden_fields`
  - optional `profile_base_submission_id`
- Extend CSV import to parse the JSON columns and restore:
  - `MetaLead.field_data_raw`
  - `CaseProfileOverride` rows
  - `CaseProfileHiddenField` rows
- Keep PII rules: no raw PII logging and store only JSON in export/import.

## Ideas
- Case detail: expand the existing Case Overview tab with a Questionnaire section (no new tab).
- Inline edits: use current profile edit controls and reuse save/override flow.
- Empty state: if no form schema is available, render key/value pairs from `field_data_raw`.
- Export usability: keep core case columns unchanged and add JSON columns at the end.
- Import safety: validate JSON columns, fail with clear errors on invalid JSON.
