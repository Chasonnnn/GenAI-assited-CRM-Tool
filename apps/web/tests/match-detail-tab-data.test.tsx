import { describe, expect, it } from "vitest"
import { selectMatchDetailTabData } from "../app/(app)/intended-parents/matches/[id]/hooks/useMatchDetailTabData"
import type { MatchWork } from "@/lib/api/matches"

const work: MatchWork = {
    notes: [{ id: "note1", content: "Case note", created_at: "2026-09-05", source: "match" }],
    files: [{ id: "file1", filename: "donor.pdf", file_size: 12, created_at: "2026-09-05", source: "donor" }],
    tasks: [{ id: "task1", title: "Case task", due_date: null, is_completed: false, source: "match" }],
    activity: [{ id: "activity1", event_type: "note_added", description: "Case note added", actor_name: "Alex", created_at: "2026-09-05", source: "ip" }],
}

describe("exact case work selection", () => {
    it("uses canonical case activity without synthesizing duplicate rows from notes and files", () => {
        const selected = selectMatchDetailTabData(work, "all")
        expect(selected.filteredActivity).toEqual(work.activity)
        expect(selected.filteredNotes).toEqual(work.notes)
        expect(selected.filteredTasks).toEqual(work.tasks)
    })

    it("filters donor case work independently of the other party and shared case work", () => {
        expect(selectMatchDetailTabData(work, "donor")).toEqual({
            filteredNotes: [], filteredFiles: work.files, filteredTasks: [], filteredActivity: [],
        })
    })

    it("does not manufacture participant history while case work is unavailable", () => {
        expect(selectMatchDetailTabData(undefined, "all")).toEqual({
            filteredNotes: [], filteredFiles: [], filteredTasks: [], filteredActivity: [],
        })
    })
})
