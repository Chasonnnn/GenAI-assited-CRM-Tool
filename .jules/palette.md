## 2025-04-08 - Focus-Visible Missing on Group-Hover Elements
**Learning:** Some elements in the UI rely on `group-hover:opacity-100` to be shown visually on hover, but are fully missing focus styles for keyboard users. Specifically, when these elements aren't focused but tabbed into they do not gain visibility since there isn't a corresponding focus-visible state.
**Action:** When adding `group-hover:opacity-100` functionality, I will ensure `focus-visible:opacity-100` is also included so keyboard users can properly access and view those actions.
