# API request diagnostics

Observed interval: `2026-10-04T20:04:13.038925+00:00` through `2026-10-04T20:50:40.302647+00:00`.
Total recorded HTTP requests: 4,225.
HTTP 5xx responses: 0. Captured uncaught exception records: 0.

Logging began after the controlled API restart. Each record contains UTC time, method, route template, route name, and status. No URL query, raw resource path, tokens, bodies, or credentials are logged. Requests include concurrent QA lanes, so the counts below do not identify individual actors.

| Status | Method | Route template | Count |
| --- | --- | --- | --- |
| 422 | POST | `/messaging/conversations/{conversation_id}/link` | 2 |
| 422 | GET | `/settings/invites/accept/{invite_id}` | 1 |
| 422 | POST | `/surrogates` | 1 |
| 422 | GET | `/tickets/{ticket_id}` | 1 |
| 422 | POST | `/tickets/{ticket_id}/link-surrogate` | 1 |
| 409 | POST | `/appointments/{appointment_id}/reschedule` | 2 |
| 409 | POST | `/queues` | 1 |
| 404 | GET | `/book/self-service/{org_id}/manage/{token}` | 1 |
| 404 | GET | `/donors/{donor_id}` | 1 |
| 404 | GET | `/forms/public/embed/{slug}/frame-policy` | 1 |
| 404 | GET | `/forms/{form_id}` | 1 |
| 404 | GET | `/intended-parents/{ip_id}` | 1 |
| 404 | POST | `/messaging/conversations/{conversation_id}/link` | 1 |
| 404 | GET | `/public/messaging-consent/{token}` | 1 |
| 404 | POST | `/tickets/{ticket_id}/link-surrogate` | 1 |
| 404 | GET | `/{surrogate_id:uuid}` | 3 |
| 404 | GET | `<unmatched>` | 2 |
| 403 | GET | `/analytics/surrogates/by-status` | 3 |
| 403 | GET | `/analytics/surrogates/trend` | 6 |
| 403 | GET | `/appointments` | 5 |
| 403 | GET | `/appointments/booking-link` | 3 |
| 403 | GET | `/appointments/status-counts` | 3 |
| 403 | GET | `/appointments/types` | 3 |
| 403 | GET | `/assignees` | 5 |
| 403 | GET | `/created-dates` | 2 |
| 403 | GET | `/dashboard/attention` | 3 |
| 403 | GET | `/dashboard/upcoming` | 3 |
| 403 | GET | `/donors` | 1 |
| 403 | GET | `/intelligent-suggestions/summary` | 2 |
| 403 | GET | `/settings/invites` | 4 |
| 403 | GET | `/settings/permissions/members` | 4 |
| 403 | GET | `/settings/pipelines/default` | 1 |
| 403 | GET | `/stats` | 6 |
| 403 | GET | `/surrogates` | 2 |
| 403 | GET | `/tasks` | 8 |
| 403 | POST | `/tasks` | 2 |
| 403 | GET | `/{surrogate_id:uuid}` | 4 |
| 400 | PUT | `/forms/public/intake/{slug}/draft/{draft_session_id}` | 3 |
| 400 | POST | `/forms/public/intake/{slug}/submit` | 2 |
| 400 | POST | `/workflow-metrics/events` | 2 |

403s include deliberate denied-role tests. 404s include cross-organization records and invalid or invalidated public links. 409s include scheduling conflict tests. 422s include invalid ticket, messaging, and invitation inputs. 400s include public form validation. Individual lane reports identify user-visible defects.

Before diagnostic logging, initial uninitialized calendar availability returned503; refreshing the synthetic provider snapshot recovered booking and rescheduling. The planned API restart briefly interrupted notification polling. Neither condition demonstrates an application defect on its own.

The Messaging page initially raised a frontend TypeError because the communication fixture omitted the standard promotional route. The fixture was repaired and the page recovered; see integrations-security.md. A backend 200 response does not establish a successful frontend render.
