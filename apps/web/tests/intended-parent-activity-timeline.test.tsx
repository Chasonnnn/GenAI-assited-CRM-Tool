import { describe, expect, it } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import { IntendedParentActivityTimeline } from "@/components/intended-parents/IntendedParentActivityTimeline"
import type { Attachment } from "@/lib/api/attachments"
import type { PipelineStage } from "@/lib/api/pipelines"
import type { TaskListItem } from "@/lib/api/tasks"
import type { EntityNoteListItem, IntendedParentStatusHistoryItem } from "@/lib/types/intended-parent"

function makeStage(overrides: Partial<PipelineStage> = {}): PipelineStage {
    return {
        id: "stage-1",
        stage_key: "new",
        slug: "new",
        label: "New",
        color: "#3b82f6",
        order: 1,
        stage_type: "intake",
        is_active: true,
        ...overrides,
    }
}

function makeHistory(
    overrides: Partial<IntendedParentStatusHistoryItem> = {},
): IntendedParentStatusHistoryItem {
    return {
        id: "history-1",
        old_stage_id: null,
        new_stage_id: "stage-1",
        old_status: null,
        new_status: "new",
        reason: null,
        changed_by_user_id: null,
        changed_by_name: null,
        changed_at: "2024-01-01T00:00:00.000Z",
        effective_at: "2024-01-01T00:00:00.000Z",
        recorded_at: "2024-01-01T00:00:00.000Z",
        requested_at: null,
        approved_by_user_id: null,
        approved_by_name: null,
        approved_at: null,
        is_undo: false,
        request_id: null,
        ...overrides,
    }
}

function makeNote(overrides: Partial<EntityNoteListItem> = {}): EntityNoteListItem {
    return {
        id: "note-1",
        author_id: "user-1",
        content: "Stage note",
        created_at: "2024-01-02T00:00:00.000Z",
        ...overrides,
    }
}

function makeAttachment(overrides: Partial<Attachment> = {}): Attachment {
    return {
        id: "attachment-1",
        filename: "File.pdf",
        content_type: "application/pdf",
        file_size: 1024,
        scan_status: "clean",
        quarantined: false,
        uploaded_by_user_id: "user-1",
        created_at: "2024-01-02T00:00:00.000Z",
        ...overrides,
    }
}

function makeTask(overrides: Partial<TaskListItem> = {}): TaskListItem {
    return {
        id: "task-1",
        title: "Follow up",
        description: null,
        task_type: "follow_up",
        surrogate_id: null,
        intended_parent_id: "ip-1",
        surrogate_number: null,
        owner_type: "user",
        owner_id: "user-1",
        owner_name: "Owner",
        created_by_user_id: "user-1",
        created_by_name: "Owner",
        due_date: "2099-01-01",
        due_time: null,
        duration_minutes: null,
        is_completed: false,
        status: "pending",
        workflow_action_type: null,
        workflow_action_preview: null,
        due_at: null,
        completed_at: null,
        completed_by_name: null,
        created_at: "2024-01-01T00:00:00.000Z",
        ...overrides,
    }
}

function getStageButton(label: string): HTMLButtonElement {
    const button = screen.getByText(label).closest("button")
    expect(button).toBeTruthy()
    return button as HTMLButtonElement
}

