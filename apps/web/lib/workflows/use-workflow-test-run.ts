"use client"

import { useState } from "react"

import { ApiError } from "@/lib/api"
import type { WorkflowTestResponse } from "@/lib/api/workflows"
import { isPermissionError } from "@/lib/error-utils"
import { useTestWorkflowDraft, useWorkflowOptions } from "@/lib/hooks/use-workflows"
import type { WorkflowEditorController } from "@/lib/workflows/use-workflow-editor"
import { getTestEntityType, type TestEntitySuggestion } from "@/lib/workflows/test-entities"

/** What a dry run says about one step, in the order the engine would reach it. */
export type TestRunStepState = "would_run" | "needs_approval" | "after_approval" | "skipped"

export const TEST_RUN_STEP_LABELS: Record<TestRunStepState, string> = {
    would_run: "Would run",
    needs_approval: "Waits for approval",
    after_approval: "After approval",
    skipped: "Skipped",
}

/** Execution pauses at the first step that needs approval; filters that fail skip every step. */
export function getTestRunStepStates(result: WorkflowTestResponse): TestRunStepState[] {
    if (!result.conditions_matched) return result.actions_preview.map(() => "skipped")
    let paused = false
    return result.actions_preview.map((step) => {
        if (paused) return "after_approval"
        if (step.requires_approval) {
            paused = true
            return "needs_approval"
        }
        return "would_run"
    })
}

export function getTestRunErrorMessage(error: unknown): string {
    if (isPermissionError(error)) return "You don't have access to test this workflow on that record."
    if (error instanceof ApiError) {
        if (error.status === 404) return "That record is no longer available."
        if (error.status >= 500) return "Couldn't run the test. Try again."
        if (error.message) return error.message
    }
    return "Couldn't run the test. Try again."
}

type TestRun = {
    record: TestEntitySuggestion
    result: WorkflowTestResponse
    /** The definition that was tested, to tell when the canvas has changed since. */
    definitionKey: string
}

export type WorkflowTestRunController = ReturnType<typeof useWorkflowTestRun>

export function useWorkflowTestRun(controller: WorkflowEditorController) {
    const { state, workflowId, buildWorkflowPayload } = controller
    const mutation = useTestWorkflowDraft()
    const [run, setRun] = useState<TestRun | null>(null)
    const [pendingRecord, setPendingRecord] = useState<TestEntitySuggestion | null>(null)

    const { data: options } = useWorkflowOptions(state.workflowScope, state.subjectType)
    const entityType = getTestEntityType(state.subjectType, state.triggerType, options?.trigger_entity_types)

    // Enabled state and is_enabled do not change what a dry run evaluates.
    const definitionKey = JSON.stringify(buildWorkflowPayload({ isEnabled: false }))
    const isStale = run !== null && run.definitionKey !== definitionKey

    const start = (record: TestEntitySuggestion) => {
        setPendingRecord(record)
        const payload = buildWorkflowPayload({ isEnabled: false })
        mutation.mutate(
            {
                workflow: payload,
                entity_id: record.id,
                entity_type: entityType,
                ...(workflowId ? { workflow_id: workflowId } : {}),
            },
            {
                onSuccess: (result) => setRun({ record, result, definitionKey: JSON.stringify(payload) }),
                onSettled: () => setPendingRecord(null),
            },
        )
    }

    const clear = () => {
        setRun(null)
        mutation.reset()
    }

    return {
        entityType,
        run,
        stepStates: run ? getTestRunStepStates(run.result) : null,
        isStale,
        isPending: mutation.isPending,
        pendingRecord,
        error: mutation.error ? getTestRunErrorMessage(mutation.error) : null,
        start,
        rerun: () => run && start(run.record),
        clear,
    }
}
