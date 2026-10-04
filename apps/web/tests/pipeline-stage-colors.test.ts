import { describe, expect, it } from "vitest"

import { resolveStageColor, shouldAutoRefreshStageColor, suggestStageColor } from "@/lib/pipeline-stage-colors"
import { stageDisplayColor } from "@/lib/stage-colors"

describe("pipeline stage colors", () => {
    it("suggests keyword colors as displayed colors", () => {
        expect(suggestStageColor({ label: "Medical clearance" })).toBe(stageDisplayColor("#14b8a6"))
        expect(suggestStageColor({ slug: "qualification-review" })).toBe(stageDisplayColor("#f59e0b"))
    })

    it("keeps refreshing suggestions stored before display darkening", () => {
        const stage = { label: "Medical clearance", stage_type: "post_approval" }
        expect(shouldAutoRefreshStageColor({ ...stage, color: "#14b8a6" })).toBe(true)
        expect(shouldAutoRefreshStageColor({ ...stage, color: stageDisplayColor("#14b8a6") })).toBe(true)
        expect(shouldAutoRefreshStageColor({ ...stage, color: "#123abc" })).toBe(false)
    })

    it("preserves explicit non-fallback colors", () => {
        expect(resolveStageColor({ color: "#123abc", label: "Medical clearance" })).toBe("#123abc")
    })
})
