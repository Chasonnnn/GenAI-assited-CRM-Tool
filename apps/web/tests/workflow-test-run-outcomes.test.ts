import { describe, expect, it } from "vitest"

import { stepOutcome } from "@/components/automation/workflow-editor/workflow-step-history"
import type { WorkflowExecution, WorkflowTestResponse } from "@/lib/api/workflows"
import { getTestRunStepStates } from "@/lib/workflows/use-workflow-test-run"

function dryRun(conditionsMatched: boolean, approvals: boolean[]): WorkflowTestResponse {
    return {
        would_trigger: conditionsMatched,
        conditions_matched: conditionsMatched,
        conditions_evaluated: [],
        actions_preview: approvals.map((requiresApproval) => ({
            action_type: "add_note",
            description: "Add note",
            requires_approval: requiresApproval,
        })),
    }
}

function execution(overrides: Partial<WorkflowExecution>): WorkflowExecution {
    return {
        id: "run-1",
        workflow_id: "workflow-1",
        event_id: "event-1",
        depth: 0,
        event_source: "user",
        entity_type: "surrogate",
        entity_id: "surrogate-1",
        subject_type: "surrogate",
        subject_id: "surrogate-1",
        entity_name: null,
        entity_number: null,
        trigger_event: {},
        matched_conditions: true,
        actions_executed: [],
        status: "success",
        error_message: null,
        duration_ms: null,
        executed_at: "2026-10-01T12:00:00Z",
        ...overrides,
    }
}

describe("getTestRunStepStates", () => {
    it("skips every step when the filters do not match", () => {
        expect(getTestRunStepStates(dryRun(false, [false, true]))).toEqual(["skipped", "skipped"])
    })

    it("pauses at the first step that needs approval", () => {
        expect(getTestRunStepStates(dryRun(true, [false, true, false, true]))).toEqual([
            "would_run",
            "needs_approval",
            "after_approval",
            "after_approval",
        ])
    })
})

describe("stepOutcome", () => {
    const ran = { success: true, action_type: "add_note" }

    it("reports unmatched filters for every step", () => {
        expect(stepOutcome(execution({ matched_conditions: false }), 0, "add_note").label).toBe("Filters not matched")
    })

    it("reports ran, failed, and skipped steps with their errors", () => {
        const run = execution({
            status: "partial",
            actions_executed: [
                ran,
                { success: false, action_type: "add_note", error: "Body empty" },
                { success: false, action_type: "add_note", skipped: true, error: "No recipient" },
            ],
        })
        expect(stepOutcome(run, 0, "add_note")).toEqual({ label: "Ran", tone: "good" })
        expect(stepOutcome(run, 1, "add_note")).toEqual({ label: "Failed", tone: "bad", detail: "Body empty" })
        expect(stepOutcome(run, 2, "add_note")).toEqual({ label: "Skipped", tone: "muted", detail: "No recipient" })
    })

    it("marks the step a paused run waits on and the steps after it", () => {
        const run = execution({ status: "paused", actions_executed: [ran] })
        expect(stepOutcome(run, 1, "send_email").label).toBe("Waiting for approval")
        expect(stepOutcome(run, 2, "add_note").label).toBe("Not reached")
    })

    it("flags runs where a different step held this position", () => {
        expect(stepOutcome(execution({ actions_executed: [ran] }), 0, "send_email").label).toBe(
            "Different step at the time",
        )
    })
})
