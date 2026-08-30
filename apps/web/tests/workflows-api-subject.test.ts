import { beforeEach, describe, expect, it, vi } from "vitest"

import { getWorkflowOptions, listWorkflows } from "@/lib/api/workflows"

const mockGet = vi.fn()

vi.mock("@/lib/api", () => ({
    __esModule: true,
    default: {
        get: (...args: unknown[]) => mockGet(...args),
    },
}))

describe("workflow subject API contract", () => {
    beforeEach(() => {
        mockGet.mockReset().mockResolvedValue([])
    })

    it("filters workflow lists by the exact donor subject", async () => {
        await listWorkflows({ scope: "org", subject_type: "sperm_donor" })

        expect(mockGet).toHaveBeenCalledWith(
            "/workflows?scope=org&subject_type=sperm_donor",
        )
    })

    it("requests subject-specific workflow builder options", async () => {
        await getWorkflowOptions("personal", "egg_donor")

        expect(mockGet).toHaveBeenCalledWith(
            "/workflows/options?workflow_scope=personal&subject_type=egg_donor",
        )
    })
})
