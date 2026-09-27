import { describe, expect, it } from "vitest"

import type { PipelineStage } from "@/lib/api/pipelines"
import { STAGE_DEFS } from "@/lib/constants/stages.generated"
import { getDonorStageLabel } from "@/lib/donor-stage-utils"
import { getMatchActionLabel, getMatchStatusLabel, isMatchStatus } from "@/lib/match-status-definitions"

const orgStages: PipelineStage[] = [
    { id: "stage-under-review", stage_key: "under_review", slug: "under_review", label: "Application Review", color: "#F59E0B", order: 8, stage_type: "intake", is_active: true },
    { id: "stage-ready", stage_key: "ready_to_match", slug: "ready_to_match", label: "Ready to Match", color: "#10B981", order: 12, stage_type: "post_approval", is_active: true },
]

describe("match status and stage label helpers", () => {
    it("disagree on under_review: the stage label comes from the pipeline, the status label from match definitions", () => {
        expect(STAGE_DEFS.some((stage) => stage.slug === "under_review")).toBe(true)
        const stageLabel = getDonorStageLabel(orgStages, { stage_key: "under_review" })
        const statusLabel = getMatchStatusLabel("under_review")
        expect(stageLabel).toBe("Application Review")
        expect(statusLabel).toBe("Under Review")
        expect(stageLabel).not.toBe(statusLabel)
    })

    it("does not resolve values from the other domain", () => {
        expect(isMatchStatus("ready_to_match")).toBe(false)
        expect(getMatchStatusLabel("ready_to_match")).not.toBe("Ready to Match")
        expect(isMatchStatus("stage-under-review")).toBe(false)
        expect(getDonorStageLabel(orgStages, { stage_key: "cancellation_pending" })).toBe("Stage unavailable")
    })

    it("labels match actions without echoing raw keys", () => {
        expect(getMatchActionLabel("request_cancel")).toBe("Request cancellation")
        expect(getMatchActionLabel("not_an_action")).toBe("Unknown match action")
    })
})
