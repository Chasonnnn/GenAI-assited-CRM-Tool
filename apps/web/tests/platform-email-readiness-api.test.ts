import { beforeEach, describe, expect, it, vi } from "vitest"

import {
    getPlatformEmailReadiness,
    getPlatformEmailStatus,
    requestPlatformEmailReadinessCheck,
} from "@/lib/api/platform"

const mockGet = vi.fn()
const mockPost = vi.fn()

vi.mock("@/lib/api", () => ({
    __esModule: true,
    default: {
        get: (...args: unknown[]) => mockGet(...args),
        post: (...args: unknown[]) => mockPost(...args),
    },
}))

describe("platform email readiness API", () => {
    beforeEach(() => {
        mockGet.mockReset()
        mockPost.mockReset()
        mockGet.mockResolvedValue({})
        mockPost.mockResolvedValue({})
    })

    it("reads the additive platform email status contract", async () => {
        await getPlatformEmailStatus()

        expect(mockGet).toHaveBeenCalledTimes(1)
        expect(mockGet).toHaveBeenCalledWith("/platform/email/status")
    })

    it("reads live readiness from its cache-only endpoint", async () => {
        await getPlatformEmailReadiness()

        expect(mockGet).toHaveBeenCalledTimes(1)
        expect(mockGet).toHaveBeenCalledWith("/platform/email/readiness")
    })

    it("requests one read-only platform readiness check without a request payload", async () => {
        await requestPlatformEmailReadinessCheck()

        expect(mockPost).toHaveBeenCalledTimes(1)
        expect(mockPost).toHaveBeenCalledWith("/platform/email/readiness/check")
    })
})
