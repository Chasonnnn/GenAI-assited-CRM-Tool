import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import WorkflowTemplatesPanel from '../components/automation/workflow-templates-panel'

const mockUseAuth = vi.fn()
vi.mock('@/lib/auth-context', () => ({
    useAuth: () => mockUseAuth(),
}))

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
    useSearchParams: () => ({
        get: vi.fn(() => null),
    }),
    useRouter: () => ({
        push: vi.fn(),
        replace: vi.fn(),
    }),
}))

// Mock email templates hook
const mockEmailTemplates = [
    { id: 'et-1', name: 'Welcome Email', subject: 'Welcome!' },
    { id: 'et-2', name: 'Follow Up', subject: 'Following up' },
]
vi.mock('@/lib/hooks/use-email-templates', () => ({
    useEmailTemplates: () => ({ data: mockEmailTemplates, isLoading: false }),
}))

// Template data
const mockTemplateWithMissingEmail = {
    id: 'tmpl-1',
    name: 'Welcome New Lead',
    description: 'Send a welcome email when a new lead is created',
    category: 'onboarding',
    trigger_type: 'surrogate_created',
    is_global: true,
    usage_count: 5,
    created_at: '2025-01-01T00:00:00Z',
    icon: 'mail',
    trigger_config: {},
    conditions: [],
    condition_logic: 'AND',
    actions: [
        { action_type: 'send_email', template_id: null },
    ],
}

const mockTemplateWithEmail = {
    id: 'tmpl-2',
    name: 'Task Reminder',
    description: 'Create a task when status changes',
    category: 'automation',
    trigger_type: 'surrogate_status_changed',
    is_global: true,
    usage_count: 3,
    created_at: '2025-01-01T00:00:00Z',
    icon: 'check',
    trigger_config: {},
    conditions: [],
    condition_logic: 'AND',
    actions: [
        { action_type: 'create_task', title: 'Follow up' },
    ],
}

const mockTemplates = [mockTemplateWithMissingEmail, mockTemplateWithEmail]
const mockCategories = [
    { value: 'onboarding', label: 'Onboarding' },
    { value: 'follow-up', label: 'Follow-up' },
    { value: 'notifications', label: 'Notifications' },
    { value: 'compliance', label: 'Compliance' },
    { value: 'general', label: 'General' },
]

describe('WorkflowTemplatesPanel', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockUseAuth.mockReturnValue({ user: { role: 'admin' } })

            // Mock useQuery to return different data based on queryKey
            ; (useQuery as ReturnType<typeof vi.fn>).mockImplementation(({ queryKey }) => {
                if (queryKey[0] === 'template-categories') {
                    return { data: { categories: mockCategories }, isLoading: false, isError: false, error: null }
                }
                if (queryKey[0] === 'templates') {
                    return { data: mockTemplates, isLoading: false, isError: false, error: null }
                }
                if (queryKey[0] === 'template') {
                    const templateId = queryKey[1]
                    if (templateId === 'tmpl-1') {
                        return { data: mockTemplateWithMissingEmail, isLoading: false, isError: false, error: null }
                    }
                    if (templateId === 'tmpl-2') {
                        return { data: mockTemplateWithEmail, isLoading: false, isError: false, error: null }
                    }
                    return { data: null, isLoading: false, isError: false, error: null }
                }
                return { data: null, isLoading: false, isError: false, error: null }
            })

            // Mock useMutation
            ; (useMutation as ReturnType<typeof vi.fn>).mockReturnValue({
                mutate: vi.fn(),
                mutateAsync: vi.fn(),
                isPending: false,
            })

            // Mock useQueryClient
            ; (useQueryClient as ReturnType<typeof vi.fn>).mockReturnValue({
                invalidateQueries: vi.fn(),
            })
    })

    it('renders the workflow templates panel', () => {
        render(<WorkflowTemplatesPanel />)
        expect(screen.getByText('Workflow Templates')).toBeInTheDocument()
    })

    it('renders template list from mocked data', () => {
        render(<WorkflowTemplatesPanel />)
        expect(screen.getByText('Welcome New Lead')).toBeInTheDocument()
        expect(screen.getByText('Task Reminder')).toBeInTheDocument()
    })

    it('shows email template selection when template with missing email is selected', async () => {
        render(<WorkflowTemplatesPanel />)

        // Find and click the template card (Card component, not button)
        const templateName = screen.getByText('Welcome New Lead')
        const templateCard = templateName.closest('[class*="cursor-pointer"]') || templateName.closest('div[class*="Card"]')
        expect(templateCard).toBeTruthy()
        fireEvent.click(templateCard!)

        // Should show the email template selection prompt
        await waitFor(() => {
            expect(screen.getByText(/Select email templates for this workflow/i)).toBeInTheDocument()
        })
    })

    it('does not show email template selection for templates without send_email actions', async () => {
        render(<WorkflowTemplatesPanel />)

        // Find and click the Task Reminder template card
        const templateName = screen.getByText('Task Reminder')
        const templateCard = templateName.closest('[class*="cursor-pointer"]') || templateName.closest('div[class*="Card"]')
        expect(templateCard).toBeTruthy()
        fireEvent.click(templateCard!)

        // Should NOT show email template selection
        await waitFor(() => {
            // Dialog should be open but without email selection
            expect(screen.getByRole("heading", { name: /Use Template/i })).toBeInTheDocument()
        })

        expect(screen.queryByText(/Select email templates for this workflow/i)).not.toBeInTheDocument()
    })
})
