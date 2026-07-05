import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import WorkflowTemplatesPanel from '../components/automation/workflow-templates-panel'

const { mockApiPost } = vi.hoisted(() => ({
    mockApiPost: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
    default: {
        get: vi.fn(),
        post: mockApiPost,
    },
}))

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

const mockFormScopedTemplate = {
    id: 'tmpl-form',
    name: 'Pre-Screening: Auto-Match then Create Lead (Approval)',
    description: 'Approval-gated intake routing for the Surrogate Pre-Screening Questionnaire',
    category: 'onboarding',
    trigger_type: 'form_submitted',
    is_global: true,
    usage_count: 8,
    created_at: '2025-01-01T00:00:00Z',
    icon: 'template',
    trigger_config: { form_name: 'Surrogate Pre-Screening Questionnaire' },
    conditions: [],
    condition_logic: 'AND',
    actions: [
        { action_type: 'auto_match_submission', requires_approval: true },
        { action_type: 'create_intake_lead', requires_approval: true },
    ],
}

const mockFormIdTemplate = {
    ...mockFormScopedTemplate,
    id: 'tmpl-form-id',
    name: 'Submitted Published Form Workflow',
    trigger_config: { form_id: 'form-ewi' },
}

const mockTemplates = [
    mockTemplateWithMissingEmail,
    mockTemplateWithEmail,
    mockFormScopedTemplate,
    mockFormIdTemplate,
]
const mockCategories = [
    { value: 'onboarding', label: 'Onboarding' },
    { value: 'follow-up', label: 'Follow-up' },
    { value: 'notifications', label: 'Notifications' },
    { value: 'compliance', label: 'Compliance' },
    { value: 'general', label: 'General' },
]

const baseForms = [
    {
        id: 'form-ewi',
        name: 'EWI pre-questionnaire',
        status: 'published',
        purpose: 'lead_capture',
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-01T00:00:00Z',
    },
]

let mockForms = baseForms

function getModalCreateButton() {
    const createButtons = screen.getAllByRole('button', { name: /create workflow/i })
    return createButtons[createButtons.length - 1]
}

