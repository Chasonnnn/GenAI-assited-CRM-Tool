import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import AutomationPage from '../app/(app)/automation/page'

vi.mock('@/lib/hooks/use-email-templates', () => ({
    useEmailTemplates: () => ({ data: [], isLoading: false }),
    useCreateEmailTemplate: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUpdateEmailTemplate: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteEmailTemplate: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe('AutomationPage', () => {
    it('renders', () => {
        render(<AutomationPage />)
        expect(screen.getByText('Automation')).toBeInTheDocument()
    })
})
