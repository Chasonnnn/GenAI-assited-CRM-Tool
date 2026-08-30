import { beforeEach, describe, expect, it, vi } from "vitest"

import { attachmentsApi } from "@/lib/api/attachments"

const mockGet = vi.fn()
const mockUpload = vi.fn()
const mockDelete = vi.fn()

vi.mock("@/lib/api", () => ({
    __esModule: true,
    default: {
        get: (...args: unknown[]) => mockGet(...args),
        upload: (...args: unknown[]) => mockUpload(...args),
        delete: (...args: unknown[]) => mockDelete(...args),
    },
}))

describe("donor attachments API", () => {
    beforeEach(() => {
        mockGet.mockReset().mockResolvedValue([])
        mockUpload.mockReset().mockResolvedValue({})
        mockDelete.mockReset().mockResolvedValue(undefined)
    })

    it("lists and uploads donor documents through donor attachment routes", async () => {
        const file = new File(["document"], "screening.pdf", { type: "application/pdf" })

        await attachmentsApi.listForDonor("donor-1")
        await attachmentsApi.uploadForDonor("donor-1", file)

        expect(mockGet).toHaveBeenCalledWith("/attachments/donors/donor-1/attachments")
        expect(mockUpload).toHaveBeenCalledWith(
            "/attachments/donors/donor-1/attachments",
            expect.any(FormData),
        )
        expect((mockUpload.mock.calls[0]?.[1] as FormData).get("file")).toBe(file)
    })

    it("uploads a donor profile photo through its dedicated image route", async () => {
        const file = new File(["image"], "profile.jpg", { type: "image/jpeg" })

        await attachmentsApi.uploadDonorProfilePhoto("donor-1", file)

        expect(mockUpload).toHaveBeenCalledWith(
            "/attachments/donors/donor-1/profile-photo",
            expect.any(FormData),
        )
        expect((mockUpload.mock.calls[0]?.[1] as FormData).get("file")).toBe(file)
    })
})
