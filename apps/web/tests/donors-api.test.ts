import { beforeEach, describe, expect, it, vi } from "vitest"

import {
    archiveDonor,
    createDonorNote,
    createDonor,
    deleteDonorNote,
    getDonorHistory,
    listDonorNotes,
    listDonors,
    restoreDonor,
    updateDonorStatus,
} from "@/lib/api/donors"

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPatch = vi.fn()
const mockDelete = vi.fn()

vi.mock("@/lib/api", () => ({
    __esModule: true,
    default: {
        get: (...args: unknown[]) => mockGet(...args),
        post: (...args: unknown[]) => mockPost(...args),
        patch: (...args: unknown[]) => mockPatch(...args),
        delete: (...args: unknown[]) => mockDelete(...args),
    },
}))

describe("donors API client", () => {
    beforeEach(() => {
        mockGet.mockReset().mockResolvedValue({})
        mockPost.mockReset().mockResolvedValue({})
        mockPatch.mockReset().mockResolvedValue({})
        mockDelete.mockReset().mockResolvedValue(undefined)
    })

    it("lists one donor type with the supported filters", async () => {
        await listDonors({
            donor_type: "sperm",
            stage_id: "stage-1",
            q: "D10001",
            owner_id: "owner-1",
            dynamic_filter: "attention_stuck",
            created_from: "2026-08-01",
            created_to: "2026-08-29",
            sort_by: "stage",
            sort_order: "asc",
            archived_only: true,
            page: 2,
            per_page: 20,
        })

        expect(mockGet).toHaveBeenCalledWith(
            "/donors?donor_type=sperm&stage_id=stage-1&q=D10001&owner_id=owner-1&dynamic_filter=attention_stuck&created_from=2026-08-01&created_to=2026-08-29&sort_by=stage&sort_order=asc&archived_only=true&page=2&per_page=20",
        )
    })

    it("creates, changes stage, archives, restores, and fetches history through donor routes", async () => {
        const createPayload = {
            donor_type: "egg" as const,
            full_name: "Maya Thompson",
            email: "maya@example.com",
            education: "B.S. Biology",
        }
        await createDonor(createPayload)
        await updateDonorStatus("donor-1", { stage_id: "stage-2", reason: "Qualified" })
        await archiveDonor("donor-1")
        await restoreDonor("donor-1")
        await getDonorHistory("donor-1")

        expect(mockPost).toHaveBeenCalledWith("/donors", createPayload)
        expect(mockPatch).toHaveBeenCalledWith("/donors/donor-1/status", {
            stage_id: "stage-2",
            reason: "Qualified",
        })
        expect(mockPost).toHaveBeenCalledWith("/donors/donor-1/archive", {})
        expect(mockPost).toHaveBeenCalledWith("/donors/donor-1/restore", {})
        expect(mockGet).toHaveBeenCalledWith("/donors/donor-1/history")
    })

    it("lists, creates, and deletes notes through donor-scoped routes", async () => {
        await listDonorNotes("donor-1")
        await createDonorNote("donor-1", { content: "Screening call complete" })
        await deleteDonorNote("donor-1", "note-1")

        expect(mockGet).toHaveBeenCalledWith("/donors/donor-1/notes")
        expect(mockPost).toHaveBeenCalledWith("/donors/donor-1/notes", {
            content: "Screening call complete",
        })
        expect(mockDelete).toHaveBeenCalledWith("/donors/donor-1/notes/note-1")
    })
})
