## 2024-05-15 - Focus Visibility for Hover Actions
**Learning:** When using `group-hover` utilities (e.g., `group-hover:opacity-100`) to reveal child elements on hover, applying `focus-visible` directly to a non-focusable child element (like an SVG icon) fails to trigger when the parent receives keyboard focus. This leaves the action invisible to keyboard users.
**Action:** Always apply `group-focus-visible` (e.g., `group-focus-visible:opacity-100`) to the child element alongside `group-hover` so that it becomes visible when the parent container receives focus.
