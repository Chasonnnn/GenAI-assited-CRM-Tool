import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import AutomationPage from '../app/(app)/automation/page'

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
    useSearchParams: () => ({
        get: vi.fn(() => null),
    }),
    useRouter: () => ({
        push: vi.fn(),
        replace: vi.fn(),
        back: vi.fn(),
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
    useWorkflow: () => ({ data: null, isLoading: false }),
    useWorkflowStats: () => ({ data: { total: 0, enabled: 0, disabled: 0 }, isLoading: false }),
    useWorkflowOptions: () => ({ data: { trigger_types: [], action_types: [], condition_fields: [] }, isLoading: false }),
    useWorkflowExecutions: () => ({ data: { items: [], total: 0, page: 1, pages: 1 }, isLoading: false }),
    useCreateWorkflow: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUpdateWorkflow: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDuplicateWorkflow: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useTestWorkflow: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteWorkflow: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useToggleWorkflow: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe('AutomationPage', () => {
    it('renders', () => {
        render(<AutomationPage />)
        expect(screen.getAllByText('Workflows').length).toBeGreaterThan(0)
    })
})