describe('WorkflowTemplatesPanel', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockUseAuth.mockReturnValue({ user: { role: 'admin' } })
        mockForms = baseForms
        mockApiPost.mockResolvedValue({ id: 'workflow-1' })

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
                if (templateId === 'tmpl-form') {
                    return { data: mockFormScopedTemplate, isLoading: false, isError: false, error: null }
                }
                if (templateId === 'tmpl-form-id') {
                    return { data: mockFormIdTemplate, isLoading: false, isError: false, error: null }
                }
                return { data: null, isLoading: false, isError: false, error: null }
            }
            if (queryKey[0] === 'forms') {
                return { data: mockForms, isLoading: false, isError: false, error: null }
            }
            return { data: null, isLoading: false, isError: false, error: null }
        })

        // Mock useMutation and execute the provided mutationFn when mutate is called.
        ; (useMutation as ReturnType<typeof vi.fn>).mockImplementation((options) => ({
            mutate: vi.fn(() => {
                void options.mutationFn()
            }),
            mutateAsync: vi.fn(() => options.mutationFn()),
            isPending: false,
        }))

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

    it('renders each template card as an accessible button', () => {
        render(<WorkflowTemplatesPanel />)

        expect(
            screen.getByRole('button', { name: /use template welcome new lead/i })
        ).toBeInTheDocument()
        expect(
            screen.getByRole('button', { name: /use template task reminder/i })
        ).toBeInTheDocument()
    })

    it('shows email template selection when template with missing email is selected', async () => {
        render(<WorkflowTemplatesPanel />)

        fireEvent.click(screen.getByRole('button', { name: /use template welcome new lead/i }))

        // Should show the email template selection prompt
        await waitFor(() => {
            expect(screen.getByText(/Select email templates for this workflow/i)).toBeInTheDocument()
        })
    })

    it('does not show email template selection for templates without send_email actions', async () => {
        render(<WorkflowTemplatesPanel />)

        fireEvent.click(screen.getByRole('button', { name: /use template task reminder/i }))

        // Should NOT show email template selection
        await waitFor(() => {
            // Dialog should be open but without email selection
            expect(screen.getByRole("heading", { name: /Use Template/i })).toBeInTheDocument()
        })

        expect(screen.queryByText(/Select email templates for this workflow/i)).not.toBeInTheDocument()
    })

    it('shows a published form selector for form-scoped templates', async () => {
        render(<WorkflowTemplatesPanel />)

        fireEvent.click(
            screen.getByRole('button', {
                name: /use template pre-screening: auto-match then create lead/i,
            })
        )

        await waitFor(() => {
            expect(screen.getByText('Published form')).toBeInTheDocument()
        })
        expect(screen.getByText('EWI pre-questionnaire')).toBeInTheDocument()
    })

    it('includes trigger_form_id when a form-scoped template is auto-selected', async () => {
        render(<WorkflowTemplatesPanel />)

        fireEvent.click(
            screen.getByRole('button', {
                name: /use template pre-screening: auto-match then create lead/i,
            })
        )

        await waitFor(() => {
            expect(screen.getByText('Published form')).toBeInTheDocument()
        })

        fireEvent.click(getModalCreateButton())

        expect(mockApiPost).toHaveBeenCalledWith('/templates/tmpl-form/use', {
            name: mockFormScopedTemplate.name,
            description: mockFormScopedTemplate.description,
            is_enabled: true,
            action_overrides: {},
            trigger_form_id: 'form-ewi',
            scope: 'personal',
        })
    })

    it('auto-selects an existing published trigger form id before matching by form name', async () => {
        mockForms = [
            ...baseForms,
            {
                id: 'form-name-match',
                name: 'Surrogate Pre-Screening Questionnaire',
                status: 'published',
                purpose: 'lead_capture',
                created_at: '2025-01-01T00:00:00Z',
                updated_at: '2025-01-01T00:00:00Z',
            },
        ]

        render(<WorkflowTemplatesPanel />)

        fireEvent.click(
            screen.getByRole('button', {
                name: /use template submitted published form workflow/i,
            })
        )

        await waitFor(() => {
            expect(screen.getByText('EWI pre-questionnaire')).toBeInTheDocument()
        })
    })

    it('requires a user selection when multiple published forms exist without a match', async () => {
        mockForms = [
            ...baseForms,
            {
                id: 'form-other',
                name: 'Other published form',
                status: 'published',
                purpose: 'lead_capture',
                created_at: '2025-01-01T00:00:00Z',
                updated_at: '2025-01-01T00:00:00Z',
            },
        ]

        render(<WorkflowTemplatesPanel />)

        fireEvent.click(
            screen.getByRole('button', {
                name: /use template pre-screening: auto-match then create lead/i,
            })
        )

        await waitFor(() => {
            expect(screen.getByText('Choose a published form')).toBeInTheDocument()
        })
        expect(getModalCreateButton()).toBeDisabled()
    })

    it('blocks creation when no published forms exist', async () => {
        mockForms = [
            {
                id: 'form-draft',
                name: 'Draft form',
                status: 'draft',
                purpose: 'lead_capture',
                created_at: '2025-01-01T00:00:00Z',
                updated_at: '2025-01-01T00:00:00Z',
            },
        ]

        render(<WorkflowTemplatesPanel />)

        fireEvent.click(
            screen.getByRole('button', {
                name: /use template pre-screening: auto-match then create lead/i,
            })
        )

        await waitFor(() => {
            expect(
                screen.getByText('Publish a form before using this workflow template.')
            ).toBeInTheDocument()
        })
        expect(getModalCreateButton()).toBeDisabled()
    })

    it('does not show the published form selector for non-form templates', async () => {
        render(<WorkflowTemplatesPanel />)

        fireEvent.click(screen.getByRole('button', { name: /use template task reminder/i }))

        await waitFor(() => {
            expect(screen.getByRole("heading", { name: /Use Template/i })).toBeInTheDocument()
        })

        expect(screen.queryByText('Published form')).not.toBeInTheDocument()
    })

    it('closes the use-template dialog when cancelled', async () => {
        render(<WorkflowTemplatesPanel />)

        fireEvent.click(screen.getByRole('button', { name: /use template task reminder/i }))

        await waitFor(() => {
            expect(screen.getByRole("heading", { name: /Use Template/i })).toBeInTheDocument()
        })

        fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

        await waitFor(() => {
            expect(screen.queryByRole("heading", { name: /Use Template/i })).not.toBeInTheDocument()
        })
    })
})
