import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { CSVUpload } from '@/components/import/CSVUpload'

const mockPreviewImport = vi.fn()
const mockSubmitImport = vi.fn()
const mockApproveImport = vi.fn()
const mockAiMap = vi.fn()

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({ user: { role: 'admin', user_id: 'u1' } }),
}))

vi.mock('@/lib/hooks/use-import', () => ({
    usePreviewImport: () => ({ mutateAsync: mockPreviewImport, isPending: false }),
    useSubmitImport: () => ({ mutateAsync: mockSubmitImport, isPending: false }),
    useApproveImport: () => ({ mutateAsync: mockApproveImport, isPending: false }),
    useAiMapImport: () => ({ mutateAsync: mockAiMap, isPending: false }),
}))

describe('CSVUpload created_at backdating', () => {
    const previewData = {
        import_id: 'import-1',
        total_rows: 3,
        sample_rows: [
            {
                full_name: 'Test User',
                email: 'test@example.com',
                created_time: '2024-01-01T10:00:00Z',
            },
        ],
        detected_encoding: 'utf-8',
        detected_delimiter: ',',
        has_header: true,
        column_suggestions: [
            {
                csv_column: 'full_name',
                suggested_field: 'full_name',
                confidence: 1,
                confidence_level: 'high',
                transformation: null,
                sample_values: ['Test User'],
                reason: 'Exact match',
                warnings: [],
                default_action: null,
                needs_inversion: false,
            },
            {
                csv_column: 'email',
                suggested_field: 'email',
                confidence: 1,
                confidence_level: 'high',
                transformation: null,
                sample_values: ['test@example.com'],
                reason: 'Exact match',
                warnings: [],
                default_action: null,
                needs_inversion: false,
            },
            {
                csv_column: 'created_time',
                suggested_field: 'created_at',
                confidence: 0.98,
                confidence_level: 'high',
                transformation: null,
                sample_values: ['2024-01-01T10:00:00Z'],
                reason: 'Exact match',
                warnings: [],
                default_action: null,
                needs_inversion: false,
            },
        ],
        matched_count: 3,
        unmatched_count: 0,
        matching_templates: [],
        available_fields: ['full_name', 'email', 'created_at'],
        duplicate_emails_db: 0,
        duplicate_emails_csv: 0,
        validation_errors: 0,
        date_ambiguity_warnings: [],
        ai_available: false,
        auto_applied_template: null,
        template_unknown_column_behavior: null,
        ai_auto_triggered: false,
        ai_mapped_columns: [],
    }

    beforeEach(() => {
        mockPreviewImport.mockResolvedValue(previewData)
        mockSubmitImport.mockResolvedValue({ import_id: 'import-1', status: 'pending' })
        mockApproveImport.mockResolvedValue({ import_id: 'import-1', status: 'approved' })
        mockAiMap.mockResolvedValue({ suggestions: [] })
        mockPreviewImport.mockClear()
        mockSubmitImport.mockClear()
        mockApproveImport.mockClear()
        mockAiMap.mockClear()
    })

    it('defaults to backdating created_at when mapped and includes it on submit', async () => {
        const { container } = render(<CSVUpload />)
        const fileInput = container.querySelector<HTMLInputElement>('input[type="file"]')
        expect(fileInput).not.toBeNull()

        const file = new File(['full_name,email,created_time'], 'surrogates.csv', {
            type: 'text/csv',
        })
        fireEvent.change(fileInput as HTMLInputElement, { target: { files: [file] } })

        await waitFor(() => expect(mockPreviewImport).toHaveBeenCalled())

        await screen.findByText(/Use CSV created_at values/i)

        fireEvent.click(screen.getByRole('button', { name: 'Submit Import' }))

        await waitFor(() => {
            expect(mockSubmitImport).toHaveBeenCalledWith(
                expect.objectContaining({
                    importId: 'import-1',
                    payload: expect.objectContaining({
                        backdate_created_at: true,
                    }),
                })
            )
        })
    })
})
