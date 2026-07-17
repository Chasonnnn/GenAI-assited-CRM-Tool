import { renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useTrackSurrogateView } from "@/lib/hooks/use-track-surrogate-view"

const trackSurrogateViewed = vi.hoisted(() => vi.fn())

vi.mock("@/lib/workflow-metrics", () => ({
    trackSurrogateViewed,
}))

describe("useTrackSurrogateView", () => {
    beforeEach(() => {
        trackSurrogateViewed.mockReset()
    })

    it("tracks each available surrogate ID once when the viewed record changes", () => {
        const { rerender } = renderHook(
            ({ surrogateId }) => useTrackSurrogateView(surrogateId),
            {
                initialProps: {
                    surrogateId: null as string | null,
                },
            }
        )

        expect(trackSurrogateViewed).not.toHaveBeenCalled()

        rerender({ surrogateId: "surrogate-1" })
        expect(trackSurrogateViewed).toHaveBeenLastCalledWith("surrogate-1")

        rerender({ surrogateId: "surrogate-1" })
        expect(trackSurrogateViewed).toHaveBeenCalledTimes(1)

        rerender({ surrogateId: "surrogate-2" })
        expect(trackSurrogateViewed).toHaveBeenNthCalledWith(2, "surrogate-2")
    })
})
