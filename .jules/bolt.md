## 2025-01-20 - N+1 Query on Mailbox Loading in Ticketing Sync

**Learning:** SQLAlchemy pre-fetching of records with `.in_()` over an extracted collection of foreign keys converts an N+1 looping bottleneck into an O(1) loop lookup against an O(1) query. It prevents repeatedly calling `.first()` on `Mailbox` items within an iteration over `UserIntegration`s.
**Action:** When iterating over objects to find matching relations based on secondary properties, always bulk-fetch the relations before entering the loop and transform them into a quick-access map (e.g., dict mapping user integration ID to a list of/a specific matching mailbox).
