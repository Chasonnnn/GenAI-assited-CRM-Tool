## 2025-05-20 - DropdownMenuTrigger Accessibility Pattern
**Learning:** `DropdownMenuTrigger` in this codebase (shadcn/ui) renders a button by default. Wrapping a styled `span` inside it for visual customization creates semantic issues (nested clickable elements if not careful) and misses accessibility features.
**Action:** Apply `buttonVariants` and `aria-label` directly to `DropdownMenuTrigger` instead of nesting styled elements.

## 2025-05-20 - Dynamic Icon Button Accessibility
**Learning:** In lists of items (like file attachments), icon-only buttons (download, delete) often lack context. Adding 'aria-label' with the item name (e.g., "Delete report.pdf" instead of just "Delete") is critical for screen reader users to know *which* item they are acting on.
**Action:** Always include dynamic context in 'aria-label' for repeated action buttons in lists.

## 2025-05-20 - Table Checkbox Accessibility
**Learning:** Table row selection checkboxes often lack accessible names. Adding dynamic `aria-label` (e.g., "Select {Name}") is essential for screen reader users to distinguish between rows.
**Action:** Ensure all selection checkboxes in data tables have unique, descriptive `aria-label` props derived from the row data.

## 2026-09-16 - SelectTrigger Accessibility Pattern
**Learning:** Select components inside complex popovers/menus (like filter bars) often lack `aria-label` attributes, and their visible labels (using `<Label>`) might not be properly associated via `htmlFor` (or the generic Radix `Select` components miss this association internally). This makes it difficult for screen readers to identify the dropdown's purpose.
**Action:** Always ensure `SelectTrigger` components have descriptive `aria-label` props (e.g., 'Filter by source'), especially when rendering dynamically within popovers without explicit `htmlFor` associations on their labels.
