import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, within } from "@testing-library/react"

import { FileUploadZone } from "@/components/FileUploadZone"

const mockUseAttachments = vi.fn()
const mockUseUploadAttachment = vi.fn()
const mockUseDownloadAttachment = vi.fn()
const mockUseDeleteAttachment = vi.fn()
const openMock = vi.fn()

vi.mock("react-dropzone", () => ({
    useDropzone: () => ({
        getRootProps: (props: Record<string, unknown> = {}) => props,
        getInputProps: (props: Record<string, unknown> = {}) => props,
        isDragActive: false,
        open: openMock,
    }),
}))

vi.mock("@/lib/hooks/use-attachments", () => ({
    useAttachments: (...args: unknown[]) => mockUseAttachments(...args),
    useUploadAttachment: () => mockUseUploadAttachment(),
    useDownloadAttachment: () => mockUseDownloadAttachment(),
    useDeleteAttachment: () => mockUseDeleteAttachment(),
}))

describe("FileUploadZone accessibility", () => {
    beforeEach(() => {
        openMock.mockReset()
        mockUseUploadAttachment.mockReturnValue({
            mutateAsync: vi.fn(),
            isPending: false,
        })
        mockUseDownloadAttachment.mockReturnValue({
            mutate: vi.fn(),
            isPending: false,
        })
        mockUseDeleteAttachment.mockReturnValue({
            mutate: vi.fn(),
            isPending: false,
        })
        mockUseAttachments.mockReturnValue({
            isLoading: false,
            data: [
                {
                    id: "att-1",
                    filename: "contract.pdf",
                    content_type: "application/pdf",
                    file_size: 1024,
                    scan_status: "clean",
                    quarantined: false,
                    uploaded_by_user_id: "user-1",
                    created_at: new Date().toISOString(),
                },
            ],
        })
    })

    it("renders upload area and attachments with semantic list structure", () => {
        render(<FileUploadZone surrogateId="surrogate-1" />)

        expect(screen.getByRole("button", { name: "Upload attachments" })).toBeInTheDocument()

        const list = screen.getByRole("list", { name: "Attachments" })
        expect(within(list).getAllByRole("listitem")).toHaveLength(1)

        expect(screen.getByRole("button", { name: "Download contract.pdf" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Delete contract.pdf" })).toBeInTheDocument()
    })

    it("supports keyboard activation and includes an aria-live region", () => {
        const { container } = render(<FileUploadZone surrogateId="surrogate-1" />)

        const uploadZone = screen.getByRole("button", { name: "Upload attachments" })
        fireEvent.keyDown(uploadZone, { key: "Enter" })
        fireEvent.keyDown(uploadZone, { key: " " })

        expect(openMock).toHaveBeenCalledTimes(2)
        expect(container.querySelector('[aria-live="polite"]')).toBeTruthy()
    })

    it("mentions the file name in delete confirmation", () => {
        render(<FileUploadZone surrogateId="surrogate-1" />)

        fireEvent.click(screen.getByRole("button", { name: "Delete contract.pdf" }))
        const dialog = screen.getByRole("alertdialog")
        expect(dialog).toHaveTextContent("This will permanently delete")
        expect(dialog).toHaveTextContent("contract.pdf")
    })

    it("renders the enhanced empty state when no attachments exist", () => {
        mockUseAttachments.mockReturnValue({
            isLoading: false,
            data: [],
        })

        render(<FileUploadZone surrogateId="surrogate-1" />)
        expect(screen.getByText("No attachments yet")).toBeInTheDocument()
        expect(
            screen.getByText("Upload documents to keep surrogate records complete.")
        ).toBeInTheDocument()
    })
})
