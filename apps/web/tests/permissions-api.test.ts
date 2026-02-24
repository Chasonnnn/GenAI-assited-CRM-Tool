import { beforeEach, describe, expect, it, vi } from "vitest"

import {
    getEffectivePermissions,
    getMyEffectivePermissions,
} from "../lib/api/permissions"

const mockGet = vi.fn()

vi.mock("@/lib/api", () => ({
    __esModule: true,
    default: {
        get: (...args: unknown[]) => mockGet(...args),
    },
}))

describe("permissions api client", () => {
    beforeEach(() => {
        mockGet.mockReset()
        mockGet.mockResolvedValue({
            user_id: "user-1",
            role: "admin",
            permissions: [],
            overrides: [],
        })
    })

    it("fetches self effective permissions from /effective/me", async () => {
        await getMyEffectivePermissions()
        expect(mockGet).toHaveBeenCalledWith("/settings/permissions/effective/me")
    })

    it("keeps user-targeted effective permissions endpoint for team-management flows", async () => {
        await getEffectivePermissions("user-2")
        expect(mockGet).toHaveBeenCalledWith("/settings/permissions/effective/user-2")
    })
})
