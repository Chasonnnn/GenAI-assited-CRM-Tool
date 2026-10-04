# Import and surrogate bulk QA

## Import

- Live `/surrogates/import` loaded successfully as Test Admin.
- Upload control and empty Import History rendered.
- Synthetic CSV fixtures prepared locally for three valid rows including one duplicate, fractional height, dates, states, source, and unknown column; separate invalid-field/email fixture prepared.
- The documented file-chooser upload flow stalled for about 11 minutes while the Mac was locked and was interrupted. No successful upload, mapping preview, validation, approval, or import was observed.
- Root instructed all agents to stop file-chooser attempts. The chooser was not retried or bypassed.
- Synthetic fixture files were prepared under `/private/tmp/crm-live-qa-import/` and removed after the blocked attempt; no data from user files was uploaded.

## Bulk and list

- Surrogate list loaded 93 synthetic records across four pages. No board or export control is exposed on this current list screen; neither was claimed as tested.
- Name sorting verified descending (Zoey, Violet, Victoria) and ascending (Abigail Jones, Abigail Lee, Abigail Lewis); URL reflected column/direction.
- Next opened page 2 with rows 31–60 and preserved sorting. Page input 99 clamped to page 4, rows 91–93, with Next disabled. Page input 0 clamped to page 1.
- More Filters opened; source options displayed human labels. Source Website and Assignee Test Admin composed correctly, returning only three Website records assigned to that user. Both filter chips displayed labels. Reset cleared filters and sort.
- Date preset menu rendered All Time, Today, This Week, This Month, Custom Range. Today produced `range=today` and October 4 records. Other presets/custom dates were inspected but not applied.
- New surrogate form rejected `.invalid` domain with a visible email validation message. Reserved `example.com` synthetic addresses succeeded. New records opened detail, Back preserved the Today filter.
- Created QA Bulk Alpha #S10094 (`62d571b2-60d4-4bfd-8f25-eecf5b3bf214`) and QA Bulk Beta #S10095 (`fdde543b-747f-44c2-9f19-def8295b9012`). These were the only records changed in bulk.
- Search QA Bulk reduced the table to those two. Select all selected exactly two and showed the bulk bar. Assign to menu exposed seeded users; assigning Test Admin updated both rows and cleared selection.
- Bulk Change stage dialog required target selection. Stage groups Intake, Post-approval, Paused & closed rendered readable labels. Forward change to Contacted succeeded for both with a two-record success message and cleared selection.
- Reopening bulk change and selecting New Unread required a reason and disabled submission while blank. Entering a reason enabled submission; Cancel preserved Contacted.
- Archive two-record confirmation opened with correct count and cancelled without mutation. Clear removed selection.
- Reload preserved both records as Contacted, assigned Test Admin, and retained search/date filters.
- Console checkpoint after these interactions returned no warning/error entries.

## Result and limits

No new functional defect confirmed in these completed list/bulk checks. CSV mapping, validation, duplicate resolution, import approval/execution, import history after execution, bulk partial failures, actual archive/restore, board, and exports remain unverified in this assignment. No provider calls, messages, deletions, production code, or test changes were made.

Evidence: `screenshots/bulk-assignment-stage.jpg` shows the persisted two-record result.
