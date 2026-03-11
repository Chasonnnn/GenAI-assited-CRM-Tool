
## 2025-03-11 - [Dynamic ARIA Labels for List Actions]
**Learning:** Icon-only buttons in repeating lists (e.g., Delete/Duplicate for fields, columns, and options in form builders) often lack descriptive context, making them challenging for screen reader users to identify which specific item the action applies to. Using generic labels like "Delete" isn't sufficient.
**Action:** Always append dynamic contextual data (like `field.label`, `column.label`, or `option` text) to the `aria-label` of icon-only action buttons within lists. For example: `aria-label={\`Delete field ${field.label || field.id}\`}`.
