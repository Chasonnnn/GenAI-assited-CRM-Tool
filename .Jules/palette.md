## 2025-05-20 - DropdownMenuTrigger Accessibility Pattern
**Learning:** `DropdownMenuTrigger` in this codebase (shadcn/ui) renders a button by default. Wrapping a styled `span` inside it for visual customization creates semantic issues (nested clickable elements if not careful) and misses accessibility features.
**Action:** Apply `buttonVariants` and `aria-label` directly to `DropdownMenuTrigger` instead of nesting styled elements.

## 2025-05-20 - Dynamic Icon Button Accessibility
**Learning:** In lists of items (like file attachments), icon-only buttons (download, delete) often lack context. Adding 'aria-label' with the item name (e.g., "Delete report.pdf" instead of just "Delete") is critical for screen reader users to know *which* item they are acting on.
**Action:** Always include dynamic context in 'aria-label' for repeated action buttons in lists.

## 2025-05-20 - Table Checkbox Accessibility
**Learning:** Table row selection checkboxes often lack accessible names. Adding dynamic `aria-label` (e.g., "Select {Name}") is essential for screen reader users to distinguish between rows.
**Action:** Ensure all selection checkboxes in data tables have unique, descriptive `aria-label` props derived from the row data.

## 2025-02-19 - Add dynamic ARIA labels to icon-only buttons
**Learning:** Icon-only buttons (like edit, download, and delete actions in lists) often lack context for screen readers if they only use static labels or lack them entirely. Adding `aria-label`s with dynamic file/field names (e.g., `aria-label={\`Delete ${file.filename}\`}`) dramatically improves accessibility by ensuring users know exactly which item they are acting on.
**Action:** When implementing repeating lists or tables with item-specific actions (especially icon-only buttons), ensure the `aria-label` includes the item's identifying context, and apply `aria-hidden="true"` to the inner decorative SVG to prevent redundant announcements.
