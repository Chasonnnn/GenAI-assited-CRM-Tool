# Reports and dashboard browser QA

Revision `65bca746e`; local synthetic administrator, IAB, 2026-10-04.

## Confirmed findings

### REPORT-01 — Date presets exclude the current day from New This Period (P2)

Open Reports with synthetic records created today. All Time displayed 12 in New This Period. Select Today: the card becomes 0 while Surrogates Trend still displays 12 for 2026-10-04. This Month also displays 0 in the card. The label beneath the card remains Last 30 days even when Today is selected.

The frontend sends the same date-only `from_date` and `to_date` for Today (`apps/web/app/(app)/reports/page.tsx:104`). The summary endpoint calls `parse_date_range` without `inclusive_date_end=True` (`apps/api/app/routers/analytics.py:216`). The parser treats the end date as midnight, and the summary counts `created_at < end` (`apps/api/app/services/analytics_surrogate_service.py:85`). The Today interval is empty. Week/month ranges also omit the selected final day.

Evidence: [Today screenshot](screenshots/reports-today-period.jpg). The final capture shows 15 in the trend after further parallel QA creation, while New This Period remains 0. No console error accompanies the incorrect count.

### REPORT-02 — All Time silently uses a 30-day default for several analytics (P2)

All Time passes no date bounds. Shared analytics parsing supplies a 30-day default. The page displayed 92 active surrogates but only 12 recent records in the stage distribution/trend and conversion cohort. This is not an all-time cohort. Source: `getReportDateRange('all')` and `analytics_shared.parse_date_range(default_days=30)`. Individual endpoints have different range handling, so the page mixes total/current metrics and recent cohorts without making those scopes clear.

## Executed checks

- Report summary cards, stage/trend/team charts, conversion funnel, geographic map, donor charts, empty Meta spend state and individual performance table rendered.
- Today and This Month presets changed the selected label and requested new report data; date inconsistency is recorded above.
- Campaign selector displayed seeded ad identifiers with counts. Selecting a campaign updated the trigger, funnel and map; no matching geography showed a clear empty state.
- Egg/Sperm donor toggle changed chart labels and counts, with the archived sperm donor excluded from the active count.
- Created Cohort → Activity Window changed the explanatory label and table metrics. Surrogates column sort changed row order.
- Export PDF button completed its request: `GET /analytics/export/pdf` returned HTTP 200 at20:33:06UTC. Download bytes and PDF rendering were not independently verified.
- No captured browser console errors or warnings during these report interactions.

## Dashboard checks

- Greeting, summary cards, pipeline distribution, trend, attention counts and upcoming task panel loaded with the synthetic administrator.
- Day/Week/Month trend choices rendered the corresponding date buckets. Count/percentage mode changed labels and chart scale.
- Assignee Mine updated active records from 93 to 22, retained the human-readable label, and exposed Reset. Refresh retained the filter; Reset restored All Assignees.
- Upcoming This Week expanded to the two dated tasks with 2:30 PM and 3:30 PM labels. Attention and Upcoming use mutually exclusive expanded panels.
- Keyboard activation of View New Unread surrogates opened `/surrogates?stage=...` with the New Unread trigger and Stage: New Unread chip. The screen-reader stage link's pointer target overlaps the chart; keyboard activation was used for this accessible link.
- Back navigation restored the dashboard. [Dashboard charts](screenshots/dashboard-charts.jpg).
- No captured console warning/error during dashboard interactions.

## Related form checks

- Form-list Share → Copy Link copied the exact published hosted URL and showed Application link copied.
- Direct embed route returned Page not found while this application-purpose form had embedding disabled. This was an expected unavailable configuration, not a demonstrated embed defect; successful iframe embedding was not verified.
