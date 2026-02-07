import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import FormsListPage from '../app/(app)/automation/forms/page'
import { FORM_TEMPLATES } from '@/lib/forms/templates'

const mockPush = vi.fn()
const mockCreateForm = vi.fn()
const mockSetFormMappings = vi.fn()
const mockUseTemplate = vi.fn()
const mockDeleteForm = vi.fn()

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: mockPush }),
}))

const mockTemplates = FORM_TEMPLATES.map((template) => ({
    ...template,
    updated_at: new Date().toISOString(),
    published_at: null,
}))

vi.mock('@/lib/hooks/use-forms', () => ({
    useForms: () => ({ data: [], isLoading: false }),
    useFormTemplates: () => ({ data: mockTemplates, isLoading: false }),
    useUseFormTemplate: () => ({ mutateAsync: mockUseTemplate, isPending: false }),
    useCreateForm: () => ({ mutateAsync: mockCreateForm, isPending: false }),
    useDeleteForm: () => ({ mutateAsync: mockDeleteForm, isPending: false }),
    useSetFormMappings: () => ({ mutateAsync: mockSetFormMappings, isPending: false }),
}))

describe('FormsListPage templates', () => {
    beforeEach(() => {
        mockCreateForm.mockReset()
        mockSetFormMappings.mockReset()
        mockPush.mockReset()
        mockUseTemplate.mockReset()
    })

    it('creates a new form from the platform template', async () => {
        mockUseTemplate.mockResolvedValue({ id: 'form-123' })

        render(<FormsListPage />)

        fireEvent.click(screen.getByRole('tab', { name: /form templates/i }))
        fireEvent.click(screen.getByRole('button', { name: /use template/i }))

        await waitFor(() => expect(mockUseTemplate).toHaveBeenCalled())
        expect(mockUseTemplate).toHaveBeenCalledWith({
            templateId: mockTemplates[0].id,
            payload: { name: mockTemplates[0].name },
        })

        await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/automation/forms/form-123'))
    })
})
