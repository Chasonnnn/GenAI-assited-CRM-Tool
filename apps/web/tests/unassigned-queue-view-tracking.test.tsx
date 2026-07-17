import { renderHook } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { useTrackUnassignedQueueView } from "@/lib/hooks/use-track-unassigned-queue-view"

const trackViewed = vi.fn()

vi.mock("@/lib/workflow-metrics", () => ({
    trackUnassignedQueueViewed: () => trackViewed(),
}))

describe("useTrackUnassignedQueueView", () => {
    it("tracks once when the authorized queue becomes active", () => {
        const view = renderHook(
            ({ enabled }) => useTrackUnassignedQueueView(enabled),
            { initialProps: { enabled: false } }
        )

        expect(trackViewed).not.toHaveBeenCalled()

        view.rerender({ enabled: true })
        expect(trackViewed).toHaveBeenCalledTimes(1)

        view.rerender({ enabled: true })
        expect(trackViewed).toHaveBeenCalledTimes(1)
    })
})
