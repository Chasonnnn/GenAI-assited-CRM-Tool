import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import FormsListPage from '../app/(app)/automation/forms/page'
import { FORM_TEMPLATES } from '@/lib/forms/templates'

const mockPush = vi.fn()
const mockCreateForm = vi.fn()
const mockSetFormMappings = vi.fn()

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: mockPush }),
}))

vi.mock('@/lib/hooks/use-forms', () => ({
    useForms: () => ({ data: [], isLoading: false }),
    useCreateForm: () => ({ mutateAsync: mockCreateForm, isPending: false }),
    useSetFormMappings: () => ({ mutateAsync: mockSetFormMappings, isPending: false }),
}))

describe('FormsListPage templates', () => {
    beforeEach(() => {
        mockCreateForm.mockReset()
        mockSetFormMappings.mockReset()
        mockPush.mockReset()
    })

    it('creates a new form from the platform template', async () => {
        mockCreateForm.mockResolvedValue({ id: 'form-123' })
        mockSetFormMappings.mockResolvedValue([])

        render(<FormsListPage />)

        fireEvent.click(screen.getByRole('tab', { name: /form templates/i }))
        fireEvent.click(screen.getByRole('button', { name: /use template/i }))

        await waitFor(() => expect(mockCreateForm).toHaveBeenCalled())
        expect(mockCreateForm).toHaveBeenCalledWith(FORM_TEMPLATES[0].payload)

        if (FORM_TEMPLATES[0].mappings?.length) {
            await waitFor(() =>
                expect(mockSetFormMappings).toHaveBeenCalledWith({
                    formId: 'form-123',
                    mappings: FORM_TEMPLATES[0].mappings,
                }),
            )
        }

        await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/automation/forms/form-123'))
    })
})
