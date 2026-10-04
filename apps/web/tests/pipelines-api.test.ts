import { beforeEach, describe, expect, it, vi } from "vitest"

import { getPipelineVersions } from "@/lib/api/pipelines"

const mockGet = vi.fn()

vi.mock("@/lib/api", () => ({
    __esModule: true,
    default: {
        get: (...args: unknown[]) => mockGet(...args),
    },
}))

describe("pipelines API", () => {
    beforeEach(() => {
        mockGet.mockReset()
    })

    it("returns every version from the bare version list the API sends", async () => {
        const versions = [
            { id: "v2", version: 2, payload: { name: "Default", stages: [] }, comment: null, created_by_user_id: null, created_at: "2026-10-04T02:00:00Z" },
            { id: "v1", version: 1, payload: { name: "Default", stages: [] }, comment: null, created_by_user_id: null, created_at: "2026-10-03T02:00:00Z" },
        ]
        mockGet.mockResolvedValue(versions)

        await expect(getPipelineVersions("pipeline-1", "surrogate")).resolves.toEqual(versions)
        expect(mockGet).toHaveBeenCalledWith(expect.stringContaining("/settings/pipelines/pipeline-1/versions"))
    })
})
