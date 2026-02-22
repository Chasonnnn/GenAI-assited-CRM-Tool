import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { FileUploadZone } from '@/components/FileUploadZone'

const mockUseAttachments = vi.fn()
const mockUpload = vi.fn()
const mockDownload = vi.fn()
const mockDelete = vi.fn()

vi.mock('@/lib/hooks/use-attachments', () => ({
    useAttachments: (id: string) => mockUseAttachments(id),
    useUploadAttachment: () => ({ mutateAsync: mockUpload }),
    useDownloadAttachment: () => ({ mutate: mockDownload }),
    useDeleteAttachment: () => ({ mutate: mockDelete }),
}))

// Mock react-dropzone to behave predictably in tests
vi.mock('react-dropzone', async (importOriginal) => {
    const actual = await importOriginal()
    return {
        ...actual,
        useDropzone: (_args: unknown) => ({
            getRootProps: (moreProps: Record<string, unknown>) => ({
                role: 'presentation', // Default unless we override
                tabIndex: 0,
                ...moreProps,
            }),
            getInputProps: () => ({
                style: { display: 'none' },
                type: 'file',
            }),
            isDragActive: false,
            open: vi.fn(),
        }),
    }
})

describe('FileUploadZone', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockUseAttachments.mockReturnValue({
            data: [],
            isLoading: false
        })
    })

    it('renders with accessible dropzone label', () => {
        render(<FileUploadZone surrogateId="test-id" />)

        // This should fail initially because we haven't added aria-label="File upload zone"
        // and role="button" might not be there if we haven't added it explicitly in getRootProps
        // But let's check for the existence of an element with the label we intend to add.
        const dropzone = screen.queryByRole('button', { name: /file upload zone/i })
        expect(dropzone).toBeInTheDocument()
    })

    it('renders attachments as a semantic list', () => {
        mockUseAttachments.mockReturnValue({
            data: [
                {
                    id: '1',
                    filename: 'test.pdf',
                    file_size: 1024,
                    scan_status: 'clean',
                    quarantined: false
                }
            ],
            isLoading: false
        })

        render(<FileUploadZone surrogateId="test-id" />)

        // This should fail initially because it's a div, not ul/li
        const list = screen.queryByRole('list')
        expect(list).toBeInTheDocument()

        const items = screen.queryAllByRole('listitem')
        expect(items).toHaveLength(1)
    })
})
