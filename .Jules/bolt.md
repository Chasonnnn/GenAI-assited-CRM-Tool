## 2024-05-18 - [Optimizing Component Count List Fetches]
**Learning:** React components that use the `useMatches` pattern with multiple statuses will fetch full pages of entity data (e.g. 50 items each) just to access the `.total` properties.
**Action:** When a page just needs count statistics by status, replace individual filtered list queries with the dedicated `useMatchStats` hook which uses an optimized `GROUP BY` backend endpoint to avoid massive N+1 data over-fetching payloads.
