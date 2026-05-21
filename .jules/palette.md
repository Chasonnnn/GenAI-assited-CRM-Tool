## 2024-05-24 - Calendar Navigation Accessibility
**Learning:** Icon-only navigation buttons in custom calendar components often lack accessible names, making them invisible to screen readers. The header text that updates when navigation occurs is also not announced automatically.
**Action:** Always add descriptive `aria-label`s to icon-only navigation controls (like ChevronLeft/Right), hide their inner SVGs with `aria-hidden="true"`, and add `aria-live="polite"` to the dynamic text element (like the month/year header) so screen readers announce the state change when the user navigates.
