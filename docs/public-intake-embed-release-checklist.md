# Public Intake Embed Release Checklist

Use this checklist before enabling Public Intake Embed for a pilot agency. V1 scope is iframe-only lead capture: no custom domains, native DOM embed, landing-page builder, arbitrary pixels, or advanced ad-platform routing.

## Change Review
- [ ] Embed feature changes reviewed:
  - `apps/api/app/db/models/form_intake.py`
  - `apps/api/app/routers/forms_public.py`
  - `apps/api/app/services/form_intake_service.py`
  - `apps/api/app/services/embed_policy_service.py`
  - `apps/web/app/embed/forms/[slug]/page.client.tsx`
  - `apps/web/app/embed/forms.v1.js/route.ts`
  - `apps/web/proxy.ts`
  - `apps/web/components/forms/builder/ShareApplicationDialog.tsx`
- [ ] Pre-existing form-system changes reviewed separately from embed-specific changes.
- [ ] Shared/public-form infrastructure touched by both paths has regression coverage.
- [ ] No customer-facing copy frames the feature as an advertising-platform bypass.

## Migration
- [ ] `cd apps/api && uv run -m alembic upgrade head` succeeds.
- [ ] `cd apps/api && uv run -m alembic upgrade head` is idempotent.
- [ ] New nullable/default columns are safe for existing tenants.
- [ ] Indexes exist for public lookup and submission/session paths.
- [ ] Normal rollback does not require migration rollback; disablement switches keep existing data intact.

## Security
- [ ] `/embed/forms/{slug}` has no `X-Frame-Options`.
- [ ] `/embed/forms/{slug}` has dynamic `Content-Security-Policy: frame-ancestors ...` on the initial document response.
- [ ] `/embed/forms/{slug}` uses `Cache-Control: no-store`.
- [ ] Authenticated app routes and hosted intake routes retain frame protection.
- [ ] API CORS has not been widened for customer origins.
- [ ] Allowed origins are exact origins, not wildcards.
- [ ] Origin normalization rejects wildcard, suspicious host, `javascript:`, and `data:` values.
- [ ] Submit requires a valid, unexpired embed session for the matching intake link.
- [ ] Submit requires the current published version and an idempotency key.
- [ ] Rate limits and duplicate controls are active on public endpoints.
- [ ] No raw PII appears in logs, metrics, postMessage payloads, or tracking payloads.

## Privacy
- [ ] `privacy_safe_lead` sends only generic lead event metadata.
- [ ] Form answers, labels, free text, medical/reproductive details, files, qualification status, and disqualification reasons are not sent to ad platforms.
- [ ] Hashed email, phone, and name are not sent to Meta by default.
- [ ] Arbitrary URL parameters are stripped to the attribution allowlist.
- [ ] Sensitive, free-text-unclassified, and file fields block privacy-safe tracking.
- [ ] Consent text is snapshotted per submission.

## CRM
- [ ] Valid embed submission creates `FormSubmission`.
- [ ] Valid embed submission creates or links `IntakeLead`.
- [ ] `LeadAttribution` stores only allowlisted attribution.
- [ ] `ConsentRecord` stores immutable consent text and privacy policy snapshots.
- [ ] `TrackingEventLog` stores only privacy-safe payload data.
- [ ] Duplicate/idempotent submit returns the existing result.

## UX
- [ ] Share dialog exposes Hosted Link, QR Code, and Embed tabs.
- [ ] Embed tab can save allowed origins, tracking mode, and consent text.
- [ ] Embed setup health reports `Ready to embed`, `Needs attention`, or `Blocked`.
- [ ] Snippet copies correctly.
- [ ] Iframe resizes correctly.
- [ ] Mobile rendering is usable.
- [ ] Thank-you state works in the iframe.
- [ ] UI states do not promise that Meta classification will change.

## Regression
- [ ] Existing hosted `/intake/{slug}` public intake works.
- [ ] Existing form publish works.
- [ ] Existing form submission review works.
- [ ] Existing Meta Lead Ads import still works.
- [ ] Existing public booking routes still work.

## Required Commands
```bash
cd apps/api && uv run -m alembic upgrade head
cd apps/api && uv run -m pytest -q
cd apps/api && uv run -m ruff check app tests
cd apps/web && pnpm tsc --noEmit
cd apps/web && pnpm test --run
cd apps/web && pnpm lint
cd apps/web && pnpm build
git diff --check
```

## Browser Smoke Gate
- [ ] Create one published `lead_capture` form with full name and email or phone.
- [ ] Enable embed and add `http://localhost:3100` as allowed origin in dev.
- [ ] Confirm allowed parent page frames and submits successfully.
- [ ] Confirm disallowed `http://localhost:3200` parent cannot frame the embed.
- [ ] Confirm CRM records: `FormSubmission`, `IntakeLead`, `LeadAttribution`, `ConsentRecord`, `TrackingEventLog`.
- [ ] Confirm response headers for allowed and disallowed paths.

