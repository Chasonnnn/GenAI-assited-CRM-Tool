import { beforeEach, describe, expect, it, vi } from "vitest"

import {
    listEmailTemplateVersions,
    rollbackEmailTemplate,
} from "@/lib/api/email-template-history"

const mockGet = vi.fn()
const mockPost = vi.fn()

vi.mock("@/lib/api", () => ({
    __esModule: true,
    default: {
        get: (...args: unknown[]) => mockGet(...args),
        post: (...args: unknown[]) => mockPost(...args),
    },
}))

describe("email template history API", () => {
    beforeEach(() => {
        mockGet.mockReset()
        mockPost.mockReset()
    })

    it("lists the template's saved versions", async () => {
        mockGet.mockResolvedValue([])

        await listEmailTemplateVersions("template-1")

        expect(mockGet).toHaveBeenCalledWith(
            "/email-templates/template-1/versions?limit=50",
        )
    })

    it("restores a saved version through the rollback endpoint", async () => {
        mockPost.mockResolvedValue({ id: "template-1", current_version: 4 })

        await rollbackEmailTemplate("template-1", 2)

        expect(mockPost).toHaveBeenCalledWith(
            "/email-templates/template-1/rollback",
            { target_version: 2 },
        )
    })
})
