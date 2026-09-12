# EWI donor form preview

Two platform templates and their published organization forms use `scripts/fixtures/ewi-donor-pre-screening.json`: egg donor and sperm donor. Each has 19 fields across three pages, followed by the platform's review step. The schemas differ only in donor kind and donation-history wording. Six fields map to donor identity: name, email, phone, state, education, and profile photo. Other answers remain in the submission.

Date of birth has no age eligibility filter. College and race/ethnicity are optional. A PNG/JPEG profile photo is required by the current donor publishing contract. SMS remains unconfigured; no counsel approval or sending permission is fabricated. Tracking is `internal_only`.

The seed script requires `ENV=dev`, database `crm_donor_preview` at `127.0.0.1:5549`, and API URL `http://127.0.0.1:8027`. It targets only the synthetic organization created by `/dev/seed`. It uses the existing development login and CSRF-protected form APIs. Rerunning updates the named preview templates and forms, retaining their IDs. It does not create duplicate templates.

```sh
cd apps/api
uv run python ../../scripts/preview_donor_forms.py
```

The local website runs on port 3027 and the CRM web application on 3037. Local `.env` files contain generated development secrets and are excluded from Git. No production environment or provider credentials are used.

## Embed limitation

The existing compact `/embed/forms` renderer deliberately rejects file uploads. The temporary `/prototype/donor-intake/[slug]` route reuses the complete hosted CRM form, including autosave, uploads, validation, review, and submission. It is available only in development with the local API and restricts framing to `http://127.0.0.1:3027`. Production frame protection remains unchanged. This is a local integration preview, not a completed production donor embed adapter.

The preview wrapper hides the platform's generic Privacy/Terms footer and links to the single EWI notice at `http://127.0.0.1:3027/prototype/privacy/`. The website design is pending selection from generated variants A/B/C.

## Validation

- TypeScript, focused ESLint and Ruff passed.
- 21 existing/new frontend checks passed: hosted intake, autosave, and development/production frame policy.
- React Doctor found no issues; its remote score service was unavailable.
- Both local form APIs accepted a synthetic application with photo, rejected missing required photos, and returned the original submission on idempotent retry. Date of birth outside the earlier proposed ranges was accepted without age rejection. Submissions were verified in the isolated database.
- Browser confirmed the actual CRM form renders inside the website with EWI branding and the single notice link. Full browser submission and mobile validation remain pending.
- No migration or shared production form renderer was changed. No provider messages were sent.

Local review services are intentionally left running: website 3027, CRM web 3037, CRM API 8027, Docker container `crm-donor-preview-0912` on 5549. The container holds synthetic preview records only.
