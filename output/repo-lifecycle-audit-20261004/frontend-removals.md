# Frontend cleanup evidence

Current callers and relevant history inspected before deletion. Repo root AGENTS.md and test-audit skill read. Existing CI runs the same frontend Vitest suites in four shards. Repo-specific scripts take precedence over test-audit's unavailable openclaw runner paths.

## Obsolete visual editor

- Production: components/email/email-template-visual-editor.tsx has no non-test callers. Commit baa2f26e7 migrated the organization/personal studio to EmailDesignEditor; all ops editors also use EmailDesignEditor.
- Test: tests/email-template-visual-editor.test.tsx, all six cases: "keeps the original source byte-for-byte until the user changes the body"; "preserves advanced appointment layout after a visual text edit"; "does not rewrite the source for a toolbar command that changes nothing"; "removes executable markup introduced after the editor mounts"; "sanitizes rich clipboard HTML before inserting it"; "does not mount executable markup in the visual authoring surface".
- Detectable failures: removed editor's mutation, execCommand, sanitation, and no-op preservation behavior.
- Retained proof: tests/email-design-editor.test.tsx owns live editor mount/no-change, editing, and conversion; tests/email-design.test.ts owns raw HTML/design preservation; current studio and ops page tests remain. Preview sanitizer tests remain.
- History: ddd39f5d5 added safe visual editing; replaced by baa2f26e7.
- Deletion: entire obsolete editor and its exclusive six tests; no public behavior removal.
- Risk: low, unreachable UI. Validate live editor, preview, studio, ops suites and type/lint checks.

## Test-only visual editor support predicates

- Production: lib/email-template-preview.ts EmailTemplateBodyMode, EmailTemplateVisualEditorSupport, hasAdvancedEmailTemplateHtml, getEmailTemplateVisualEditorSupport, getEmailTemplateBodyMode and private tables/predicate have no production callers.
- Tests: tests/email-template-preview.test.ts cases "routes supported advanced fragments to the visual editor"; "keeps safe external links available to the visual editor"; "keeps %s in source mode" for full email documents, unsupported elements, unsupported attributes, unsupported styles, embedded styles, conditional comments (eight cases total).
- Detectable failures: obsolete allowlist and old mode decision only.
- Retained proof: current EmailDesignEditor presents legacy HTML as a preserved HTML block and asks before conversion; its tests remain. Variable extraction and preview rendering/sanitation tests remain.
- History: ddd39f5d5/f6f226bbc added safe mode and external link support; no current callers after baa2f26e7.
- Deletion: predicates, types, attribute/style allowlists; no replacement seam needed.
- Risk: low; validate preview plus current editor/studio suites.

## Test-only plain-text adapter

- Production: lib/email-template-html.ts prepareTemplateHtmlForVisualEditor and private escapeTemplateText have no non-test callers.
- Tests: tests/email-template-html.test.ts describe prepareTemplateHtmlForVisualEditor: "preserves legacy plain-text blank lines as empty paragraphs"; "escapes plain-text markup instead of turning it into editor HTML"; "does not rewrite stored HTML merely by opening the editor".
- Detectable failures: dead adapter formatting only.
- Retained proof: normalizeTemplateHtml's four cases stay, as do live editor preservation cases. Legacy input now enters initialEmailDesign as an HTML block.
- History: 452ac2774 addressed template blank lines in former editor.
- Deletion: adapter plus three exclusive tests; normalization remains live in compose/preview.
- Risk: low; validate html, preview, current editor and studio suites.

## Retired donor header photo frontend

- Production: components/donors/DonorProfilePhoto.tsx has no callers after deliberate removal in 611eee06f. Component is sole caller of useUploadDonorProfilePhoto and useAttachmentPreviewUrl. Upload hook is sole caller of attachmentsApi.uploadDonorProfilePhoto.
- Tests: tests/donor-attachments-api.test.ts "uploads a donor profile photo through its dedicated image route"; tests/use-mutation-invalidations.test.ts "refreshes donor detail and attachment queries after donor attachment changes" only the useUploadDonorProfilePhoto table row.
- Detectable failures: dead frontend transport and hook invalidation only.
- Retained proof: all donor detail cases including four "omits header photo controls for $donorType donors with photo $photoId" UI cases remain. Remove only dead hook mock setup/assertions there. Donor attachment list/upload/delete tests stay; backend profile-photo route, storage, and tests unchanged.
- History: ca4798e40 introduced donor UI; 611eee06f deliberately removed the photo control.
- Deletion: component, sole-purpose upload/preview hooks, API adapter, two exclusive test cases, dead mock wiring, obsolete native-input allowlist entry.
- Risk: low, UI already removed; no storage/data/API deletion. Validate donor detail, donor attachments API, mutation invalidations, design-system primitive boundary.

Focused command: cd apps/web && mise exec -- pnpm test tests/email-template-preview.test.ts tests/email-template-html.test.ts tests/email-design.test.ts tests/email-design-editor.test.tsx tests/organization-email-template-studio.test.tsx tests/organization-email-template-studio-routes.test.tsx tests/email-templates-page.test.tsx tests/platform-email-template-page.test.tsx tests/platform-system-email-template-page.test.tsx tests/platform-system-email-template-new-page.test.tsx tests/donor-attachments-api.test.ts tests/donor-detail.test.tsx tests/use-mutation-invalidations.test.ts tests/design-system-primitives.test.ts
