import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { FileUploadZone } from '../components/FileUploadZone'
import { useAttachments, useUploadAttachment, useDownloadAttachment, useDeleteAttachment } from '@/lib/hooks/use-attachments'

// Mock the hooks
vi.mock('@/lib/hooks/use-attachments', () => ({
    useAttachments: vi.fn(),
    useUploadAttachment: vi.fn(),
    useDownloadAttachment: vi.fn(),
    useDeleteAttachment: vi.fn(),
}))

describe('FileUploadZone Accessibility', () => {
    beforeEach(() => {
        // Default mocks
        vi.mocked(useAttachments).mockReturnValue({
            data: [
                {
                    id: '1',
                    filename: 'test-file.pdf',
                    file_size: 1024,
                    scan_status: 'clean',
                    quarantined: false,
                    created_at: new Date().toISOString(),
                },
            ],
            isLoading: false,
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
        } as any)

        vi.mocked(useUploadAttachment).mockReturnValue({
            mutateAsync: vi.fn(),
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
        } as any)

        vi.mocked(useDownloadAttachment).mockReturnValue({
            mutate: vi.fn(),
            isPending: false,
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
        } as any)

        vi.mocked(useDeleteAttachment).mockReturnValue({
            mutate: vi.fn(),
            isPending: false,
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
        } as any)
    })

    it('renders a list of attachments using semantic list elements', () => {
        render(<FileUploadZone surrogateId="surrogate-1" />)

        const list = screen.getByRole('list')
        expect(list).toBeInTheDocument()

        const items = screen.getAllByRole('listitem')
        expect(items).toHaveLength(1)
        expect(items[0]).toHaveTextContent('test-file.pdf')
    })

    it('renders the dropzone with an accessible label', () => {
        render(<FileUploadZone surrogateId="surrogate-1" />)

        // The dropzone should be focusable and have a label
        // react-dropzone usually applies role="presentation" to the root div if there is an input inside
        // However, for keyboard users, the root div receives focus.
        // We want to ensure it has an aria-label if it's interactive.
        // Let's check if we can find it by label.

        // Note: We are adding aria-label to the root div in our implementation plan.
        const dropzone = screen.getByLabelText(/file upload zone/i) // This might fail if role is presentation, but let's see.
        expect(dropzone).toBeInTheDocument()
    })

    it('renders the dropzone with tabIndex="0" for keyboard accessibility', () => {
        render(<FileUploadZone surrogateId="surrogate-1" />)
        const dropzone = screen.getByLabelText(/file upload zone/i)
        expect(dropzone).toHaveAttribute('tabIndex', '0')
    })

    it('renders action buttons with aria-labels and hidden icons', () => {
        render(<FileUploadZone surrogateId="surrogate-1" />)

        const downloadButton = screen.getByRole('button', { name: /download test-file.pdf/i })
        expect(downloadButton).toBeInTheDocument()

        const deleteButton = screen.getByRole('button', { name: /delete test-file.pdf/i })
        expect(deleteButton).toBeInTheDocument()

        // Check for hidden icons inside buttons
        // We can't easily query by aria-hidden="true" with testing-library queries,
        // but we can check the SVG inside the button.
        const downloadIcon = downloadButton.querySelector('svg')
        expect(downloadIcon).toHaveAttribute('aria-hidden', 'true')

        const deleteIcon = deleteButton.querySelector('svg')
        expect(deleteIcon).toHaveAttribute('aria-hidden', 'true')
    })

    it('renders status badge icons as hidden', () => {
        render(<FileUploadZone surrogateId="surrogate-1" />)

        // Find the "Clean" badge
        const badge = screen.getByText('Clean').closest('div') // Badge renders as div usually
        expect(badge).toBeInTheDocument()

        const icon = badge?.querySelector('svg')
        expect(icon).toHaveAttribute('aria-hidden', 'true')
    })

})
