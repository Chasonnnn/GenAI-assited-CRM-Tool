import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import FormBuilderPage from '../app/(app)/automation/forms/[id]/page'

const mockPush = vi.fn()
const mockUseForm = vi.fn()
const mockUseFormMappings = vi.fn()

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: mockPush }),
    useParams: () => ({ id: 'new' }),
}))

vi.mock('@/lib/hooks/use-forms', () => ({
    useForm: (id: string | null) => mockUseForm(id),
    useFormMappings: (id: string | null) => mockUseFormMappings(id),
    useCreateForm: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUpdateForm: () => ({ mutateAsync: vi.fn(), isPending: false }),
    usePublishForm: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useSetFormMappings: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUploadFormLogo: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({ user: { org_id: 'org-1' } }),
}))

vi.mock('@/lib/hooks/use-signature', () => ({
    useOrgSignature: () => ({ data: null }),
}))

vi.mock('sonner', () => ({
    toast: {
        success: vi.fn(),
        error: vi.fn(),
    },
}))

describe('FormBuilderPage templates', () => {
    beforeEach(() => {
        mockUseForm.mockReturnValue({ data: null, isLoading: false })
        mockUseFormMappings.mockReturnValue({ data: [], isLoading: false })
        mockPush.mockReset()
    })

    it('applies the Jotform surrogate intake template', () => {
        render(<FormBuilderPage />)

        fireEvent.click(
            screen.getByRole('button', { name: /use jotform surrogate intake template/i }),
        )

        expect(screen.getByText('Surrogate Information')).toBeInTheDocument()
        expect(screen.getByText('Decisions')).toBeInTheDocument()
        expect(screen.getByLabelText('Form Name')).toHaveValue('Surrogate Application Form (Official)')
    })
})
