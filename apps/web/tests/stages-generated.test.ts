import { describe, expect, it } from "vitest"
import {
    DEFAULT_STAGE_ORDER_BY_ENTITY,
    DEFAULT_STAGE_SEMANTICS_BY_KEY,
    DEFAULT_STAGE_ORDER,
    PIPELINE_ENTITY_TYPES,
    STAGE_DEFS,
    STAGE_TYPE_MAP,
} from "@/lib/constants/stages.generated"

describe("stages.generated", () => {
    it("exports the exact pipeline entity type contract", () => {
        expect(PIPELINE_ENTITY_TYPES).toEqual([
            "surrogate",
            "intended_parent",
            "egg_donor",
            "sperm_donor",
        ])
    })

    it("exports distinct egg and sperm donor defaults", () => {
        expect(DEFAULT_STAGE_ORDER_BY_ENTITY.egg_donor).toEqual([
            "new",
            "contacted",
            "pre_screening",
            "application_submitted",
            "medical_records_review",
            "psychological_screening",
            "ready_to_match",
            "matched",
            "cycle_in_progress",
            "retrieval_complete",
            "on_hold",
            "disqualified",
            "closed",
        ])
        expect(DEFAULT_STAGE_ORDER_BY_ENTITY.sperm_donor).toEqual([
            "new",
            "contacted",
            "pre_screening",
            "application_submitted",
            "semen_analysis",
            "medical_genetic_screening",
            "available",
            "matched",
            "collection_in_progress",
            "donation_complete",
            "on_hold",
            "disqualified",
            "closed",
        ])
        expect(DEFAULT_STAGE_ORDER_BY_ENTITY.egg_donor).not.toEqual(
            DEFAULT_STAGE_ORDER_BY_ENTITY.sperm_donor
        )
    })

    it("matches the full platform surrogate default stage order", () => {
        expect(DEFAULT_STAGE_ORDER).toEqual([
            "new_unread",
            "contacted",
            "pre_qualified",
            "application_submitted",
            "interview_scheduled",
            "pending_docusign",
            "under_review",
            "approved",
            "ready_to_match",
            "matched",
            "medical_clearance_passed",
            "legal_clearance_passed",
            "transfer_cycle",
            "second_hcg_confirmed",
            "heartbeat_confirmed",
            "life_insurance_application_started",
            "ob_care_established",
            "pbo_process_started",
            "anatomy_scanned",
            "delivered",
            "on_hold",
            "cold_leads",
            "lost",
            "disqualified",
        ])
    })

    it("exports the new stage labels and categories", () => {
        expect(
            STAGE_DEFS.map((stage) => [stage.stageKey, stage.label, stage.stageType])
        ).toEqual([
            ["new_unread", "New Unread", "intake"],
            ["contacted", "Contacted", "intake"],
            ["pre_qualified", "Pre-Qualified", "intake"],
            ["application_submitted", "Application Submitted", "intake"],
            ["interview_scheduled", "Interview Scheduled", "intake"],
            ["pending_docusign", "Pending-DocuSign", "intake"],
            ["under_review", "Under Review", "intake"],
            ["approved", "Approved", "intake"],
            ["ready_to_match", "Ready to Match", "post_approval"],
            ["matched", "Matched", "post_approval"],
            ["medical_clearance_passed", "Medical Clearance Passed", "post_approval"],
            ["legal_clearance_passed", "Legal Clearance Passed", "post_approval"],
            ["transfer_cycle", "Transfer Cycle Initiated", "post_approval"],
            ["second_hcg_confirmed", "Second hCG confirmed", "post_approval"],
            ["heartbeat_confirmed", "Heartbeat Confirmed", "post_approval"],
            [
                "life_insurance_application_started",
                "Life Insurance Application Started",
                "post_approval",
            ],
            ["ob_care_established", "OB Care Established", "post_approval"],
            ["pbo_process_started", "PBO Process Started", "post_approval"],
            ["anatomy_scanned", "Anatomy Scanned", "post_approval"],
            ["delivered", "Delivered", "post_approval"],
            ["on_hold", "On-Hold", "paused"],
            ["cold_leads", "Cold Leads", "terminal"],
            ["lost", "Lost", "terminal"],
            ["disqualified", "Disqualified", "terminal"],
        ])
    })

    it("exposes the new stage types to generated consumers", () => {
        expect(STAGE_TYPE_MAP.pending_docusign).toBe("intake")
        expect(STAGE_TYPE_MAP.life_insurance_application_started).toBe("post_approval")
        expect(STAGE_TYPE_MAP.pbo_process_started).toBe("post_approval")
        expect(STAGE_TYPE_MAP.cold_leads).toBe("terminal")
    })

    it("exports backend-owned default semantics for representative lifecycle stages", () => {
        expect(DEFAULT_STAGE_SEMANTICS_BY_KEY.new_unread).toMatchObject({
            integration_bucket: "none",
            analytics_bucket: "new_unread",
            suggestion_profile_key: "new_unread_followup",
            capabilities: {
                counts_as_contacted: false,
            },
        })

        expect(DEFAULT_STAGE_SEMANTICS_BY_KEY.contacted).toMatchObject({
            integration_bucket: "intake",
            analytics_bucket: "contacted",
            suggestion_profile_key: "contacted_followup",
            capabilities: {
                counts_as_contacted: true,
            },
        })

        expect(DEFAULT_STAGE_SEMANTICS_BY_KEY.ready_to_match).toMatchObject({
            integration_bucket: "converted",
            analytics_bucket: "ready_to_match",
            capabilities: {
                eligible_for_matching: true,
            },
        })

        expect(DEFAULT_STAGE_SEMANTICS_BY_KEY.on_hold).toMatchObject({
            pause_behavior: "resume_previous_stage",
            analytics_bucket: "on_hold",
            requires_reason_on_enter: true,
        })

        expect(DEFAULT_STAGE_SEMANTICS_BY_KEY.lost).toMatchObject({
            terminal_outcome: "lost",
            integration_bucket: "lost",
            suggestion_profile_key: null,
        })

        expect(DEFAULT_STAGE_SEMANTICS_BY_KEY.disqualified).toMatchObject({
            terminal_outcome: "disqualified",
            integration_bucket: "not_qualified",
            suggestion_profile_key: null,
        })
    })
})
