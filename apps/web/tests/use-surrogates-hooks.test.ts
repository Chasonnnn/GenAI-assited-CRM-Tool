import { beforeEach, describe, expect, it, vi } from "vitest"
import { useMutation, useQueryClient } from "@tanstack/react-query"

import {
    contactAttemptKeys,
    surrogateKeys,
    useChangeSurrogateStatus,
    useCreateContactAttempt,
    useLogInterviewOutcome,
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
})
