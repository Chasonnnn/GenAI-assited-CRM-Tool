import { describe, expect, it } from "vitest"

import {
    createInitialWorkflowBuilderState,
    createWorkflowEditorHistory,
    workflowBuilderReducer,
    workflowEditorHistoryReducer,
    type WorkflowBuilderAction,
    type WorkflowEditorHistory,
} from "@/lib/workflows/workflow-editor-state"

function edit(history: WorkflowEditorHistory, action: WorkflowBuilderAction, at = 0) {
    return workflowEditorHistoryReducer(history, { type: "edit", action, at })
}

function withActions(...types: string[]) {
    let history = createWorkflowEditorHistory(createInitialWorkflowBuilderState("org"))
    types.forEach((actionType, index) => {
        history = edit(history, { type: "addAction", clientId: `a${index}`, action: { action_type: actionType } })
    })
    return history
}

const actionTypes = (history: WorkflowEditorHistory) => history.present.actions.map((action) => action.action_type)

describe("workflow builder actions", () => {
    it("inserts before the given index and clamps out-of-range positions", () => {
        const base = withActions("send_email", "create_task").present
        const inserted = workflowBuilderReducer(base, {
            type: "addAction",
            clientId: "new",
            action: { action_type: "add_note" },
            index: 1,
        })
        expect(inserted.actions.map((action) => action.action_type)).toEqual(["send_email", "add_note", "create_task"])

        const clamped = workflowBuilderReducer(base, { type: "addAction", clientId: "end", index: 99 })
        expect(clamped.actions.at(-1)?.clientId).toBe("end")
    })

    it("reorders to an absolute position and ignores invalid moves", () => {
        const base = withActions("send_email", "create_task", "add_note").present
        const moved = workflowBuilderReducer(base, { type: "reorderAction", from: 0, to: 2 })
        expect(moved.actions.map((action) => action.action_type)).toEqual(["create_task", "add_note", "send_email"])
        expect(workflowBuilderReducer(base, { type: "reorderAction", from: 1, to: 1 })).toBe(base)
        expect(workflowBuilderReducer(base, { type: "reorderAction", from: 0, to: 3 })).toBe(base)
    })
})

describe("workflow editor history", () => {
    it("undoes and redoes structural edits", () => {
        let history = withActions("send_email", "create_task")
        history = edit(history, { type: "removeAction", index: 0 })
        expect(actionTypes(history)).toEqual(["create_task"])

        history = workflowEditorHistoryReducer(history, { type: "undo" })
        expect(actionTypes(history)).toEqual(["send_email", "create_task"])

        history = workflowEditorHistoryReducer(history, { type: "redo" })
        expect(actionTypes(history)).toEqual(["create_task"])
    })

    it("merges rapid edits to one field into one undo step", () => {
        let history = createWorkflowEditorHistory(createInitialWorkflowBuilderState("org"))
        history = edit(history, { type: "setWorkflowName", value: "W" }, 1000)
        history = edit(history, { type: "setWorkflowName", value: "Wo" }, 1400)
        history = edit(history, { type: "setWorkflowName", value: "Wor" }, 1800)
        // A pause starts a new step.
        history = edit(history, { type: "setWorkflowName", value: "Word" }, 4000)

        expect(history.past).toHaveLength(2)
        history = workflowEditorHistoryReducer(history, { type: "undo" })
        expect(history.present.workflowName).toBe("Wor")
        history = workflowEditorHistoryReducer(history, { type: "undo" })
        expect(history.present.workflowName).toBe("")
    })

    it("starts a new step when a different field changes", () => {
        let history = createWorkflowEditorHistory(createInitialWorkflowBuilderState("org"))
        history = edit(history, { type: "setWorkflowName", value: "Name" }, 1000)
        history = edit(history, { type: "setWorkflowDescription", value: "About" }, 1100)
        expect(history.past).toHaveLength(2)
    })

    it("clears redo after a new edit", () => {
        let history = withActions("send_email")
        history = workflowEditorHistoryReducer(history, { type: "undo" })
        expect(history.future).toHaveLength(1)
        history = edit(history, { type: "setWorkflowName", value: "New" })
        expect(history.future).toHaveLength(0)
    })

    it("does not record errors, normalization, or no-op edits", () => {
        let history = withActions("send_email")
        const steps = history.past.length
        history = edit(history, { type: "setServerErrors", value: ["Bad"] })
        history = edit(history, { type: "setValidationError", value: "Bad" })
        history = edit(history, { type: "normalizeTriggerConfig", value: { cron: "" } })
        history = edit(history, { type: "reorderAction", from: 0, to: 0 })
        expect(history.past).toHaveLength(steps)
        expect(history.present.serverErrors).toEqual(["Bad"])
    })

    it("drops stale errors and keeps the loaded workflow id on undo", () => {
        let history = createWorkflowEditorHistory({
            ...createInitialWorkflowBuilderState("org"),
            hydratedWorkflowId: "wf-1",
        })
        history = edit(history, { type: "setWorkflowName", value: "A" })
        history = edit(history, { type: "setServerErrors", value: ["Name taken"] })
        history = workflowEditorHistoryReducer(history, { type: "undo" })
        expect(history.present.hydratedWorkflowId).toBe("wf-1")
        expect(history.present.serverErrors).toEqual([])
    })

    it("starts fresh history when a workflow loads", () => {
        let history = withActions("send_email", "create_task")
        history = edit(history, {
            type: "hydrateWorkflow",
            workflowId: "wf-2",
            statusOptions: [],
            workflow: {
                name: "Loaded",
                subject_type: "surrogate",
                scope: "org",
                trigger_type: "surrogate_created",
                trigger_config: {},
                conditions: [],
                condition_logic: "AND",
                actions: [{ action_type: "add_note", content: "Hi" }],
            },
        })
        expect(history.past).toHaveLength(0)
        expect(history.future).toHaveLength(0)
        expect(workflowEditorHistoryReducer(history, { type: "undo" })).toBe(history)
    })
})
