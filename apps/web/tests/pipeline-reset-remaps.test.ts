import { describe, expect, it } from "vitest"

import { buildRecommendedDraftRemaps } from "@/lib/pipeline-reset-remaps"

const currentStages = [
    {
        stage_key: "new_unread",
        order: 1,
        category: "intake" as const,
        stage_type: "intake" as const,
        is_active: true,
        semantics: {
            capabilities: {
                counts_as_contacted: false,
                eligible_for_matching: false,
                locks_match_state: false,
                shows_pregnancy_tracking: false,
                requires_delivery_details: false,
                tracks_interview_outcome: false,
            },
            pause_behavior: "none" as const,
            terminal_outcome: "none" as const,
            integration_bucket: "intake" as const,
            analytics_bucket: "new_unread",
            suggestion_profile_key: "new_unread_followup",
            requires_reason_on_enter: false,
        },
    },
    {
        stage_key: "application_packet_received",
        order: 4,
        category: "intake" as const,
        stage_type: "intake" as const,
        is_active: true,
        semantics: {
            capabilities: {
                counts_as_contacted: true,
                eligible_for_matching: false,
                locks_match_state: false,
                shows_pregnancy_tracking: false,
                requires_delivery_details: false,
                tracks_interview_outcome: false,
            },
            pause_behavior: "none" as const,
            terminal_outcome: "none" as const,
            integration_bucket: "qualified" as const,
            analytics_bucket: "application_submitted",
            suggestion_profile_key: "application_submitted_followup",
            requires_reason_on_enter: false,
        },
    },
    {
        stage_key: "panel_review",
        order: 6,
        category: "intake" as const,
        stage_type: "intake" as const,
        is_active: true,
        semantics: {
            capabilities: {
                counts_as_contacted: true,
                eligible_for_matching: false,
                locks_match_state: false,
                shows_pregnancy_tracking: false,
                requires_delivery_details: false,
                tracks_interview_outcome: true,
            },
            pause_behavior: "none" as const,
            terminal_outcome: "none" as const,
            integration_bucket: "qualified" as const,
            analytics_bucket: "under_review",
            suggestion_profile_key: "under_review_followup",
            requires_reason_on_enter: false,
        },
    },
    {
        stage_key: "transfer_readiness",
        order: 12,
        category: "post_approval" as const,
        stage_type: "post_approval" as const,
        is_active: true,
        semantics: {
            capabilities: {
                counts_as_contacted: false,
                eligible_for_matching: false,
                locks_match_state: false,
                shows_pregnancy_tracking: false,
                requires_delivery_details: false,
                tracks_interview_outcome: false,
            },
            pause_behavior: "none" as const,
            terminal_outcome: "none" as const,
            integration_bucket: "converted" as const,
            analytics_bucket: "transfer_readiness",
            suggestion_profile_key: "transfer_cycle_followup",
            requires_reason_on_enter: false,
        },
    },
]

const recommendedStages = [
    currentStages[0],
    {
        stage_key: "application_submitted",
        order: 4,
        category: "intake" as const,
        stage_type: "intake" as const,
        is_active: true,
        semantics: currentStages[1].semantics,
    },
    {
        stage_key: "under_review",
        order: 6,
        category: "intake" as const,
        stage_type: "intake" as const,
        is_active: true,
        semantics: currentStages[2].semantics,
    },
    {
        stage_key: "transfer_cycle",
        order: 12,
        category: "post_approval" as const,
        stage_type: "post_approval" as const,
        is_active: true,
        semantics: {
            capabilities: {
                counts_as_contacted: false,
                eligible_for_matching: false,
                locks_match_state: true,
                shows_pregnancy_tracking: false,
                requires_delivery_details: false,
                tracks_interview_outcome: false,
            },
            pause_behavior: "none" as const,
            terminal_outcome: "none" as const,
            integration_bucket: "converted" as const,
            analytics_bucket: "transfer_cycle",
            suggestion_profile_key: "transfer_cycle_followup",
            requires_reason_on_enter: false,
        },
    },
]

describe("buildRecommendedDraftRemaps", () => {
    it("maps removed custom stages onto the closest default stages", () => {
        expect(buildRecommendedDraftRemaps(currentStages, recommendedStages)).toEqual([
            {
                removed_stage_key: "application_packet_received",
                target_stage_key: "application_submitted",
            },
            {
                removed_stage_key: "panel_review",
                target_stage_key: "under_review",
            },
            {
                removed_stage_key: "transfer_readiness",
                target_stage_key: "transfer_cycle",
            },
        ])
    })
})
