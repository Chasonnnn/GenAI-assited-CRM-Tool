import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import AutomationPage from '../app/(app)/automation/page'

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
    useSearchParams: () => ({
        get: vi.fn(() => null),
    }),
}))

vi.mock('@/lib/hooks/use-email-templates', () => ({
    useEmailTemplates: () => ({ data: [], isLoading: false }),
    useCreateEmailTemplate: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUpdateEmailTemplate: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteEmailTemplate: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/lib/hooks/use-workflows', () => ({
    useWorkflows: () => ({ data: [], isLoading: false }),
    useCreateWorkflow: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUpdateWorkflow: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteWorkflow: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useToggleWorkflow: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe('AutomationPage', () => {
    it('renders', () => {
        render(<AutomationPage />)
        expect(screen.getByText('Automation')).toBeInTheDocument()
    })
})
