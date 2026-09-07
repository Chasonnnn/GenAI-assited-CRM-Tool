import { beforeEach, describe, expect, it, vi } from "vitest"
import { getMatchWork, listMatches, uploadMatchFile, createMatchNote, completeMatch, updateMatchAttempt } from "@/lib/api/matches"
import api from "@/lib/api"
import { getTasks } from "@/lib/api/tasks"
import { getAppointments } from "@/lib/api/appointments"

vi.mock("@/lib/api", () => ({ default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), upload: vi.fn() } }))

describe("match API context", () => {
    beforeEach(() => vi.clearAllMocks())
    it("keeps donor filters explicit", async () => {
        await listMatches({ match_kind: "donor", donor_id: "donor1", intended_parent_id: "ip1", status: "completed" })
        expect(api.get).toHaveBeenCalledWith("/matches/?status=completed&donor_id=donor1&match_kind=donor&intended_parent_id=ip1")
    })
    it("requests the selected attempt and history page within the case", async () => {
        await getMatchWork("match2", "attempt3", 2)
        expect(api.get).toHaveBeenCalledWith("/matches/match2/work?attempt_id=attempt3&page=2")
    })
    it("serializes exact case and attempt filters for calendar tasks", async () => {
        await getTasks({ match_id: "match2", attempt_id: "attempt3", is_completed: false, exclude_approvals: true })
        const url = new URL(vi.mocked(api.get).mock.calls[0]![0], "https://example.test")
        expect(url.pathname).toBe("/tasks")
        expect(Object.fromEntries(url.searchParams)).toEqual({ match_id: "match2", attempt_id: "attempt3", is_completed: "false", exclude_approvals: "true" })
    })
    it("serializes donor, case and attempt filters for appointments", async () => {
        await getAppointments({ donor_id: "donor1", match_id: "match2", attempt_id: "attempt3", date_start: "2026-09-01", date_end: "2026-09-30" })
        const url = new URL(vi.mocked(api.get).mock.calls[0]![0], "https://example.test")
        expect(url.pathname).toBe("/appointments")
        expect(Object.fromEntries(url.searchParams)).toEqual({ donor_id: "donor1", match_id: "match2", attempt_id: "attempt3", date_start: "2026-09-01", date_end: "2026-09-30" })
    })
    it("attaches notes and documents to the exact case and attempt", async () => {
        await createMatchNote("match2", { source: "donor", content: "Follow up", attempt_id: "attempt3" })
        expect(api.post).toHaveBeenCalledWith("/matches/match2/notes", { source: "donor", content: "Follow up", attempt_id: "attempt3" })
        const file = new File(["synthetic"], "document.txt")
        await uploadMatchFile("match2", file, "donor", "attempt3")
        expect(api.upload).toHaveBeenCalledWith("/matches/match2/attachments?source=donor&attempt_id=attempt3", expect.any(FormData))
        expect(vi.mocked(api.upload).mock.calls[0]?.[1].get("file")).toBe(file)
    })
    it("uses exact lifecycle targets for completion and attempt changes", async () => {
        await completeMatch("match2", { outcome: "Completed" })
        expect(api.put).toHaveBeenCalledWith("/matches/match2/complete", { outcome: "Completed" })
        await updateMatchAttempt("match2", "attempt3", { status: "completed", outcome: "Completed" })
        expect(api.patch).toHaveBeenCalledWith("/matches/match2/attempts/attempt3", { status: "completed", outcome: "Completed" })
    })
})
