import { beforeEach, describe, expect, it, vi } from "vitest"

import { duplicateCampaign, previewFilters } from "@/lib/api/campaigns"

const mockGet = vi.fn()
const mockPost = vi.fn()

vi.mock("@/lib/api", () => ({
    __esModule: true,
    default: {
        get: (...args: unknown[]) => mockGet(...args),
        post: (...args: unknown[]) => mockPost(...args),
    },
}))

describe("donor campaign API contract", () => {
    beforeEach(() => {
        mockGet.mockReset()
        mockPost.mockReset().mockResolvedValue({})
    })

    it("previews an exact donor subtype with its stage filters", async () => {
        await previewFilters(
            "email",
            "egg_donor",
            { stage_ids: ["egg-stage-1"], states: ["CA"] },
            false,
            3,
        )

        expect(mockPost).toHaveBeenCalledWith("/campaigns/preview-filters?limit=3", {
            channel: "email",
            recipient_type: "egg_donor",
            filter_criteria: { stage_ids: ["egg-stage-1"], states: ["CA"] },
            include_unsubscribed: false,
        })
    })

    it("preserves the exact donor subtype and filters when duplicating", async () => {
        mockGet.mockResolvedValue({
            id: "campaign-1",
            name: "Sperm donor follow-up",
            description: "Collection reminder",
            channel: "email",
            email_template_id: "template-1",
            recipient_type: "sperm_donor",
            filter_criteria: { stage_ids: ["sperm-stage-1"] },
            include_unsubscribed: false,
        })

        await duplicateCampaign("campaign-1")

        expect(mockPost).toHaveBeenCalledWith("/campaigns", {
            name: "Sperm donor follow-up (Copy)",
            description: "Collection reminder",
            channel: "email",
            email_template_id: "template-1",
            recipient_type: "sperm_donor",
            filter_criteria: { stage_ids: ["sperm-stage-1"] },
            include_unsubscribed: false,
        })
    })
})
