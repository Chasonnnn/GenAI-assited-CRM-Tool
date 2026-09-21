# Release 0.91.66 candidate QA

Status: current local QA passed with synthetic records. This package is release-candidate evidence; it does not indicate deployment, production activation, or external provider acceptance.

## Verified results

| Area | Result |
| --- | --- |
| Donor intake | Local HTTP ingress created separate egg- and sperm-donor records; replay reused the existing record without duplicate side effects. |
| Website donor forms | New and existing-applicant paths passed; persisted mapped answers and synthetic profile images were visible in the reviewed UI. |
| Workflows and outbound events | Form workflows completed; retry and rejection behavior passed; a configured donor-stage event reached a local receiver. |
| Interview lifecycle | Schedule, reschedule, cancel with stage change, and rebook passed focused tests and live local QA. |
| Interview activity layout | Manage stays on the latest scheduled or rescheduled entry after cancellation, the three dialog actions share one row, and the transition preview uses equal-width stage labels around a centered arrow. |
| Validation | The combined focused frontend suite passed 74 tests across activity timelines, the interview manager, form builder, and surrogate hooks. Focused backend suites, type checking, scoped linting, Ruff checks, and diff checks also passed. Other suite counts overlap and are not combined. |

## Remaining limits

- Meta and Zapier acceptance, credentials, production provider activation, and an end-to-end production event were not tested. The outbound screenshot shows a local receiver result.
- ClamAV was unavailable. Synthetic uploads were accepted with attachment scanning disabled, so malware scanning remains unverified.
- Donor application approval and apply-to-profile controls remain incomplete. An existing donor's uploaded photo stays attached to the submission and cannot be applied from donor detail; new-donor promotion copies the photo.
- Production workers, production writes, external sends, and deployment were outside this QA run.

All names, email addresses, phone numbers, records, and images shown in this package are synthetic QA data.
