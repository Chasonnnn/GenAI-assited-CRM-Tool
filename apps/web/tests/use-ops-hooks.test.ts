import { beforeEach, describe, expect, it, vi } from "vitest"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { ApiError } from "@/lib/api"

vi.mock("sonner", () => ({
    toast: {
        error: vi.fn(),
    },
}))

import { useAcknowledgeAlert, useResolveAlert, useSnoozeAlert } from "@/lib/hooks/use-ops"

type MutationOptions = {
    onError?: (error: unknown) => void
}

describe("ops alert mutation hooks", () => {
    let capturedOptions: MutationOptions | null = null
    const invalidateQueries = vi.fn()

    beforeEach(() => {
        capturedOptions = null
        invalidateQueries.mockReset()
        vi.mocked(toast.error).mockReset()

        vi.mocked(useQueryClient).mockReturnValue({
            invalidateQueries,
        } as unknown as ReturnType<typeof useQueryClient>)

        vi.mocked(useMutation).mockImplementation((options: unknown) => {
            capturedOptions = options as MutationOptions
            return {
                mutate: vi.fn(),
                isPending: false,
            } as unknown as ReturnType<typeof useMutation>
        })
    })

    it("shows API message for resolve alert errors", () => {
        useResolveAlert()

        expect(capturedOptions?.onError).toBeTypeOf("function")
        capturedOptions?.onError?.(new ApiError(500, "Internal Server Error", "Resolve failed"))

        expect(toast.error).toHaveBeenCalledWith("Resolve failed")
    })

    it("shows API message for acknowledge alert errors", () => {
        useAcknowledgeAlert()

        expect(capturedOptions?.onError).toBeTypeOf("function")
        capturedOptions?.onError?.(new ApiError(500, "Internal Server Error", "Acknowledge failed"))

        expect(toast.error).toHaveBeenCalledWith("Acknowledge failed")
    })

    it("shows API message for snooze alert errors", () => {
        useSnoozeAlert()

        expect(capturedOptions?.onError).toBeTypeOf("function")
        capturedOptions?.onError?.(new ApiError(500, "Internal Server Error", "Snooze failed"))

        expect(toast.error).toHaveBeenCalledWith("Snooze failed")
    })
})
