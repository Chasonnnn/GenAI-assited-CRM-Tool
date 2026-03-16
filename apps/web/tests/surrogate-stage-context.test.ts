import { describe, expect, it } from "vitest"
import { getSurrogateStageContext } from "@/lib/surrogate-stage-context"
import type { PipelineStage } from "@/lib/api/pipelines"

const stageById = new Map<string, PipelineStage>([
    [
        "stage_ready",
        {
            id: "stage_ready",
            stage_key: "ready_to_match",
            slug: "matching_queue",
            label: "Ready to Match",
            color: "#10b981",
            order: 10,
            stage_type: "post_approval",
            is_active: true,
        },
    ],
    [
        "stage_on_hold",
        {
            id: "stage_on_hold",
            stage_key: "on_hold",
            slug: "paused_review",
            label: "On-Hold",
            color: "#b4536a",
            order: 99,
            stage_type: "paused",
            is_active: true,
        },
    ],
])

describe("getSurrogateStageContext", () => {
    it("uses stage_key to resolve on-hold semantics when slugs are renamed", () => {
        const context = getSurrogateStageContext(
            {
                stage_id: "stage_on_hold",
                stage_key: "on_hold",
                stage_slug: "paused_review",
                stage_type: "paused",
                paused_from_stage_id: "stage_ready",
                paused_from_stage_key: "ready_to_match",
                paused_from_stage_slug: "matching_queue",
                paused_from_stage_label: "Ready to Match",
                paused_from_stage_type: "post_approval",
            },
            stageById
        )

        expect(context.isOnHold).toBe(true)
        expect(context.currentStageKey).toBe("on_hold")
        expect(context.effectiveStage?.id).toBe("stage_ready")
        expect(context.effectiveStageKey).toBe("ready_to_match")
        expect(context.effectiveStageSlug).toBe("matching_queue")
    })
})
