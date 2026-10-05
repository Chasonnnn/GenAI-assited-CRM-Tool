# Supplementary mobile dashboard and reports QA

Revision `65bca746e`, 2026-10-04. Chrome through CUA, isolated synthetic developer profile, 390×844 viewport. Disposable local environment. No additional product defect found. Date-boundary findings remain in [reports-dashboard.md](reports-dashboard.md).

## Dashboard

- Header, date/assignee controls, summary cards, trend chart, pipeline chart, and attention/upcoming panels fit a single-column mobile layout. Measured viewport width and document scroll width both 390px.
- Sidebar opened from its toggle. Escape closed it. Clicking the visible backdrop outside the drawer closed it. Selecting Reports closed the drawer and navigated correctly.
- Date-range menu showed All Time, Today, This Week, This Month, Custom Range. Custom Range displayed two vertically stacked calendars, Back, instructions, and disabled Apply before selection. All controls fit; Back and Escape dismissed it. Date calculations were not repeated.
- Assignee Mine updated the human-readable trigger, URL, cards, and charts; Reset restored All Assignees and removed the query parameter.
- Trend Week and pipeline percentage controls updated selected states and chart axes. Charts remained readable.
- Upcoming This Week expanded its empty state and collapsed Attention Needed. Both panel controls remained reachable.

Evidence: [Dashboard](dashboard-mobile.jpg), [custom date popup](dashboard-mobile-filter.jpg).

## Reports

- Summary cards, AI summary, stage/trend/team charts, conversion funnel, state map, donor charts, Meta spend empty state, and individual-performance sections stacked vertically without page-wide horizontal overflow. Measured viewport and document scroll width both 390px.
- Campaign filter opened within the viewport. Selecting a seeded campaign updated its trigger, funnel, and geographic empty state. All campaigns restored the populated map.
- Egg/Sperm donor selector remained reachable and switched totals and chart labels.
- Created Cohort/Activity Window menu remained reachable and updated the explanatory label, chart, and performance rows.
- The desktop performance table rendered mobile summary cards with complete metric labels and values, rather than requiring horizontal table scrolling. The selected mode and each card fit the viewport.
- Export PDF was visible but not repeated; root already tested the export request.

Evidence: [Reports](reports-mobile.jpg), [performance cards](reports-mobile-performance.jpg).

## Console and cleanup

No application console warning/error appeared. Captured warnings came only from the unrelated AssignmentCache browser extension. [Console](supplementarymobile-console.json).

The CUA semantic click on the full-screen sidebar backdrop targeted its geometric center under the drawer; the visible right-hand backdrop was then clicked successfully. This was treated as an automation-targeting limitation.

Temporary viewport override reset; agent-created tab closed. No services started, production code edited, or data mutated.
