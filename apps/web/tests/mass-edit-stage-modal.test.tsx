import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import { MassEditStageModal } from "@/components/surrogates/MassEditStageModal"
import type { PipelineStage } from "@/lib/api/pipelines"
import type { SurrogateMassEditStageFilters } from "@/lib/api/surrogates"

const mockPreviewMutateAsync = vi.fn()
const mockApplyStageMutateAsync = vi.fn()
const mockApplyArchiveMutateAsync = vi.fn()

vi.mock("sonner", () => ({
    toast: {
        error: vi.fn(),
        info: vi.fn(),
        success: vi.fn(),
    },
}))

vi.mock("@/lib/hooks/use-surrogates", () => ({
    usePreviewSurrogateMassEditStage: () => ({
        mutateAsync: mockPreviewMutateAsync,
        isPending: false,
    }),
    useApplySurrogateMassEditStage: () => ({
        mutateAsync: mockApplyStageMutateAsync,
        isPending: false,
    }),
    useApplySurrogateMassEditArchive: () => ({
        mutateAsync: mockApplyArchiveMutateAsync,
        isPending: false,
    }),
    useSurrogateMassEditOptions: () => ({
        data: { races: ["white", "asian"] },
        isPending: false,
        isError: false,
    }),
}))

const STAGES: PipelineStage[] = [
    {
        id: "stage-disqualified",
        slug: "disqualified",
        label: "Disqualified",
        color: "#ef4444",
        order: 1,
        stage_type: "terminal",
        is_active: true,
    },
]

function renderModal(baseFilters: SurrogateMassEditStageFilters = {}) {
    render(
        <MassEditStageModal
            open
            onOpenChange={vi.fn()}
            stages={STAGES}
            baseFilters={baseFilters}
        />
    )
}

describe("MassEditStageModal", () => {
    beforeEach(() => {
        mockPreviewMutateAsync.mockReset()
        mockApplyStageMutateAsync.mockReset()
        mockApplyArchiveMutateAsync.mockReset()
        mockPreviewMutateAsync.mockResolvedValue({
            total: 1,
            over_limit: false,
            max_apply: 2000,
            items: [],
        })
        mockApplyArchiveMutateAsync.mockResolvedValue({
            matched: 1,
            archived: 1,
            failed: [],
        })
    })

    it("renders created date inputs and explicit filter logic copy", () => {
        renderModal()

        expect(screen.getByLabelText("Created From")).toBeInTheDocument()
        expect(screen.getByLabelText("Created To")).toBeInTheDocument()
        expect(screen.getByText("Filter Logic")).toBeInTheDocument()
        expect(screen.getByText(/Different filter groups combine with/i)).toBeInTheDocument()
        expect(screen.getByText(/Multiple values in one field/i)).toBeInTheDocument()
        expect(screen.getByText(/Search matches name, email, phone, or surrogate number/i)).toBeInTheDocument()
    })

    it("renders friendly labels for tri-state filter triggers", () => {
        renderModal()

        expect(screen.getAllByText("Any")).toHaveLength(4)
        expect(screen.queryByText("any")).not.toBeInTheDocument()
    })

    it("sends modal created date filters in preview request and shows override badge", async () => {
        renderModal({
            created_from: "2025-01-01",
            created_to: "2025-01-31",
        })

        fireEvent.change(screen.getByLabelText("Created From"), {
            target: { value: "2025-02-01" },
        })
        fireEvent.change(screen.getByLabelText("Created To"), {
            target: { value: "2025-02-10" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Preview Matches" }))

        await waitFor(() => expect(mockPreviewMutateAsync).toHaveBeenCalledTimes(1))
        expect(mockPreviewMutateAsync).toHaveBeenCalledWith({
            data: {
                filters: expect.objectContaining({
                    created_from: "2025-02-01",
                    created_to: "2025-02-10",
                }),
            },
            limit: 25,
        })

        expect(screen.getByText("Created: modal override")).toBeInTheDocument()
    })

    it("uses modal created date override semantics when only one modal bound is set", async () => {
        renderModal({
            created_from: "2025-01-01",
            created_to: "2025-01-31",
        })

        fireEvent.change(screen.getByLabelText("Created From"), {
            target: { value: "2025-02-01" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Preview Matches" }))

        await waitFor(() => expect(mockPreviewMutateAsync).toHaveBeenCalledTimes(1))
        const sentFilters = mockPreviewMutateAsync.mock.calls[0][0].data.filters as Record<string, unknown>
        expect(sentFilters.created_from).toBe("2025-02-01")
        expect(sentFilters).not.toHaveProperty("created_to")
    })

    it("renders preview created dates with a deterministic UTC date label", async () => {
        mockPreviewMutateAsync.mockResolvedValueOnce({
            total: 1,
            over_limit: false,
            max_apply: 2000,
            items: [
                {
                    id: "surrogate-1",
                    surrogate_number: "S10001",
                    full_name: "Alex Chen",
                    status_label: "New",
                    state: "CA",
                    age: 31,
                    created_at: "2025-01-02T23:30:00Z",
                },
            ],
        })

        renderModal()

        fireEvent.click(screen.getByRole("button", { name: "Preview Matches" }))

        expect(await screen.findByText("Jan 2, 2025")).toBeInTheDocument()
    })

    it("applies archive action when archive mode is selected", async () => {
        renderModal()

        fireEvent.click(screen.getByRole("button", { name: "Archive" }))
        fireEvent.click(screen.getByRole("button", { name: "Preview Matches" }))
        await waitFor(() => expect(mockPreviewMutateAsync).toHaveBeenCalledTimes(1))

        fireEvent.click(screen.getByRole("button", { name: "Apply Archive" }))
        await waitFor(() => expect(mockApplyArchiveMutateAsync).toHaveBeenCalledTimes(1))

        expect(mockApplyArchiveMutateAsync).toHaveBeenCalledWith({
            filters: expect.any(Object),
            expected_total: 1,
        })
    })
})
