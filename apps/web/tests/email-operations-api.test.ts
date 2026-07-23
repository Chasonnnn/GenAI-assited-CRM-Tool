import { beforeEach, describe, expect, it, vi } from "vitest"

import {
    getEmailOperationMessage,
    getEmailOperationsMessages,
    getEmailOperationsReadiness,
} from "@/lib/api/email-operations"

const mockGet = vi.fn()

vi.mock("@/lib/api", () => ({
    __esModule: true,
    default: {
        get: (...args: unknown[]) => mockGet(...args),
    },
}))

describe("email operations API", () => {
    beforeEach(() => {
        mockGet.mockReset()
        mockGet.mockResolvedValue({})
    })

    it("uses the readiness and message endpoints with an encoded cursor", async () => {
        await getEmailOperationsReadiness()
        await getEmailOperationsMessages({ limit: 25, cursor: "cursor+with/slash=" })
        await getEmailOperationMessage("message/id")

        expect(mockGet).toHaveBeenNthCalledWith(1, "/email-operations/readiness")
        expect(mockGet).toHaveBeenNthCalledWith(
            2,
            "/email-operations/messages?limit=25&cursor=cursor%2Bwith%2Fslash%3D",
        )
        expect(mockGet).toHaveBeenNthCalledWith(
            3,
            "/email-operations/messages/message%2Fid",
        )
    })
})
