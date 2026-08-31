import { beforeEach, describe, expect, it, vi } from "vitest"

import {
    getDashboardDonorsByStatus,
    getDonorAnalyticsSummary,
    getDonorsByStatus,
    getDonorsTrend,
} from "@/lib/api/analytics"

const mockGet = vi.fn()

vi.mock("@/lib/api", () => ({
    __esModule: true,
    default: {
        get: (...args: unknown[]) => mockGet(...args),
    },
}))

describe("donor analytics API contract", () => {
    beforeEach(() => {
        mockGet.mockReset().mockResolvedValue([])
    })

    it("preserves subtype and every analytics filter on report endpoints", async () => {
        const params = {
            donor_type: "egg" as const,
            from_date: "2026-08-01",
            to_date: "2026-08-29",
            period: "week" as const,
            timezone: "America/New_York",
            pipeline_id: "pipeline-1",
            owner_id: "owner-1",
            state: "NY",
            include_archived: true,
        }

        await getDonorAnalyticsSummary(params)
        await getDonorsByStatus(params)
        await getDonorsTrend(params)

        const sharedQuery = "donor_type=egg&from_date=2026-08-01&to_date=2026-08-29&pipeline_id=pipeline-1&owner_id=owner-1&state=NY&include_archived=true"
        const trendQuery = "donor_type=egg&from_date=2026-08-01&to_date=2026-08-29&period=week&pipeline_id=pipeline-1&owner_id=owner-1&timezone=America%2FNew_York&state=NY&include_archived=true"
        expect(mockGet).toHaveBeenNthCalledWith(1, `/analytics/donors/summary?${sharedQuery}`)
        expect(mockGet).toHaveBeenNthCalledWith(2, `/analytics/donors/by-status?${sharedQuery}`)
        expect(mockGet).toHaveBeenNthCalledWith(3, `/analytics/donors/trend?${trendQuery}`)
    })

    it("uses the dashboard permission surface for pipeline distribution", async () => {
        await getDashboardDonorsByStatus({ donor_type: "sperm" })

        expect(mockGet).toHaveBeenCalledWith(
            "/dashboard/donors/by-status?donor_type=sperm",
        )
    })
})
