import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, within } from "@testing-library/react"

import { FileUploadZone } from "@/components/FileUploadZone"

const mockUseAttachments = vi.fn()
const mockUseUploadAttachment = vi.fn()
const mockUseDownloadAttachment = vi.fn()
const mockUseDeleteAttachment = vi.fn()

vi.mock("react-dropzone", () => ({
    useDropzone: () => ({
        getRootProps: (props: Record<string, unknown> = {}) => props,
        getInputProps: (props: Record<string, unknown> = {}) => props,
        isDragActive: false,
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

    it("hides decorative icons from screen readers", () => {
        const { container } = render(<FileUploadZone surrogateId="surrogate-1" />)

        const iconSelectors = [
            "svg.lucide-upload",
            "svg.lucide-file",
            "svg.lucide-circle-check",
            "svg.lucide-download",
            "svg.lucide-trash2",
        ]

        iconSelectors.forEach((selector) => {
            const icon = container.querySelector(selector)
            expect(icon).toBeTruthy()
            expect(icon).toHaveAttribute("aria-hidden", "true")
        })
    })
})
