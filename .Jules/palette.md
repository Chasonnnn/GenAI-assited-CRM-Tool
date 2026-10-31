## 2025-05-20 - DropdownMenuTrigger Accessibility Pattern
**Learning:** `DropdownMenuTrigger` in this codebase (shadcn/ui) renders a button by default. Wrapping a styled `span` inside it for visual customization creates semantic issues (nested clickable elements if not careful) and misses accessibility features.
**Action:** Apply `buttonVariants` and `aria-label` directly to `DropdownMenuTrigger` instead of nesting styled elements.

## 2025-05-20 - Dynamic Icon Button Accessibility
**Learning:** In lists of items (like file attachments), icon-only buttons (download, delete) often lack context. Adding 'aria-label' with the item name (e.g., "Delete report.pdf" instead of just "Delete") is critical for screen reader users to know *which* item they are acting on.
**Action:** Always include dynamic context in 'aria-label' for repeated action buttons in lists.

## 2025-05-20 - Table Checkbox Accessibility
**Learning:** Table row selection checkboxes often lack accessible names. Adding dynamic `aria-label` (e.g., "Select {Name}") is essential for screen reader users to distinguish between rows.
**Action:** Ensure all selection checkboxes in data tables have unique, descriptive `aria-label` props derived from the row data.
## 2026-10-31 - Notification Bell Tooltip Implementation
**Learning:** The  library in this project relies on a `render={<Button />}` prop pattern for `TooltipTrigger` instead of Radix UI's `asChild`. Code review flagged `asChild` but this would be incorrect for this codebase.
**Action:** When adding `Tooltip` to icon-only buttons, use the `Tooltip, TooltipTrigger, TooltipContent, TooltipProvider` components and compose using the `render` prop to prevent rendering invalid nested buttons while avoiding breaking the interface.
## 2026-10-31 - Notification Bell Tooltip Implementation
**Learning:** The @base-ui/react library in this project relies on a render prop pattern for TooltipTrigger instead of Radix UIs asChild. Code review flagged asChild but this would be incorrect for this codebase.
**Action:** When adding Tooltip to icon-only buttons, use the Tooltip, TooltipTrigger, TooltipContent, TooltipProvider components and compose using the render prop to prevent rendering invalid nested buttons while avoiding breaking the interface.
