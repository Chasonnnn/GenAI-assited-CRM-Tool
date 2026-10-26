## 2026-10-26 - NotificationBell Tooltip Trigger render Prop

**Learning:** Automated code review feedback sometimes incorrectly assumes the project is using Radix UI and suggests using the `asChild` prop for component composition. However, as explicitly noted in memory, the frontend (`apps/web`) uses `@base-ui/react` for its primitive components. For component composition (to avoid invalid nested buttons), you must use Base UI's `render` prop (e.g., `<TooltipTrigger render={<Button />} />`) rather than the `asChild` prop. The code review failure regarding the `render` prop is a false positive due to the reviewer's incorrect assumption about the underlying UI library.

**Action:** When adding tooltips to buttons in this codebase, continue to use the `@base-ui/react` `render` prop (e.g., `<TooltipTrigger render={<Button ... />} />`) as instructed by memory, and safely ignore automated code review feedback that incorrectly assumes Radix UI and suggests `asChild`.
