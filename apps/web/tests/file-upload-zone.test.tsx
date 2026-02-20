import { render, screen } from "@testing-library/react"
import { FileUploadZone } from "@/components/FileUploadZone"
import { vi, describe, it, expect, beforeEach } from "vitest"

// Mock the hooks
const mockUpload = vi.fn()
const mockDownload = vi.fn()
const mockDelete = vi.fn()
const mockAttachments = [
    {
        id: "1",
        filename: "test.pdf",
        file_size: 1024,
        scan_status: "clean",
        quarantined: false,
    },
    {
        id: "2",
        filename: "image.png",
        file_size: 2048,
        scan_status: "pending",
        quarantined: true,
    },
]

vi.mock("@/lib/hooks/use-attachments", () => ({
    useAttachments: () => ({
        data: mockAttachments,
        isLoading: false,
    }),
    useUploadAttachment: () => ({
        mutateAsync: mockUpload,
        isPending: false,
    }),
    useDownloadAttachment: () => ({
        mutate: mockDownload,
        isPending: false,
    }),
    useDeleteAttachment: () => ({
        mutate: mockDelete,
        isPending: false,
    }),
}))

describe("FileUploadZone", () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it("renders the dropzone with accessibility attributes", () => {
        render(<FileUploadZone surrogateId="test-id" />)

        // Find the dropzone. It should be a button role with an aria-label.
        const dropText = screen.getByText(/Drag & drop files here/i)
        const dropzone = dropText.closest("div")

        expect(dropzone).toBeInTheDocument()

        // We check if it has the correct role and aria-label
        const button = screen.queryByRole("button", { name: /file upload zone/i })

        expect(button).toBeInTheDocument()
    })

    it("renders attachments as a list", () => {
        render(<FileUploadZone surrogateId="test-id" />)

        // Verify attachments are present
        expect(screen.getByText("test.pdf")).toBeInTheDocument()
        expect(screen.getByText("image.png")).toBeInTheDocument()

        // Check for semantic list structure (ul > li)
        const list = screen.getByRole("list")
        expect(list).toBeInTheDocument()

        const items = screen.getAllByRole("listitem")
        expect(items).toHaveLength(2)
    })

    it("allows keyboard interaction on dropzone", () => {
        render(<FileUploadZone surrogateId="test-id" />)

        // We can simulate keyboard events on the dropzone if we can find it.
        const dropText = screen.getByText(/Drag & drop files here/i)
        const dropzone = dropText.closest("div")

        if (dropzone) {
            // Dropzone typically handles click, we want to ensure it handles keyboard enter/space
            // if it's focused.
            // We can check if it has tabIndex="0"
            expect(dropzone).toHaveAttribute("tabIndex", "0")
        }
    })
})
