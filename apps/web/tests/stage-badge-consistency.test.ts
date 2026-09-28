import { describe, expect, it } from "vitest"
import type { StageMetadataOption } from "@/lib/api/metadata"
import type { PipelineStage } from "@/lib/api/pipelines"
import { getDonorStageColor, getDonorStageStyle } from "@/lib/donor-stage-utils"
import { getIntendedParentStatusStyle } from "@/lib/intended-parent-stage-utils"
import { MATCH_STATUS_DEFINITIONS, getMatchStatusBadgeClassName } from "@/lib/match-status-definitions"
import { stageBadgeStyle } from "@/lib/stage-colors"

describe("stage badges across entity types", () => {
    it("renders intended-parent stages with the shared white-text style", () => {
        const options = [
            { id: "ip-1", value: "ready_to_match", label: "Ready to Match", stage_key: "ready_to_match", stage_slug: "ready_to_match", stage_type: "intake", color: "#0EA5E9", order: 2 },
        ] as StageMetadataOption[]

        expect(getIntendedParentStatusStyle(options, "ready_to_match")).toEqual(stageBadgeStyle("#0EA5E9"))
    })

    it("renders donor stages with the shared style and keeps the raw color for dots", () => {
        const stages = [{ id: "d-1", stage_key: "available", color: "#0EA5E9" }] as PipelineStage[]
        const donor = { stage_id: "d-1", stage_key: "available" }

        expect(getDonorStageStyle(stages, donor)).toEqual(stageBadgeStyle("#0EA5E9"))
        expect(getDonorStageColor(stages, donor)).toBe("#0EA5E9")
    })

    it("renders every match status as a solid fill with white text", () => {
        for (const definition of MATCH_STATUS_DEFINITIONS) {
            expect(definition.badgeClassName).toMatch(/^bg-\w+-\d{3} text-white$/)
        }
        expect(getMatchStatusBadgeClassName("unknown")).toBe("bg-gray-600 text-white")
    })
})
