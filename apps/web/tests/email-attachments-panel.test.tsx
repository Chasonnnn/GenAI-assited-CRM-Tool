import * as React from "react"
import { describe, expect, it, beforeEach, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import { EmailAttachmentsPanel } from "@/components/email/EmailAttachmentsPanel"

const mockUseAttachments = vi.fn()
const mockUseUploadAttachment = vi.fn()

vi.mock("react-dropzone", () => ({
    useDropzone: () => ({
        getRootProps: () => ({}),
        getInputProps: () => ({}),
        isDragActive: false,
    }),
}))

vi.mock("@/lib/hooks/use-attachments", () => ({
    useAttachments: (surrogateId: string) => mockUseAttachments(surrogateId),
    useUploadAttachment: () => mockUseUploadAttachment(),
}))

describe("EmailAttachmentsPanel", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockUseUploadAttachment.mockReturnValue({
            mutateAsync: vi.fn(),
            isPending: false,
        })
    })

    it("marks selection as blocking when a non-clean attachment is selected", async () => {
        mockUseAttachments.mockReturnValue({
            data: [
                {
                    id: "att-clean",
                    filename: "clean.pdf",
                    content_type: "application/pdf",
                    file_size: 1024,
                    scan_status: "clean",
                    quarantined: false,
                    uploaded_by_user_id: "u1",
                    created_at: new Date().toISOString(),
                },
                {
                    id: "att-pending",
                    filename: "pending.pdf",
                    content_type: "application/pdf",
                    file_size: 2048,
                    scan_status: "pending",
                    quarantined: true,
                    uploaded_by_user_id: "u1",
                    created_at: new Date().toISOString(),
                },
            ],
            isLoading: false,
        })

        const onSelectionChange = vi.fn()
        render(<EmailAttachmentsPanel surrogateId="sur-1" onSelectionChange={onSelectionChange} />)

        fireEvent.click(screen.getByLabelText("Select pending.pdf"))

        await waitFor(() => {
            expect(onSelectionChange).toHaveBeenLastCalledWith(
                expect.objectContaining({
                    selectedAttachmentIds: ["att-pending"],
                    hasBlockingAttachments: true,
                })
            )
        })
    })

    it("keeps selection sendable when only clean attachments are selected", async () => {
        mockUseAttachments.mockReturnValue({
            data: [
                {
                    id: "att-clean",
                    filename: "clean.pdf",
                    content_type: "application/pdf",
                    file_size: 1024,
                    scan_status: "clean",
                    quarantined: false,
                    uploaded_by_user_id: "u1",
                    created_at: new Date().toISOString(),
                },
            ],
            isLoading: false,
        })

        const onSelectionChange = vi.fn()
        render(<EmailAttachmentsPanel surrogateId="sur-1" onSelectionChange={onSelectionChange} />)

        fireEvent.click(screen.getByLabelText("Select clean.pdf"))

        await waitFor(() => {
            expect(onSelectionChange).toHaveBeenLastCalledWith(
                expect.objectContaining({
                    selectedAttachmentIds: ["att-clean"],
                    hasBlockingAttachments: false,
                })
            )
        })
    })

    it("clears selected attachments when the surrogate changes", async () => {
        mockUseAttachments.mockImplementation((surrogateId: string) => ({
            data: [
                {
                    id: surrogateId === "sur-1" ? "att-one" : "att-two",
                    filename: surrogateId === "sur-1" ? "one.pdf" : "two.pdf",
                    content_type: "application/pdf",
                    file_size: 1024,
                    scan_status: "clean",
                    quarantined: false,
                    uploaded_by_user_id: "u1",
                    created_at: new Date().toISOString(),
                },
            ],
            isLoading: false,
        }))

        const onSelectionChange = vi.fn()
        const { rerender } = render(
            <EmailAttachmentsPanel surrogateId="sur-1" onSelectionChange={onSelectionChange} />,
        )

        fireEvent.click(screen.getByLabelText("Select one.pdf"))
        await waitFor(() => {
            expect(onSelectionChange).toHaveBeenLastCalledWith(
                expect.objectContaining({
                    selectedAttachmentIds: ["att-one"],
                }),
            )
        })

        rerender(
            <EmailAttachmentsPanel surrogateId="sur-2" onSelectionChange={onSelectionChange} />,
        )

        await waitFor(() => {
            expect(onSelectionChange).toHaveBeenLastCalledWith(
                expect.objectContaining({
                    selectedAttachmentIds: [],
                }),
            )
        })
        expect(screen.getByText("0 selected")).toBeInTheDocument()
    })

    it("starts valid batch uploads without waiting for earlier files to finish", async () => {
        mockUseAttachments.mockReturnValue({
            data: [],
            isLoading: false,
        })

        let resolveFirstUpload: ((value: { id: string }) => void) | null = null
        const firstUpload = new Promise<{ id: string }>((resolve) => {
            resolveFirstUpload = resolve
        })
        const mutateAsync = vi
            .fn()
            .mockReturnValueOnce(firstUpload)
            .mockResolvedValueOnce({ id: "att-two" })
        mockUseUploadAttachment.mockReturnValue({
            mutateAsync,
            isPending: false,
        })

        const onSelectionChange = vi.fn()
        render(<EmailAttachmentsPanel surrogateId="sur-1" onSelectionChange={onSelectionChange} />)

        const fileInput = screen.getByLabelText("Choose email attachments to upload")
        expect(fileInput).toHaveAttribute("type", "file")

        fireEvent.change(fileInput, {
            target: {
                files: [
                    new File(["one"], "one.pdf", { type: "application/pdf" }),
                    new File(["two"], "two.pdf", { type: "application/pdf" }),
                ],
            },
        })

        await waitFor(() => {
            expect(mutateAsync).toHaveBeenCalledTimes(2)
        })

        resolveFirstUpload?.({ id: "att-one" })

        await waitFor(() => {
            expect(onSelectionChange).toHaveBeenLastCalledWith(
                expect.objectContaining({
                    selectedAttachmentIds: ["att-one", "att-two"],
                })
            )
        })
    })
})
