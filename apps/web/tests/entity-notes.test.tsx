import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { EntityNotes } from "@/components/notes/EntityNotes"

vi.mock("@/components/rich-text-editor", () => ({
    RichTextEditor: ({ content, onChange, ariaLabel, enableEmojiPicker }: { content: string; onChange: (html: string) => void; ariaLabel: string; enableEmojiPicker: boolean }) => <textarea aria-label={ariaLabel} value={content} onChange={(event) => onChange(event.target.value)} data-emoji={enableEmojiPicker} />,
}))
const note = { id: "note-1", author_id: "user-1", author_name: "Alex", body: "<p>Screening complete</p>", created_at: "2026-09-01T12:00:00Z" }
const add = vi.fn()
const remove = vi.fn()
const props = { notes: [note], onAddNote: add, onDeleteNote: remove, isSubmitting: false }

describe("EntityNotes", () => {
    beforeEach(() => { vi.clearAllMocks(); add.mockResolvedValue(undefined); remove.mockResolvedValue(undefined) })

    it("shares author identity, rich preview, and machine-readable timestamps", () => {
        render(<EntityNotes {...props} />)
        expect(screen.getByText("Alex")).toBeInTheDocument()
        expect(screen.getByText("Screening complete")).toBeInTheDocument()
        expect(screen.getByText(/Sep 1, 2026/).closest("time")).toHaveAttribute("dateTime", note.created_at)
        expect(screen.getByRole("textbox", { name: "New note" })).toHaveAttribute("data-emoji", "true")
    })

    it("preserves the rich-text draft on failure and clears it after successful retry", async () => {
        add.mockRejectedValueOnce(new Error("Save failed"))
        render(<EntityNotes {...props} />)
        const editor = screen.getByRole("textbox", { name: "New note" })
        fireEvent.change(editor, { target: { value: "<p><strong>Follow up</strong></p>" } })
        fireEvent.click(screen.getByRole("button", { name: "Add Note" }))
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Save failed"))
        expect(editor).toHaveValue("<p><strong>Follow up</strong></p>")
        fireEvent.click(screen.getByRole("button", { name: "Add Note" }))
        await waitFor(() => expect(editor).toHaveValue(""))
        expect(add).toHaveBeenLastCalledWith("<p><strong>Follow up</strong></p>")
    })

    it("rejects empty rich-text documents", () => {
        render(<EntityNotes {...props} />)
        fireEvent.change(screen.getByRole("textbox"), { target: { value: "<p>&nbsp;</p>" } })
        expect(screen.getByRole("button", { name: "Add Note" })).toBeDisabled()
    })

    it("requires a reviewable delete dialog and retains it on failure", async () => {
        remove.mockRejectedValueOnce(new Error("Delete failed"))
        render(<EntityNotes {...props} />)
        fireEvent.click(screen.getByRole("button", { name: "Delete note by Alex" }))
        expect(remove).not.toHaveBeenCalled()
        const dialog = screen.getByRole("dialog")
        fireEvent.click(within(dialog).getByRole("button", { name: "Delete Note" }))
        await waitFor(() => expect(within(dialog).getByRole("alert")).toHaveTextContent("Delete failed"))
        fireEvent.click(within(dialog).getByRole("button", { name: "Delete Note" }))
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
        expect(remove).toHaveBeenLastCalledWith(note.id)
    })

    it("honors create/delete permissions and supports a current-user author fallback", () => {
        render(<EntityNotes {...props} notes={[{ ...note, author_name: null }]} currentUser={{ id: "user-1", name: "Alex" }} canCreate={false} canDeleteNote={() => false} />)
        expect(screen.getByText("Alex")).toBeInTheDocument()
        expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /Delete note/ })).not.toBeInTheDocument()
    })

    it("renders loading, retry, and empty states", () => {
        const retry = vi.fn()
        const { rerender } = render(<EntityNotes {...props} status="loading" />)
        expect(screen.getByRole("status")).toHaveTextContent("Loading notes")
        rerender(<EntityNotes {...props} status="error" onRetry={retry} />)
        fireEvent.click(screen.getByRole("button", { name: "Retry notes" }))
        expect(retry).toHaveBeenCalledOnce()
        rerender(<EntityNotes {...props} notes={[]} />)
        expect(screen.getByText("No notes yet.")).toBeInTheDocument()
    })
})
