import { beforeEach, describe, expect, it, vi } from "vitest"
import { useMutation, useQueryClient } from "@tanstack/react-query"

import {
    contactAttemptKeys,
    surrogateKeys,
    useApplySurrogateMassEditArchive,
    useApplySurrogateMassEditStage,
    useArchiveSurrogate,
    useAssignSurrogate,
    useBulkArchive,
    useBulkAssign,
    useChangeSurrogateStatus,
    useCreateContactAttempt,
    useLogInterviewOutcome,
    useRevealSurrogateSensitiveInfo,
    useRestoreSurrogate,
    useUpdateSurrogate,
} from "@/lib/hooks/use-surrogates"

type MutationOptions = {
    onSuccess?: (response: unknown, variables: unknown) => void
}

describe("surrogate mutation hooks", () => {
    let capturedOptions: MutationOptions | null = null
    const invalidateQueries = vi.fn()
    const setQueryData = vi.fn()

    beforeEach(() => {
        capturedOptions = null
        invalidateQueries.mockReset()
        setQueryData.mockReset()

        vi.mocked(useQueryClient).mockReturnValue({
            invalidateQueries,
            setQueryData,
        } as unknown as ReturnType<typeof useQueryClient>)

        vi.mocked(useMutation).mockImplementation((options: unknown) => {
            capturedOptions = options as MutationOptions
            return {
                mutateAsync: vi.fn(),
                isPending: false,
            } as unknown as ReturnType<typeof useMutation>
        })
    })

    it("invalidates surrogate activity and task lists after a stage change", () => {
        useChangeSurrogateStatus()

        capturedOptions?.onSuccess?.(
            {
                status: "applied",
                surrogate: { id: "surrogate-1" },
            },
            {
                surrogateId: "surrogate-1",
                data: { stage_id: "stage-on-hold" },
            }
        )

        expect(setQueryData).toHaveBeenCalledWith(
            surrogateKeys.detail("surrogate-1"),
            { id: "surrogate-1" }
        )
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.activity("surrogate-1"),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: ["tasks", "list"],
        })
    })

    it("invalidates surrogate lists after logging an interview outcome", () => {
        useLogInterviewOutcome()

        capturedOptions?.onSuccess?.(
            {},
            {
                surrogateId: "surrogate-1",
                data: { interview_id: "interview-1", outcome: "pass" },
            }
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.activity("surrogate-1"),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.detail("surrogate-1"),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.lists(),
        })
    })

    it("invalidates surrogate lists after logging a contact attempt", () => {
        useCreateContactAttempt()

        capturedOptions?.onSuccess?.(
            {},
            {
                surrogateId: "surrogate-1",
                data: {
                    contact_methods: ["phone"],
                    outcome: "no_answer",
                },
            }
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: contactAttemptKeys.all("surrogate-1"),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.detail("surrogate-1"),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.activity("surrogate-1"),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.lists(),
        })
    })

    it("invalidates activity after revealing sensitive surrogate info", () => {
        useRevealSurrogateSensitiveInfo()

        capturedOptions?.onSuccess?.(
            { ssn: "123-45-6789", partner_ssn: null },
            "surrogate-1"
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.activity("surrogate-1"),
        })
    })

    it("refreshes detail, activity, list, stats, and queue caches after updating a surrogate", () => {
        useUpdateSurrogate()

        capturedOptions?.onSuccess?.(
            { id: "surrogate-1" },
            {
                surrogateId: "surrogate-1",
                data: { full_name: "Updated Lead" },
            }
        )

        expect(setQueryData).toHaveBeenCalledWith(surrogateKeys.detail("surrogate-1"), {
            id: "surrogate-1",
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.detail("surrogate-1"),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.activity("surrogate-1"),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.lists(),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.stats(),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.unassignedQueue(),
        })
    })

    it("refreshes assignment-sensitive caches after assigning a surrogate", () => {
        useAssignSurrogate()

        capturedOptions?.onSuccess?.(
            { id: "surrogate-1" },
            {
                surrogateId: "surrogate-1",
                owner_type: "queue",
                owner_id: "queue-1",
            }
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.activity("surrogate-1"),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.unassignedQueue(),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.stats(),
        })
    })

    it("refreshes list, stats, queue, and detail caches after archive lifecycle mutations", () => {
        useArchiveSurrogate()
        capturedOptions?.onSuccess?.({ id: "surrogate-1" }, "surrogate-1")

        useRestoreSurrogate()
        capturedOptions?.onSuccess?.({ id: "surrogate-1" }, "surrogate-1")

        useBulkArchive()
        capturedOptions?.onSuccess?.(
            { archived: 2, failed: [] },
            ["surrogate-1", "surrogate-2"]
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.activity("surrogate-1"),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.detail("surrogate-2"),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.lists(),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.stats(),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.unassignedQueue(),
        })
    })

    it("refreshes selected surrogate caches after bulk assignment and mass edit mutations", () => {
        useBulkAssign()
        capturedOptions?.onSuccess?.(
            { assigned: 2, failed: [] },
            {
                surrogate_ids: ["surrogate-1", "surrogate-2"],
                owner_type: "user",
                owner_id: "user-1",
            }
        )

        useApplySurrogateMassEditStage()
        capturedOptions?.onSuccess?.(
            { matched: 2, applied: 2, pending_approval: 0, failed: [] },
            {
                filters: {},
                stage_id: "stage-1",
                expected_total: 2,
                trigger_workflows: true,
            }
        )

        useApplySurrogateMassEditArchive()
        capturedOptions?.onSuccess?.(
            { matched: 2, archived: 2, failed: [] },
            {
                filters: {},
                expected_total: 2,
            }
        )

        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.activity("surrogate-1"),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.detail("surrogate-2"),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: surrogateKeys.unassignedQueue(),
        })
        expect(invalidateQueries).toHaveBeenCalledWith({
            queryKey: ["tasks", "list"],
        })
    })
})
