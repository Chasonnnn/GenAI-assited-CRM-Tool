import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { EntityActivityHistory } from "@/components/activity/EntityActivityHistory"
import {
    ActivityEventRow,
    EntityActivityTimeline,
} from "@/components/activity/EntityActivityTimeline"
import type { PipelineStage } from "@/lib/api/pipelines"
import type { SurrogateActivity, SurrogateStatusHistory } from "@/lib/api/surrogates"

const mockUseInfiniteEntityActivity = vi.hoisted(() => vi.fn())

vi.mock("@/lib/hooks/use-entity-activity", () => ({
    useInfiniteEntityActivity: mockUseInfiniteEntityActivity,
}))

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
}))

const stage: PipelineStage = {
    id: "stage-1",
    stage_key: "screening",
    slug: "screening",
    label: "Screening",
    color: "#3b82f6",
    stage_type: "intake",
    order: 1,
    is_active: true,
}

const history: SurrogateStatusHistory = {
    id: "history-1",
    from_stage_id: null,
    to_stage_id: stage.id,
    from_label_snapshot: null,
    to_label_snapshot: stage.label,
    changed_by_user_id: "user-1",
    changed_by_name: "Morgan Lee",
    reason: "Application reviewed",
    changed_at: "2026-08-29T12:00:00Z",
    effective_at: "2026-08-29T12:00:00Z",
    recorded_at: "2026-08-29T12:00:00Z",
}

function activity(
    activityType: string,
    details: Record<string, unknown> | null,
): SurrogateActivity {
    return {
        id: `activity-${activityType}`,
        activity_type: activityType,
        actor_user_id: "user-1",
        actor_name: "Morgan Lee",
        details,
        created_at: "2026-08-30T12:00:00Z",
    }
}

describe("EntityActivityTimeline", () => {
    it("renders explicit loading and retryable error states", () => {
        const retry = vi.fn()
        const { rerender } = render(
            <EntityActivityTimeline
                currentStageId={stage.id}
                stages={[stage]}
                stageHistory={[]}
                status="loading"
            />,
        )
        expect(screen.getByRole("status")).toHaveTextContent("Loading activity")

        rerender(
            <EntityActivityTimeline
                currentStageId={stage.id}
                stages={[stage]}
                stageHistory={[]}
                status="error"
                onRetry={retry}
            />,
        )
        expect(screen.getByText("Failed to load activity.")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(retry).toHaveBeenCalledOnce()
    })

    it("preserves stage reasons and links to the complete history", () => {
        render(
            <EntityActivityTimeline
                currentStageId={stage.id}
                stages={[stage]}
                stageHistory={[history]}
                historyHref="/donors/donor-1/history"
            />,
        )

        expect(screen.getByText("Application reviewed")).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "View full history →" })).toHaveAttribute(
            "href",
            "/donors/donor-1/history",
        )
    })

    it("keeps activity usable while next steps fail independently", () => {
        const retryTasks = vi.fn()
        render(
            <EntityActivityTimeline
                currentStageId={stage.id}
                stages={[stage]}
                stageHistory={[history]}
                activities={[activity("note_added", { preview: "Visible activity" })]}
                tasksStatus="error"
                onRetryTasks={retryTasks}
            />,
        )

        expect(screen.getByText("Visible activity")).toBeInTheDocument()
        expect(screen.getByRole("alert")).toHaveTextContent("Failed to load next steps.")
        fireEvent.click(screen.getByRole("button", { name: "Retry next steps" }))
        expect(retryTasks).toHaveBeenCalledOnce()
    })
})

describe("ActivityEventRow", () => {
    it.each([
        ["record_created", null, "Record created", null],
        ["note_added", { preview: "Screening call completed" }, "Note", "Screening call completed"],
        ["attachment_added", { filename: "screening.pdf" }, "File uploaded", "screening.pdf"],
        ["task_completed", { title: "Review records" }, "Task completed", "Review records"],
        [
            "status_changed",
            { from: "New", to: "Screening", reason: "Application reviewed" },
            "Stage changed",
            "New → Screening • Application reviewed",
        ],
    ])("renders %s activity with its safe preview", (type, details, title, preview) => {
        render(<ActivityEventRow activity={activity(type, details)} />)
        expect(screen.getByText(title)).toBeInTheDocument()
        if (preview) expect(screen.getByText(preview)).toBeInTheDocument()
        expect(screen.getByText(/Morgan Lee/)).toBeInTheDocument()
    })
})

describe("EntityActivityHistory", () => {
    beforeEach(() => {
        mockUseInfiniteEntityActivity.mockReset()
    })

    it("shows a retryable error when the history request fails", () => {
        const refetch = vi.fn()
        mockUseInfiniteEntityActivity.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            refetch,
            hasNextPage: false,
            isFetchingNextPage: false,
            fetchNextPage: vi.fn(),
        })

        render(
            <EntityActivityHistory
                entityType="donor"
                entityId="donor-1"
                backHref="/donors/donor-1"
            />,
        )

        expect(screen.getByText("Failed to load activity.")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(refetch).toHaveBeenCalledOnce()
    })

    it("loads another page and hides the control after the terminal page", () => {
        const fetchNextPage = vi.fn()
        const firstActivity = activity("record_created", null)
        const secondActivity = activity("task_completed", { title: "Review records" })
        mockUseInfiniteEntityActivity.mockReturnValue({
            data: {
                pages: [{ items: [firstActivity], total: 2, page: 1, pages: 2 }],
            },
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
            hasNextPage: true,
            isFetchingNextPage: false,
            fetchNextPage,
        })

        const view = render(
            <EntityActivityHistory
                entityType="intended_parent"
                entityId="ip-1"
                backHref="/intended-parents/ip-1"
            />,
        )
        expect(screen.getByText("Record created")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Load more" }))
        expect(fetchNextPage).toHaveBeenCalledOnce()

        mockUseInfiniteEntityActivity.mockReturnValue({
            data: {
                pages: [
                    { items: [firstActivity], total: 2, page: 1, pages: 2 },
                    { items: [secondActivity], total: 2, page: 2, pages: 2 },
                ],
            },
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
            hasNextPage: false,
            isFetchingNextPage: false,
            fetchNextPage,
        })
        view.rerender(
            <EntityActivityHistory
                entityType="intended_parent"
                entityId="ip-1"
                backHref="/intended-parents/ip-1"
            />,
        )

        expect(screen.getByText("Review records")).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument()
    })
})
