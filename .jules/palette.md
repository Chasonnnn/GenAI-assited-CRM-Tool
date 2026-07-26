## 2024-07-26 - Added aria-hidden to decorative icons inside interactive elements
**Learning:** Decorative icons placed inside interactive elements like `<Button>` that already contain visible text must include `aria-hidden="true"` to prevent redundant screen reader announcements.
**Action:** When adding or fixing buttons with text and icons, ensure the icon has `aria-hidden="true"`.
