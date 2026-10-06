# EWI Permission V2 activation — October 5, 2026

EWI Family Global activated Permission V2 at 10:06 p.m. America/New_York. The authenticated policy endpoint returned version `2`, status `active`, and configuration revision `2`.

## Release verification

- Production API, worker, and web images match successful builds from `7fddce14a5653340281ac2b97a86d81901556c81`.
- This release contains permission fixes merged through PR #800 (`6f4607109`).
- Production readiness returned version `0.91.82`; the database reached `20261005_0100_under_review_scope`.

## Applied decisions

- All 46 historical record fingerprints matched the approved plan.
- All 46 reviews completed: three retained current Intake assignees; 43 added no historical collaborator.
- The activation audit confirms 44 transfers into the shared Surrogate Pool. Two candidates already belonged to that pool.
- Case Manager surrogate scope is `all` / `under_review_onward`. Creator access remains part of the deployed policy.
- Intake's Intended Parents and Matches view permissions remain disabled. No deferred match-specific exception was added.

## Workflow continuity

The existing organizational Welcome Email for New Lead workflow was paused by activation and re-enabled under V2 authority. Its trigger, conditions, action, and email-template reference matched the approved configuration.

The bounded request-to-restart window was `2026-10-06T02:05:55.300Z` through `2026-10-06T02:06:21.999188Z` (October 5, 10:05:55–10:06:22 p.m. Eastern).

No active surrogate in the newest-record results was created during that window. The latest active record preceded activation by 49 minutes. No surrogate-creation audit event appeared during the window. No test send or execution replay was requested.

## Verification

- The activation audit digest matches the final reviewed preview; its committed transfer count is 44.
- The live access checker allows all three retained records through `collaborator` access.
- The live role editor displays Case Manager scope as “Under Review and later.”
- Intake's IP and Matches View controls both report `aria-checked=false`.
- The Welcome workflow toggle returned HTTP 200 and displays enabled. Its executable configuration is unchanged.
- Both inspected browser tabs reported zero console errors.
- Post-activation Cloud Logging queries returned no API or worker entries with severity ERROR or higher during verification.

Private previews, audit identifiers, record checks, and screenshots remain in Git-ignored `.exports/permission-v2-activation-20261005/`. The approved private plans are marked applied. No local QA services were started.
