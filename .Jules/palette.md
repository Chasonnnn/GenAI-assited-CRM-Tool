## 2025-05-20 - DropdownMenuTrigger Accessibility Pattern
**Learning:** `DropdownMenuTrigger` in this codebase (shadcn/ui) renders a button by default. Wrapping a styled `span` inside it for visual customization creates semantic issues (nested clickable elements if not careful) and misses accessibility features.
**Action:** Apply `buttonVariants` and `aria-label` directly to `DropdownMenuTrigger` instead of nesting styled elements.

## 2025-05-20 - Dynamic Icon Button Accessibility
**Learning:** In lists of items (like file attachments), icon-only buttons (download, delete) often lack context. Adding 'aria-label' with the item name (e.g., "Delete report.pdf" instead of just "Delete") is critical for screen reader users to know *which* item they are acting on.
**Action:** Always include dynamic context in 'aria-label' for repeated action buttons in lists.

## 2025-05-20 - Table Checkbox Accessibility
**Learning:** Table row selection checkboxes often lack accessible names. Adding dynamic `aria-label` (e.g., "Select {Name}") is essential for screen reader users to distinguish between rows.
**Action:** Ensure all selection checkboxes in data tables have unique, descriptive `aria-label` props derived from the row data.

## 2025-02-14 - Fix Base UI Accessible Names for Icon Buttons
**Learning:** For components built using `@base-ui/react` (like `Dialog` and `Sheet`) that pass a `render` prop containing a `<Button>` wrapping an icon, wrapping text in an `<span className="sr-only">` inside the button can be less robust than applying `aria-label` directly to the `Button`. Furthermore, screen readers can redundantly announce the icon SVG unless `aria-hidden="true"` is explicitly added to the icon element itself.
**Action:** When customizing components like `DialogContent` or `SheetContent` close buttons, ensure the `<Button>` has an explicit `aria-label` describing its action, remove `<span className="sr-only">` elements containing text inside the button, and apply `aria-hidden="true"` to the inner SVG icon (e.g., `<XIcon>`) to prevent redundant screen reader announcements.
