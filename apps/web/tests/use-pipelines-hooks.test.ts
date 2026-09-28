import { beforeEach, describe, expect, it, vi } from "vitest"
import { useMutation, useQueryClient } from "@tanstack/react-query"

import {
    useApplyPipelineDraft,
    useCreatePipeline,
    useCreateStage,
    useDeletePipeline,
    useDeleteStage,
    useReorderStages,
    useRollbackPipeline,
    useUpdatePipeline,
    useUpdateStage,
} from "@/lib/hooks/use-pipelines"

vi.mock("@tanstack/react-query", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@tanstack/react-query")>()
    return { ...actual, useMutation: vi.fn(), useQueryClient: vi.fn() }
})

type MutationOptions = {
    onSuccess?: (response: unknown, variables: unknown) => void
}

const IP_STATUSES_KEY = ["metadata", "intended-parent-statuses"]

describe("pipeline mutation hooks", () => {
    let capturedOptions: MutationOptions | null = null
    const invalidateQueries = vi.fn()

    beforeEach(() => {
        capturedOptions = null
        invalidateQueries.mockReset()
        vi.mocked(useQueryClient).mockReturnValue({
            invalidateQueries,
        } as unknown as ReturnType<typeof useQueryClient>)
        vi.mocked(useMutation).mockImplementation((options: unknown) => {
            capturedOptions = options as MutationOptions
            return { mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useMutation>
        })
    })

    function invalidatedKeys() {
        return invalidateQueries.mock.calls.map(([filters]) => (filters as { queryKey: unknown }).queryKey)
    }

    it.each([
        ["apply draft", useApplyPipelineDraft, { id: "p1" }],
        ["rollback", useRollbackPipeline, { id: "p1", version: 2 }],
        ["update", useUpdatePipeline, { id: "p1", data: {} }],
        ["delete", useDeletePipeline, { id: "p1" }],
        ["create", useCreatePipeline, { name: "IP", entity_type: "intended_parent" }],
    ])("refreshes intended parent stage metadata after an intended parent pipeline %s", (_, hook, variables) => {
        hook()

        capturedOptions?.onSuccess?.({}, { entityType: "intended_parent", ...variables })

        expect(invalidatedKeys()).toContainEqual(IP_STATUSES_KEY)
    })

    it.each([
        ["apply draft", useApplyPipelineDraft, { id: "p1" }],
        ["rollback", useRollbackPipeline, { id: "p1", version: 2 }],
    ])("keeps intended parent stage metadata after a surrogate pipeline %s", (_, hook, variables) => {
        hook()

        capturedOptions?.onSuccess?.({}, { entityType: "surrogate", ...variables })

        expect(invalidatedKeys()).not.toContainEqual(IP_STATUSES_KEY)
    })

    it.each([
        ["create", useCreateStage, { pipelineId: "p1", data: {} }],
        ["update", useUpdateStage, { pipelineId: "p1", stageId: "s1", data: {} }],
        ["delete", useDeleteStage, { pipelineId: "p1", stageId: "s1", migrateToStageId: "s2" }],
        ["reorder", useReorderStages, { pipelineId: "p1", orderedStageIds: ["s1"] }],
    ])("refreshes intended parent stage metadata after a stage %s on any pipeline", (_, hook, variables) => {
        hook()

        capturedOptions?.onSuccess?.({}, variables)

        expect(invalidatedKeys()).toContainEqual(IP_STATUSES_KEY)
    })
})
