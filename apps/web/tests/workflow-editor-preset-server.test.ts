import { describe, expect, it, vi } from "vitest"

// A Server Component sees exports of a "use client" module as opaque client references.
vi.mock("@/components/automation/workflow-editor/shared", async (importOriginal) => {
    const actual = await importOriginal<Record<string, unknown>>()
    return Object.fromEntries(Object.keys(actual).map((name) => [name, Object.freeze(() => {})]))
})

describe("getWorkflowEditorPreset in a Server Component", () => {
    it("builds form and appointment presets without values from the client editor module", async () => {
        const { getWorkflowEditorPreset } = await import("@/lib/workflows/workflow-editor-state")

        expect(getWorkflowEditorPreset({ trigger: "form_submission_rejected", form_id: "form-1" })).toEqual({
            triggerType: "form_submission_rejected",
            triggerConfig: { form_id: "form-1" },
        })
        expect(getWorkflowEditorPreset({ trigger: "form_submitted" })).toEqual({
            triggerType: "form_submitted",
            triggerConfig: { form_id: "" },
        })
        expect(
            getWorkflowEditorPreset({ trigger: "appointment_scheduled", appointment_type: "Initial Consultation" }),
        ).toEqual({
            triggerType: "appointment_scheduled",
            triggerConfig: { appointment_type_names: ["Initial Consultation"] },
        })
        expect(getWorkflowEditorPreset({ trigger: "surrogate_created" })).toBeNull()
    })
})
