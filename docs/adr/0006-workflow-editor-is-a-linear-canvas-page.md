---
status: accepted
---

# The workflow editor is a full-page linear canvas

Workflows are created and edited at `/automation/workflows/[id]` (`new` creates; `?scope=org|personal` picks the scope for a new workflow). The page has three columns: a contextual inspector on the left (trigger kind and type, record type, schedule presets for scheduled triggers, filters, and description; or the selected action step), a vertical node canvas in the middle (a trigger node whose enrollment criteria summarize the trigger config and filters, one node per action, an add-action slot, an exit marker), and an action palette on the right with Agents and Actions groups. Filters are the workflow's conditions; they are edited in the left panel, not as a canvas node. Schedule presets write the same simple cron the scheduler accepts; any other cron stays editable as a custom cron. Below the `lg` breakpoint the inspector and palette open as sheets. The list page's Create and Edit actions navigate to this route; `/automation?create=true` redirects to it. A new workflow can be saved as a draft (disabled) or launched (enabled); editing never changes the enabled flag.

The canvas renders the existing linear model only: one trigger, flat AND/OR conditions, an ordered action list. It is a projection of `AutomationWorkflow`, not a graph document. Editor state and validation live in `apps/web/lib/workflows/workflow-editor-state.ts` (pure) and `use-workflow-editor.ts` (controller); the list page no longer owns any editor state.

## Considered Options

- Keep the four-step wizard in a dialog and restyle it: rejected. The reference design the user chose is a canvas with side panels, which does not fit a dialog, and the list page had grown to 3,250 lines with the wizard inside it.
- Add true/false and multi-split branches, delay, and exit nodes to match the reference exactly: deferred. The engine evaluates one condition set and runs actions in order; branches need a new workflow schema version, engine and execution-history changes, and a migration. Revisit as its own project with its own ADR.
- Use a graph library (React Flow) for the canvas: rejected for now. A linear flow needs no free-form positioning; CSS layout with simple connectors renders it, keeps the bundle unchanged, and stays keyboard accessible. A library earns its place only if branching lands.
