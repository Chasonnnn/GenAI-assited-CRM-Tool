import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { EntityDocuments } from "@/components/documents/EntityDocuments"
import type { Attachment } from "@/lib/api/attachments"

const attachment: Attachment = {
    id: "attachment-1", filename: "record.pdf", file_size: 1024,
    content_type: "application/pdf", scan_status: "clean", quarantined: false,
    uploaded_by_user_id: "user-1", created_at: "2026-09-05T12:00:00Z",
}

function props() {
    return {
        attachments: [attachment], isLoading: false, onRetry: vi.fn(),
        onUpload: vi.fn().mockResolvedValue(undefined), onDownload: vi.fn(),
        onDelete: vi.fn().mockResolvedValue(undefined),
        isUploading: false, isDownloading: false, isDeleting: false,
    }
}

describe("shared record documents", () => {
    it("uploads a file through the subject adapter", async () => {
        const callbacks = props()
        render(<EntityDocuments {...callbacks} inputLabel="Choose documents" />)
        const file = new File(["%PDF-1.4"], "new.pdf", { type: "application/pdf" })
        fireEvent.change(screen.getByLabelText("Choose documents"), { target: { files: [file] } })
        await waitFor(() => expect(callbacks.onUpload).toHaveBeenCalledWith(file))
    })

    it("keeps a failed delete reviewable and supports retry", async () => {
        const callbacks = props()
        callbacks.onDelete.mockRejectedValueOnce(new Error("Delete failed"))
        render(<EntityDocuments {...callbacks} />)
        fireEvent.click(screen.getByRole("button", { name: "Delete record.pdf" }))
        fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Delete" }))
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Delete failed"))
        expect(screen.getByRole("alertdialog")).toBeInTheDocument()
        fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Delete" }))
        await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument())
        expect(callbacks.onDelete).toHaveBeenNthCalledWith(2, attachment.id)
    })

    it.each(["infected", "error"])("blocks downloads for %s files even without quarantine", (scan_status) => {
        render(<EntityDocuments {...props()} attachments={[{ ...attachment, scan_status }]} />)
        expect(screen.getByRole("button", { name: "Download record.pdf" })).toBeDisabled()
    })

    it("shows the final scan result for quarantined infected files", () => {
        render(<EntityDocuments {...props()} attachments={[{ ...attachment, scan_status: "infected", quarantined: true }]} />)
        expect(screen.getByText("Infected")).toBeInTheDocument()
        expect(screen.queryByText("Scanning")).not.toBeInTheDocument()
    })

    it("keeps downloads available while hiding mutation controls for readers", () => {
        const callbacks = props()
        render(<EntityDocuments {...callbacks} canEdit={false} />)
        expect(screen.queryByRole("button", { name: "Upload attachments" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Delete record.pdf" })).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Download record.pdf" }))
        expect(callbacks.onDownload).toHaveBeenCalledWith(attachment.id)
    })

    it("renders loading, error with retry, and empty states", () => {
        const callbacks = props()
        const { rerender } = render(<EntityDocuments {...callbacks} isLoading />)
        expect(screen.getByRole("status")).toHaveTextContent("Loading attachments")
        rerender(<EntityDocuments {...callbacks} isError />)
        expect(screen.getByText("Failed to load documents.")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(callbacks.onRetry).toHaveBeenCalledOnce()
        rerender(<EntityDocuments {...callbacks} attachments={[]} />)
        expect(screen.getByText("No attachments yet")).toBeInTheDocument()
    })
})
