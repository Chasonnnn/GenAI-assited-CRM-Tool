import { describe, expect, it } from "vitest"
import { getStageSemantics, getSurrogateStageContext } from "@/lib/surrogate-stage-context"
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

    it("resolves the new platform surrogate stage semantics conservatively", () => {
        expect(
            getStageSemantics({
                stage_key: "new_unread",
                stage_type: "intake",
            })
        ).toMatchObject({
            terminal_outcome: "none",
            integration_bucket: "none",
            analytics_bucket: "new_unread",
            suggestion_profile_key: "new_unread_followup",
            capabilities: {
                counts_as_contacted: false,
            },
        })

        expect(
            getStageSemantics({
                stage_key: "contacted",
                stage_type: "intake",
            })
        ).toMatchObject({
            terminal_outcome: "none",
            integration_bucket: "intake",
            analytics_bucket: "contacted",
            suggestion_profile_key: "contacted_followup",
            capabilities: {
                counts_as_contacted: true,
            },
        })

        expect(
            getStageSemantics({
                stage_key: "pending_docusign",
                stage_type: "intake",
            })
        ).toMatchObject({
            terminal_outcome: "none",
            integration_bucket: "qualified",
            capabilities: {
                counts_as_contacted: true,
                eligible_for_matching: false,
                locks_match_state: false,
                shows_pregnancy_tracking: false,
                requires_delivery_details: false,
                tracks_interview_outcome: false,
            },
        })

        expect(
            getStageSemantics({
                stage_key: "life_insurance_application_started",
                stage_type: "post_approval",
            })
        ).toMatchObject({
            terminal_outcome: "none",
            integration_bucket: "converted",
            capabilities: {
                locks_match_state: true,
                shows_pregnancy_tracking: true,
                requires_delivery_details: false,
            },
        })

        expect(
            getStageSemantics({
                stage_key: "pbo_process_started",
                stage_type: "post_approval",
            })
        ).toMatchObject({
            terminal_outcome: "none",
            integration_bucket: "converted",
            capabilities: {
                locks_match_state: true,
                shows_pregnancy_tracking: true,
                requires_delivery_details: false,
            },
        })

        expect(
            getStageSemantics({
                stage_key: "cold_leads",
                stage_type: "terminal",
            })
        ).toMatchObject({
            terminal_outcome: "none",
            integration_bucket: "none",
            capabilities: {
                counts_as_contacted: false,
                locks_match_state: false,
                shows_pregnancy_tracking: false,
                requires_delivery_details: false,
            },
        })
    })

    it("lets explicit server semantics override generated defaults", () => {
        expect(
            getStageSemantics({
                stage_key: "new_unread",
                stage_type: "intake",
                semantics: {
                    integration_bucket: "intake",
                    suggestion_profile_key: "custom_followup",
                    capabilities: {
                        counts_as_contacted: true,
                    },
                },
            })
        ).toMatchObject({
            integration_bucket: "intake",
            analytics_bucket: "new_unread",
            suggestion_profile_key: "custom_followup",
            capabilities: {
                counts_as_contacted: true,
                eligible_for_matching: false,
            },
        })
    })

    it("falls back conservatively for custom stages without generated semantics", () => {
        expect(
            getStageSemantics({
                stage_key: "custom_screening_review",
                stage_type: "intake",
            })
        ).toMatchObject({
            terminal_outcome: "none",
            integration_bucket: "none",
            analytics_bucket: "custom_screening_review",
            suggestion_profile_key: null,
            capabilities: {
                counts_as_contacted: false,
                eligible_for_matching: false,
                locks_match_state: false,
                shows_pregnancy_tracking: false,
                requires_delivery_details: false,
                tracks_interview_outcome: false,
            },
        })
    })
})
