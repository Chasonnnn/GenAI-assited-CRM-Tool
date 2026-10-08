## 2025-05-20 - DropdownMenuTrigger Accessibility Pattern
**Learning:** `DropdownMenuTrigger` in this codebase (shadcn/ui) renders a button by default. Wrapping a styled `span` inside it for visual customization creates semantic issues (nested clickable elements if not careful) and misses accessibility features.
**Action:** Apply `buttonVariants` and `aria-label` directly to `DropdownMenuTrigger` instead of nesting styled elements.

## 2025-05-20 - Dynamic Icon Button Accessibility
**Learning:** In lists of items (like file attachments), icon-only buttons (download, delete) often lack context. Adding 'aria-label' with the item name (e.g., "Delete report.pdf" instead of just "Delete") is critical for screen reader users to know *which* item they are acting on.
**Action:** Always include dynamic context in 'aria-label' for repeated action buttons in lists.

## 2025-05-20 - Table Checkbox Accessibility
**Learning:** Table row selection checkboxes often lack accessible names. Adding dynamic `aria-label` (e.g., "Select {Name}") is essential for screen reader users to distinguish between rows.
**Action:** Ensure all selection checkboxes in data tables have unique, descriptive `aria-label` props derived from the row data.

## 2024-10-08 - Added Default ARIA Label to Shared UI Components
**Learning:** Reusable, composable components (like `CopyButton` which extends `Button`) that often render as icon-only UI are common sources of missing accessibility labels if not enforced at the prop level. Providing an intelligent default `aria-label` inside the shared component itself (falling back when `children` are empty) ensures a baseline of accessibility across the entire application without requiring manual prop passing at every call site.
**Action:** When auditing or building shared UI components that can render in visually minimal states (e.g., icon-only buttons, generic triggers), proactively implement sensible fallback `aria-label` logic at the component definition level rather than relying solely on developers to provide them at instantiation.
