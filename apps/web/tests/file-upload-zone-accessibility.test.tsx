import { render, screen, act } from "@testing-library/react"
import { FileUploadZone } from "@/components/FileUploadZone"
import { vi, describe, it, expect, beforeEach } from "vitest"

// Mocks
const mockUseAttachments = vi.fn()
const mockUploadAttachment = { mutateAsync: vi.fn(), isPending: false }
const mockDownloadAttachment = { mutate: vi.fn(), isPending: false }
const mockDeleteAttachment = { mutate: vi.fn(), isPending: false }

vi.mock("@/lib/hooks/use-attachments", () => ({
    useAttachments: (id: string) => mockUseAttachments(id),
    useUploadAttachment: () => mockUploadAttachment,
    useDownloadAttachment: () => mockDownloadAttachment,
    useDeleteAttachment: () => mockDeleteAttachment,
}))

// Mock hooks
const mockUseDropzone = vi.fn()
vi.mock("react-dropzone", () => ({
    useDropzone: (props: any) => mockUseDropzone(props),
}))

describe("FileUploadZone Accessibility", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockUseAttachments.mockReturnValue({
            data: [],
            isLoading: false,
        })
        mockUseDropzone.mockReturnValue({
            getRootProps: () => ({ role: "button" }),
            getInputProps: () => ({ type: "file", style: { display: "none" } }),
            isDragActive: false,
            open: vi.fn(),
        })
    })

    it("renders attachments as a semantic list", () => {
        mockUseAttachments.mockReturnValue({
            data: [
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
                    quarantined: false,
                },
            ],
            isLoading: false,
        })

        render(<FileUploadZone surrogateId="123" />)

        const list = screen.getByRole("list")
        expect(list).toBeInTheDocument()
        expect(list.tagName).toBe("UL")

        const items = screen.getAllByRole("listitem")
        expect(items).toHaveLength(2)
        expect(items[0].tagName).toBe("LI")
    })

    it("renders clear error button with accessible label when error occurs", async () => {
        let onDropCallback: (files: File[]) => void = () => {}
        mockUseDropzone.mockImplementation(({ onDrop }) => {
            onDropCallback = onDrop
            return {
                getRootProps: () => ({ role: "button" }),
                getInputProps: () => ({ type: "file", style: { display: "none" } }),
                isDragActive: false,
                open: vi.fn(),
            }
        })

        render(<FileUploadZone surrogateId="123" />)

        // Trigger onDrop with an invalid file (e.g. .exe)
        const file = new File(["dummy content"], "test.exe", { type: "application/x-msdownload" })

        await act(async () => {
            onDropCallback([file])
        })

        const errorButton = screen.getByRole("button", { name: /clear error/i })
        expect(errorButton).toBeInTheDocument()
    })
})
