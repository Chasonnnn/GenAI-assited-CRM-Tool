import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { CSVUpload } from '@/components/import/CSVUpload'

const mockPreviewImport = vi.fn()

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({ user: { role: 'admin', user_id: 'u1' } }),
}))

vi.mock('@/lib/hooks/use-import', () => ({
    usePreviewImport: () => ({ mutateAsync: mockPreviewImport, isPending: false }),
    useSubmitImport: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useApproveImport: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useAiMapImport: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

function suggestion(csvColumn: string, field: string, transformation: string | null) {
    return {
        csv_column: csvColumn,
        suggested_field: field,
        confidence: 0.9,
        confidence_level: 'high',
        transformation,
        sample_values: ['sample'],
        reason: 'Similar column name match',
        warnings: [],
        default_action: null,
        needs_inversion: false,
    }
}

const previewData = {
    import_id: 'import-1',
    total_rows: 1,
    sample_rows: [{ 'Full Name': 'Test User', 'Lead Source Notes': 'met at fair', Platform: 'fb', Legacy: 'x' }],
    detected_encoding: 'utf-8',
    detected_delimiter: ',',
    has_header: true,
    column_suggestions: [
        suggestion('Full Name', 'full_name', null),
        suggestion('Lead Source Notes', 'source', 'source_channel_guess'),
        suggestion('Platform', 'source', 'source_meta_platform'),
        suggestion('Legacy', 'state', 'retired_transform'),
    ],
    matched_count: 4,
    unmatched_count: 0,
    matching_templates: [],
    available_fields: ['full_name', 'source', 'state'],
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

describe('CSVUpload transform select labels', () => {
    beforeEach(() => {
        mockPreviewImport.mockReset()
        mockPreviewImport.mockResolvedValue(previewData)
    })

    it('labels the source transforms that detection suggests and never shows Unknown selection', async () => {
        const { container } = render(<CSVUpload />)
        const fileInput = container.querySelector<HTMLInputElement>('input[type="file"]')
        const file = new File(['Full Name,Lead Source Notes,Platform,Legacy'], 'surrogates.csv', {
            type: 'text/csv',
        })
        fireEvent.change(fileInput as HTMLInputElement, { target: { files: [file] } })
        await waitFor(() => expect(mockPreviewImport).toHaveBeenCalled())

        expect(await screen.findByRole('combobox', { name: 'Full Name transform' })).toHaveTextContent('No transform')
        expect(screen.getByRole('combobox', { name: 'Lead Source Notes transform' })).toHaveTextContent('Detect channel')
        expect(screen.getByRole('combobox', { name: 'Platform transform' })).toHaveTextContent('Meta platform')
        expect(screen.getByRole('combobox', { name: 'Legacy transform' })).toHaveTextContent('Custom transform')
        expect(screen.queryByText('Unknown selection')).not.toBeInTheDocument()
    })
})
