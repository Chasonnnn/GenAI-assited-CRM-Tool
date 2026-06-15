import { beforeEach, describe, expect, it, vi } from "vitest"

import {
    createIntakePoolGrant,
    getEffectivePermissions,
    getIntakePoolGrants,
    getMyEffectivePermissions,
    revokeIntakePoolGrant,
} from "../lib/api/permissions"

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockDelete = vi.fn()

vi.mock("@/lib/api", () => ({
    __esModule: true,
    default: {
        get: (...args: unknown[]) => mockGet(...args),
        post: (...args: unknown[]) => mockPost(...args),
        delete: (...args: unknown[]) => mockDelete(...args),
    },
}))

describe("permissions api client", () => {
    beforeEach(() => {
        mockGet.mockReset()
        mockPost.mockReset()
        mockDelete.mockReset()
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

    it("manages intake pool grant endpoints", async () => {
        await getIntakePoolGrants("grantee-1")
        expect(mockGet).toHaveBeenCalledWith(
            "/settings/permissions/intake-pool-grants?grantee_user_id=grantee-1"
        )

        await createIntakePoolGrant({
            source_user_id: "source-1",
            grantee_user_id: "grantee-1",
        })
        expect(mockPost).toHaveBeenCalledWith("/settings/permissions/intake-pool-grants", {
            source_user_id: "source-1",
            grantee_user_id: "grantee-1",
        })

        await revokeIntakePoolGrant("grant-1")
        expect(mockDelete).toHaveBeenCalledWith(
            "/settings/permissions/intake-pool-grants/grant-1"
        )
    })
})
