# Permission Studio design QA

final result: passed

Reference: [approved option 1](docs/mockups/permissions/2026-09-12-module-first-studio.png). Implementation: [desktop capture](docs/verification/permissions-2026-09-12/desktop-donors.png), September 12, 2026.

Browser evidence comes from the original main-based implementation run. The stacked PR branch received separate automated validation recorded in the linked report.

The source and implementation were opened together in one comparison input at 1499 × 1049. Both show Case Manager, Donors, all-record post-approval scope, View/Edit/Change status enabled, Create/Archive/Approve/Assign disabled, and unsaved changes. Application chrome remains the existing product shell; comparison centers on the permission workspace. The implementation capture is vertically scrolled to align the workspace with the reference.

## Findings and resolution

| Priority | Finding | Resolution |
|---|---|---|
| P2, resolved | Alphabetical groups placed progress before records; actions began with Archive | Records now precede progress and notes. Record actions follow View, Create, Edit, Archive, Delete, Import |
| P2, resolved | Preview repeated ambiguous View/Edit labels across records and notes | Preview uses View notes and Edit notes; switches retain short labels |
| P2, resolved | Legacy surrogate post-approval permission duplicated the version 2 phase control | Removed from version 2 catalogs; version 1 and migration review retain compatibility |
| P3, accepted | Existing product font, smaller switches, global navigation, and shared button styling differ from the raster mockup | Existing customized components and application shell retained |
| P3, accepted | Operations children are collapsed outside Operations | Reduces navigation clutter; children appear on selection |

No unresolved P0, P1, or P2 findings remain. The final comparison was made after the listed fixes. At full capture resolution, labels, switches, and layout were readable without a separate detail crop.

## Fidelity surfaces

| Surface | Result |
|---|---|
| Typography | Clear title, module, section, and action hierarchy; existing product font and weights retained. No visible label clipping in the workspace |
| Layout | Role strip, module navigation, scope/actions column, and preview match the reference structure. Specific stages remain available in a collapsed control |
| Colors | Ivory canvas, plum selected role, pink selections, and pale preview follow the source palette. Dark mode uses existing semantic tokens |
| Assets | Existing supplied product branding and icon-library components retained; no new raster asset or handcrafted illustration required |
| Content | Five primary topics, separate Create/Edit, short actions, protected roles, and included-default preview match the accepted model. Actual organization AI availability drives the preview |

## Interaction and responsive evidence

Role changes were reviewed, applied, and confirmed after reload. Operations subtopics, protected-role controls, individual additions, denied access, and reviewed activation were exercised in the browser. The 390 × 844 viewport has no document horizontal overflow; its role strip scrolls and review dialog remains usable. The observed content width is 375 CSS pixels after the scrollbar. Dark-mode contrast was inspected.

[Mobile layout](docs/verification/permissions-2026-09-12/mobile-top.png) · [Mobile review](docs/verification/permissions-2026-09-12/mobile-review.png) · [Dark theme](docs/verification/permissions-2026-09-12/dark-donors.png) · [Behavior and test evidence](docs/permission-upgrade-verification.md).
