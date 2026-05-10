import { describe, expect, it } from "vitest"

import { resolveStageColor, suggestStageColor } from "@/lib/pipeline-stage-colors"

describe("pipeline stage colors", () => {
    it("matches stage keyword colors without relying on array membership lookups", () => {
        expect(suggestStageColor({ label: "Medical clearance" })).toBe("#14b8a6")
        expect(suggestStageColor({ slug: "qualification-review" })).toBe("#f59e0b")
    })

    it("preserves explicit non-fallback colors", () => {
        expect(resolveStageColor({ color: "#123abc", label: "Medical clearance" })).toBe("#123abc")
    })
})
