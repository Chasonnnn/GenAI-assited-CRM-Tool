## 2025-05-20 - DropdownMenuTrigger Accessibility Pattern
**Learning:** `DropdownMenuTrigger` in this codebase (shadcn/ui) renders a button by default. Wrapping a styled `span` inside it for visual customization creates semantic issues (nested clickable elements if not careful) and misses accessibility features.
**Action:** Apply `buttonVariants` and `aria-label` directly to `DropdownMenuTrigger` instead of nesting styled elements.

## 2025-05-20 - Dynamic Icon Button Accessibility
**Learning:** In lists of items (like file attachments), icon-only buttons (download, delete) often lack context. Adding 'aria-label' with the item name (e.g., "Delete report.pdf" instead of just "Delete") is critical for screen reader users to know *which* item they are acting on.
**Action:** Always include dynamic context in 'aria-label' for repeated action buttons in lists.

## 2025-05-20 - Table Checkbox Accessibility
**Learning:** Table row selection checkboxes often lack accessible names. Adding dynamic `aria-label` (e.g., "Select {Name}") is essential for screen reader users to distinguish between rows.
**Action:** Ensure all selection checkboxes in data tables have unique, descriptive `aria-label` props derived from the row data.

## 2025-05-20 - Custom Button Focus Visibility
**Learning:** Custom interactive elements (like `button`s built specifically for dashboard panels or AI assistant history items) often lack keyboard focus states by default when styled directly with Tailwind classes. The design system relies on `focus-visible` utilities rather than `focus` to ensure focus rings are only shown for keyboard users and not mouse clicks.
**Action:** When building custom interactive elements, always include `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2` (and ensure the element has a `rounded` class) to match the application's default focus styles and maintain accessibility for keyboard navigation.
