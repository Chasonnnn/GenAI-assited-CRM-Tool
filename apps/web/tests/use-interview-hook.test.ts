import { beforeEach, describe, expect, it, vi } from "vitest"
import { useQuery } from "@tanstack/react-query"

import { useInterview } from "@/lib/hooks/use-interviews"

describe("useInterview", () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it("polls interview detail only while transcription is pending", () => {
        useInterview("interview-1", { pollWhileTranscribing: true })

        const mockedUseQuery = vi.mocked(useQuery)
        expect(mockedUseQuery).toHaveBeenCalledTimes(1)
        expect(mockedUseQuery.mock.calls[0]?.[0]?.refetchInterval).toBe(5_000)

        vi.clearAllMocks()
        useInterview("interview-1", { pollWhileTranscribing: false })

        expect(mockedUseQuery.mock.calls[0]?.[0]?.refetchInterval).toBe(false)
    })
})