describe("IntendedParentActivityTimeline", () => {
    const stages = [
        makeStage({ id: "stage-1", stage_key: "new", slug: "new", label: "New", order: 1 }),
        makeStage({
            id: "stage-2",
            stage_key: "review",
            slug: "review",
            label: "Active Review",
            order: 2,
        }),
        makeStage({
            id: "stage-3",
            stage_key: "approved",
            slug: "approved",
            label: "Approved",
            order: 3,
        }),
    ]

    const history = [
        makeHistory({
            id: "history-1",
            new_stage_id: "stage-1",
            new_status: "new",
            changed_at: "2024-01-04T00:00:00.000Z",
            effective_at: "2024-01-01T00:00:00.000Z",
            recorded_at: "2024-01-04T00:00:00.000Z",
        }),
        makeHistory({
            id: "history-2",
            old_stage_id: "stage-1",
            new_stage_id: "stage-2",
            old_status: "new",
            new_status: "review",
            changed_at: "2024-02-01T00:00:00.000Z",
            effective_at: "2024-02-01T00:00:00.000Z",
            recorded_at: "2024-02-01T00:00:00.000Z",
        }),
        makeHistory({
            id: "history-3",
            old_stage_id: "stage-2",
            new_stage_id: "stage-3",
            old_status: "review",
            new_status: "approved",
            changed_at: "2024-03-01T00:00:00.000Z",
            effective_at: "2024-03-01T00:00:00.000Z",
            recorded_at: "2024-03-01T00:00:00.000Z",
        }),
    ]

    const notes = [
        makeNote({
            id: "note-1",
            content: "Backdated stage note",
            created_at: "2024-01-02T00:00:00.000Z",
        }),
        makeNote({
            id: "note-2",
            content: "Current stage note",
            created_at: "2024-02-02T00:00:00.000Z",
        }),
        makeNote({
            id: "note-3",
            content: "Next stage note",
            created_at: "2024-03-02T00:00:00.000Z",
        }),
    ]

    it("shows only the current stage details by default", () => {
        render(
            <IntendedParentActivityTimeline
                currentStageId="stage-2"
                stages={stages}
                history={history}
                notes={notes}
                attachments={[]}
                tasks={[]}
            />,
        )

        expect(screen.getByText("Current stage note")).toBeInTheDocument()
        expect(screen.queryByText("Backdated stage note")).not.toBeInTheDocument()
        expect(screen.queryByText("Next stage note")).not.toBeInTheDocument()
    })

    it("keeps collapse-all as a valid user state and only opens the clicked stage afterward", async () => {
        render(
            <IntendedParentActivityTimeline
                currentStageId="stage-2"
                stages={stages}
                history={history}
                notes={notes}
                attachments={[]}
                tasks={[]}
            />,
        )

        fireEvent.click(getStageButton("Active Review"))

        await waitFor(() => {
            expect(screen.queryByText("Current stage note")).not.toBeInTheDocument()
            expect(screen.queryByText("Backdated stage note")).not.toBeInTheDocument()
        })

        fireEvent.click(getStageButton("New"))

        await waitFor(() => {
            expect(screen.getByText("Backdated stage note")).toBeInTheDocument()
            expect(screen.queryByText("Current stage note")).not.toBeInTheDocument()
            expect(screen.queryByText("Next stage note")).not.toBeInTheDocument()
        })
    })

    it("resets the default open stage when currentStageId changes while mounted", async () => {
        const { rerender } = render(
            <IntendedParentActivityTimeline
                currentStageId="stage-2"
                stages={stages}
                history={history}
                notes={notes}
                attachments={[]}
                tasks={[]}
            />,
        )

        fireEvent.click(getStageButton("Active Review"))
        fireEvent.click(getStageButton("New"))

        await waitFor(() => {
            expect(screen.getByText("Backdated stage note")).toBeInTheDocument()
            expect(screen.queryByText("Current stage note")).not.toBeInTheDocument()
        })

        rerender(
            <IntendedParentActivityTimeline
                currentStageId="stage-3"
                stages={stages}
                history={history}
                notes={notes}
                attachments={[]}
                tasks={[]}
            />,
        )

        await waitFor(() => {
            expect(screen.getByText("Next stage note")).toBeInTheDocument()
            expect(screen.queryByText("Backdated stage note")).not.toBeInTheDocument()
            expect(screen.queryByText("Current stage note")).not.toBeInTheDocument()
        })
    })

    it("defaults to all stages collapsed when the current stage is missing", () => {
        render(
            <IntendedParentActivityTimeline
                currentStageId="missing-stage"
                stages={stages}
                history={history}
                notes={notes}
                attachments={[makeAttachment()]}
                tasks={[makeTask()]}
            />,
        )

        expect(screen.queryByText("Backdated stage note")).not.toBeInTheDocument()
        expect(screen.queryByText("Current stage note")).not.toBeInTheDocument()
        expect(screen.queryByText("Next stage note")).not.toBeInTheDocument()
        expect(screen.getByText("Next Steps")).toBeInTheDocument()
    })

    it("keeps stage headers aligned even when only some stages show expanded details", () => {
        render(
            <IntendedParentActivityTimeline
                currentStageId="stage-2"
                stages={[
                    makeStage({ id: "stage-1", stage_key: "new", slug: "new", label: "New", order: 1 }),
                    makeStage({
                        id: "stage-2",
                        stage_key: "ready_to_match",
                        slug: "ready_to_match",
                        label: "Ready to Match",
                        order: 2,
                    }),
                    makeStage({
                        id: "stage-3",
                        stage_key: "delivered",
                        slug: "delivered",
                        label: "Delivered",
                        order: 3,
                    }),
                ]}
                history={[
                    makeHistory({
                        id: "history-1",
                        new_stage_id: "stage-1",
                        new_status: "new",
                        changed_at: "2024-01-01T00:00:00.000Z",
                        effective_at: "2024-01-01T00:00:00.000Z",
                        recorded_at: "2024-01-01T00:00:00.000Z",
                    }),
                    makeHistory({
                        id: "history-2",
                        old_stage_id: "stage-1",
                        new_stage_id: "stage-2",
                        old_status: "new",
                        new_status: "ready_to_match",
                        changed_at: "2024-02-01T00:00:00.000Z",
                        effective_at: "2024-02-01T00:00:00.000Z",
                        recorded_at: "2024-02-01T00:00:00.000Z",
                    }),
                ]}
                notes={[
                    makeNote({
                        id: "note-2",
                        content: "Current stage note",
                        created_at: "2024-02-02T00:00:00.000Z",
                    }),
                ]}
                attachments={[]}
                tasks={[]}
            />,
        )

        expect(screen.getByTestId("timeline-stage-row-stage-2")).toHaveClass(
            "grid-cols-[1rem_0.625rem_minmax(0,1fr)_minmax(6.5rem,max-content)]",
        )
        expect(screen.getByTestId("timeline-stage-row-stage-3")).toHaveClass(
            "grid-cols-[1rem_0.625rem_minmax(0,1fr)_minmax(6.5rem,max-content)]",
        )
        expect(screen.getByTestId("timeline-stage-meta-stage-2")).toHaveClass("justify-self-end", "text-right")
        expect(screen.getByTestId("timeline-stage-meta-stage-3")).toHaveClass("justify-self-end", "text-right")
    })
})
