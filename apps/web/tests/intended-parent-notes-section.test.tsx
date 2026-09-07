import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { IntendedParentNotesSection } from "@/components/intended-parents/IntendedParentNotesSection"

const mocks = vi.hoisted(() => ({ notes: vi.fn(), create: vi.fn(), remove: vi.fn(), auth: vi.fn() }))
vi.mock("@/lib/auth-context", () => ({ useAuth: mocks.auth }))
vi.mock("@/lib/hooks/use-intended-parents", () => ({
    useIntendedParentNotes: mocks.notes,
    useCreateIntendedParentNote: () => ({ mutateAsync: mocks.create, isPending: false }),
    useDeleteIntendedParentNote: () => ({ mutateAsync: mocks.remove, isPending: false }),
}))
vi.mock("@/components/rich-text-editor", () => ({ RichTextEditor: ({ content, onChange, ariaLabel }: { content: string; onChange: (html: string) => void; ariaLabel: string }) => <textarea aria-label={ariaLabel} value={content} onChange={(event) => onChange(event.target.value)} /> }))

describe("IntendedParentNotesSection", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mocks.auth.mockReturnValue({ user: { user_id: "user-1", display_name: "Alex", role: "case_manager" } })
        mocks.notes.mockReturnValue({ data: [{ id: "note-1", author_id: "user-1", author_name: "Alex", content: "<p>Reviewed</p>", created_at: "2026-09-01T00:00:00Z" }] })
        mocks.create.mockResolvedValue({})
        mocks.remove.mockResolvedValue(undefined)
    })

    it("creates rich notes and deletes owned notes through existing IP endpoints", async () => {
        render(<IntendedParentNotesSection intendedParentId="ip-1" canEdit />)
        fireEvent.change(screen.getByRole("textbox", { name: "New intended parent note" }), { target: { value: "<p><strong>Follow up</strong></p>" } })
        fireEvent.click(screen.getByRole("button", { name: "Add Note" }))
        await waitFor(() => expect(mocks.create).toHaveBeenCalledWith({ id: "ip-1", data: { content: "<p><strong>Follow up</strong></p>" } }))
        fireEvent.click(screen.getByRole("button", { name: "Delete note by Alex" }))
        fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete Note" }))
        await waitFor(() => expect(mocks.remove).toHaveBeenCalledWith({ ipId: "ip-1", noteId: "note-1" }))
    })

    it("hides creation without edit permission and deletion for another author", () => {
        const { rerender } = render(<IntendedParentNotesSection intendedParentId="ip-1" canEdit={false} />)
        expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /Delete note/ })).not.toBeInTheDocument()
        mocks.auth.mockReturnValue({ user: { user_id: "user-2", role: "case_manager" } })
        rerender(<IntendedParentNotesSection intendedParentId="ip-1" canEdit />)
        expect(screen.getByRole("textbox")).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /Delete note/ })).not.toBeInTheDocument()
    })
})
