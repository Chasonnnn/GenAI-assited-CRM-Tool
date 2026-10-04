---
status: accepted
---

# Email templates use the React Email editor and keep HTML as the send artifact

Every email template editor (org and personal templates, the platform library, platform system templates, and the AI builder output) uses `@react-email/editor`, Resend's TipTap-based email editor. The editor document is stored as `body_design` JSON next to the existing `body` HTML. The browser compiles the document with React Email on save and stores the `<body>` fragment of the result in `body`. The server still sanitizes `body`, and the send, snapshot, campaign, and Resend paths keep reading only `body`.

`body_design` is an editing aid, never a send input. Any write that sets `body` without `body_design` (AI generation without a design, admin import, API clients, version restore of a version that has no design) clears `body_design`, so the editor never shows content that differs from what is sent.

Existing templates are not rewritten. A template with no `body_design` opens as one Custom HTML node that holds the stored `body`. When the document is still exactly that one node, saving writes the original HTML unchanged. "Convert to blocks" parses the HTML into editor nodes as a new draft, shows the original and converted renders side by side, and changes production only when the user publishes.

Preview calls a server endpoint that runs draft content through the real composition path (variable rendering, signature, unsubscribe footer), optionally with a real record's variables, and shows the result in a sandboxed iframe.

## Considered Options

- Compile on the server with a Python block renderer: rejected because it would duplicate React Email's table markup in a second renderer that must stay aligned with the editor preview.
- Build a custom block editor on React Email components: rejected after `@react-email/editor` was found to provide the inspector, slash commands, bubble menus, columns, buttons, and HTML/text serialization, and to import complex table HTML.
- Bulk-convert existing bodies in a data migration: rejected because conversion can change published emails without review.

## Constraints

- The editor pins TipTap 3.31.x. The app's TipTap packages and the bubble/floating menu overrides in `apps/web/pnpm-workspace.yaml` must stay on the same minor so only one `@tiptap/core` is installed.
- `@react-email/components` and the per-component packages are deprecated; import from `react-email` and `@react-email/editor`.
- React Email output is a full document. Only the `<body>` fragment is stored, because the sanitizer strips `<title>` but keeps its text.
- Version history payloads move to `schema_version` 2 with `body_design`. Restore accepts versions 1 and 2. A version 1 restore clears `body_design`.
