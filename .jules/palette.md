
## 2024-04-12 - Keyboard Accessibility for Hover-Revealed Elements
**Learning:** Combining Tailwind's `group-hover:opacity-100` with interactive elements creates a significant accessibility issue where keyboard users can tab to the element but cannot see it.
**Action:** When using `group-hover:opacity-100` to reveal interactive elements on hover, always accompany it with keyboard-accessible classes. For focusable elements themselves (like `<Button>`), add `focus-visible:opacity-100`. For non-interactive child elements inside focusable parent elements (like `<PencilIcon>` inside an editable container), add `group-focus-visible:opacity-100`. For overlay containers wrapping focusable child items, use `focus-within:opacity-100`.
