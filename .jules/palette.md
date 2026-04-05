## 2024-05-24 - Explicit Focus Indicators for Custom List Items
**Learning:** Custom `<button>` elements that act as list items or rows (like `ListItem` or `SurrogateTasksCalendar` tasks) often lack default focus indicators because utility classes for background hover don't automatically provide them, making keyboard navigation difficult.
**Action:** Always add explicit `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded` classes to interactive elements that don't use standard button components.
