import type { PropsWithChildren, ButtonHTMLAttributes, ReactNode } from "react"
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import AutomationPage from '../app/(app)/automation/page.client'

const mockUseAuth = vi.fn()
const mockUseEffectivePermissions = vi.fn()
vi.mock('@/lib/auth-context', () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock('@/lib/hooks/use-permissions', () => ({
    useEffectivePermissions: () => mockUseEffectivePermissions(),
}))

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

// Simplify Select and Dialog components for deterministic tests
vi.mock('@/components/ui/select', () => ({
    Select: ({ value, onValueChange, children }: PropsWithChildren<{ value?: string; onValueChange: (value: string) => void }>) => (
        <select
            data-testid="select"
            value={value ?? ''}
            onChange={(e) => onValueChange(e.target.value)}
        >
            <option value="">Select</option>
            {children}
        </select>
    ),
    SelectTrigger: () => null,
    SelectValue: () => null,
    SelectContent: ({ children }: PropsWithChildren) => <>{children}</>,
    SelectItem: ({ value, children }: PropsWithChildren<{ value: string }>) => <option value={value}>{children}</option>,
}))

vi.mock('@/components/ui/dialog', () => ({
    Dialog: ({ open, children }: { open?: boolean; children?: ReactNode }) =>
        open ? <div>{children}</div> : null,
    DialogContent: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DialogHeader: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DialogDescription: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DialogFooter: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
}))

vi.mock('@/components/ui/dropdown-menu', () => ({
    DropdownMenu: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DropdownMenuTrigger: ({
        children,
        render,
        ...props
    }: {
        children?: ReactNode
        render?:
            | ((props: ButtonHTMLAttributes<HTMLButtonElement>) => ReactNode)
            | ReactNode
    } & ButtonHTMLAttributes<HTMLButtonElement>) => {
        if (render) {
            return typeof render === "function" ? <>{render({ ...props })}</> : <>{render}</>
        }
        return (
            <button type="button" {...props}>
                {children}
            </button>
        )
    },
    DropdownMenuContent: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DropdownMenuItem: ({
        children,
        onClick,
        onSelect,
        ...props
    }: {
        children?: ReactNode
        onClick?: () => void
        onSelect?: () => void
    }) => (
        <button
            type="button"
            onClick={() => {
                onClick?.()
                onSelect?.()
            }}
            {...props}
        >
            {children}
        </button>
    ),
}))

vi.mock('@/lib/hooks/use-email-templates', () => ({
    useEmailTemplates: () => ({ data: [], isLoading: false }),
    useCreateEmailTemplate: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUpdateEmailTemplate: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteEmailTemplate: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

const mockUseWorkflows = vi.fn()
const mockUseWorkflow = vi.fn()
const mockUseWorkflowStats = vi.fn()
const mockUseWorkflowOptions = vi.fn()
const mockUseWorkflowExecutions = vi.fn()
const mockCreateWorkflow = { mutate: vi.fn(), isPending: false }
const mockUpdateWorkflow = { mutate: vi.fn(), isPending: false }

function getFirstElement<T>(items: T[], message: string): T {
    const item = items[0]
    if (!item) {
        throw new Error(message)
    }
    return item
}

function getLastElement<T>(items: T[], message: string): T {
    const item = items.at(-1)
    if (!item) {
        throw new Error(message)
    }
    return item
}

vi.mock('@/lib/hooks/use-workflows', () => ({
    useWorkflows: (...args: unknown[]) => mockUseWorkflows(...args),
    useWorkflow: () => mockUseWorkflow(),
    useWorkflowStats: () => mockUseWorkflowStats(),
    useWorkflowOptions: () => mockUseWorkflowOptions(),
    useWorkflowExecutions: () => mockUseWorkflowExecutions(),
    useCreateWorkflow: () => mockCreateWorkflow,
    useUpdateWorkflow: () => mockUpdateWorkflow,
    useDuplicateWorkflow: () => ({ mutate: vi.fn(), isPending: false }),
    useTestWorkflow: () => ({ mutate: vi.fn(), isPending: false }),
    useDeleteWorkflow: () => ({ mutate: vi.fn(), isPending: false }),
    useToggleWorkflow: () => ({ mutate: vi.fn(), isPending: false }),
}))

function renderAutomationPage() {
    return render(
        <AutomationPage
            initialTab="workflows"
            initialWorkflowScopeTab="personal"
            initialCreateOpen={false}
        />
    )
}

describe('AutomationPage', () => {
    beforeEach(() => {
        mockUseAuth.mockReturnValue({ user: { role: 'admin' } })
        mockUseEffectivePermissions.mockReturnValue({ data: { permissions: [] } })
        mockUseWorkflows.mockClear()
        mockUseWorkflows.mockReturnValue({ data: [], isLoading: false })
        mockUseWorkflow.mockReturnValue({ data: null, isLoading: false })
        mockUseWorkflowStats.mockReturnValue({ data: { total_workflows: 0, enabled_workflows: 0, success_rate_24h: 0, total_executions_24h: 0 }, isLoading: false })
        mockUseWorkflowOptions.mockReturnValue({
            data: {
                trigger_types: [
                    { value: 'surrogate_created', label: 'Surrogate Created', description: '' },
                    { value: 'scheduled', label: 'Scheduled', description: '' },
                    { value: 'task_due', label: 'Task Due', description: '' },
                ],
                action_types: [
                    { value: 'add_note', label: 'Add Note', description: '' },
                ],
                action_types_by_trigger: {
                    surrogate_created: ['add_note'],
                    scheduled: ['add_note'],
                    task_due: ['add_note'],
                },
                trigger_entity_types: {
                    surrogate_created: 'surrogate',
                    scheduled: 'surrogate',
                    task_due: 'task',
                },
                condition_fields: [],
                condition_operators: [],
                update_fields: [],
                email_variables: [],
                email_templates: [],
                users: [],
                queues: [],
                statuses: [],
            },
            isLoading: false,
        })
        mockUseWorkflowExecutions.mockReturnValue({ data: { items: [], total: 0, page: 1, pages: 1 }, isLoading: false })
        mockCreateWorkflow.mutate.mockReset()
        mockUpdateWorkflow.mutate.mockReset()
    })

    it('renders', () => {
        renderAutomationPage()
        expect(screen.getAllByText('Workflows').length).toBeGreaterThan(0)
    })

    it('renders workflow tabs', () => {
        renderAutomationPage()
        expect(screen.getByText('My Workflows')).toBeInTheDocument()
        expect(screen.getByText('Org Workflows')).toBeInTheDocument()
        expect(screen.getByText('Workflow Templates')).toBeInTheDocument()
    })

    it('uses org scope for the first admin workflow query when no scope is explicit', () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ['manage_automation'] },
        })

        renderAutomationPage()

        expect(mockUseWorkflows).toHaveBeenNthCalledWith(1, { scope: 'org' })
        expect(mockUseWorkflows).not.toHaveBeenCalledWith({ scope: 'personal' })
    })

    it('shows server validation errors in the wizard', () => {
        mockCreateWorkflow.mutate.mockImplementation((_data: unknown, opts?: { onError?: (err: Error) => void }) => {
            opts?.onError?.(new Error('Action 1: title is required; Action 1: assignee is required'))
        })

        renderAutomationPage()

        const createButtons = screen.getAllByRole('button', { name: /create workflow/i })
        fireEvent.click(getLastElement(createButtons, 'Expected a create workflow button'))

        fireEvent.change(screen.getByPlaceholderText('e.g., Welcome New Surrogates'), { target: { value: 'Test Workflow' } })
        fireEvent.change(
            getFirstElement(screen.getAllByTestId('select'), 'Expected a trigger select'),
            { target: { value: 'surrogate_created' } },
        )

        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /next/i }))

        fireEvent.click(screen.getByRole('button', { name: /add action/i }))
        fireEvent.change(
            getFirstElement(screen.getAllByTestId('select'), 'Expected an action select'),
            { target: { value: 'add_note' } },
        )
        fireEvent.change(screen.getByPlaceholderText('Note content'), { target: { value: 'Test note' } })

        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        const saveButtons = screen.getAllByRole('button', { name: /create workflow/i })
        fireEvent.click(getLastElement(saveButtons, 'Expected a save workflow button'))

        expect(screen.getByText(/fix these errors/i)).toBeInTheDocument()
        expect(screen.getByText(/Action 1: title is required/i)).toBeInTheDocument()
    })

    it('clears server validation errors when condition logic changes', () => {
        mockCreateWorkflow.mutate.mockImplementation(
            (_data: unknown, opts?: { onError?: (err: Error) => void }) => {
                opts?.onError?.(
                    new Error('Action 1: title is required; Action 1: assignee is required'),
                )
            },
        )

        renderAutomationPage()

        const createButtons = screen.getAllByRole('button', { name: /create workflow/i })
        fireEvent.click(getLastElement(createButtons, 'Expected a create workflow button'))
        fireEvent.change(screen.getByPlaceholderText('e.g., Welcome New Surrogates'), {
            target: { value: 'Conditional Workflow' },
        })
        fireEvent.change(
            getFirstElement(screen.getAllByTestId('select'), 'Expected a trigger select'),
            { target: { value: 'surrogate_created' } },
        )
        fireEvent.click(screen.getByRole('button', { name: /next/i }))

        fireEvent.click(screen.getByRole('button', { name: /add condition/i }))
        fireEvent.click(screen.getByRole('button', { name: /add condition/i }))
        expect(screen.getByRole('button', { name: 'AND' })).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /add action/i }))
        fireEvent.change(
            getFirstElement(screen.getAllByTestId('select'), 'Expected an action select'),
            { target: { value: 'add_note' } },
        )
        fireEvent.change(screen.getByPlaceholderText('Note content'), {
            target: { value: 'Record the condition result' },
        })
        fireEvent.click(screen.getByRole('button', { name: /next/i }))

        const saveButtons = screen.getAllByRole('button', { name: /create workflow/i })
        fireEvent.click(getLastElement(saveButtons, 'Expected a save workflow button'))
        expect(mockCreateWorkflow.mutate).toHaveBeenCalledTimes(1)
        expect(screen.getByText(/Action 1: title is required/i)).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /back/i }))
        fireEvent.click(screen.getByRole('button', { name: /back/i }))
        fireEvent.click(screen.getByRole('button', { name: 'AND' }))

        expect(screen.queryByText(/Action 1: title is required/i)).not.toBeInTheDocument()
    })

    it('preserves server errors when late status options only normalize legacy config', () => {
        const initialOptions = {
            trigger_types: [
                { value: 'status_changed', label: 'Status Changed', description: '' },
            ],
            action_types: [
                { value: 'add_note', label: 'Add Note', description: '' },
            ],
            action_types_by_trigger: {
                status_changed: ['add_note'],
            },
            trigger_entity_types: {
                status_changed: 'surrogate',
            },
            condition_fields: [],
            condition_operators: [],
            update_fields: [],
            email_variables: [],
            email_templates: [],
            users: [],
            queues: [],
            statuses: [],
        }
        mockUseWorkflowOptions.mockReturnValue({
            data: initialOptions,
            isLoading: false,
        })
        mockUseWorkflows.mockReturnValue({
            data: [
                {
                    id: 'workflow-legacy',
                    name: 'Legacy Status Workflow',
                    description: null,
                    icon: 'activity',
                    trigger_type: 'status_changed',
                    is_enabled: true,
                    run_count: 0,
                    last_run_at: null,
                    last_error: null,
                    created_at: '2026-07-01T00:00:00Z',
                    can_edit: true,
                },
            ],
            isLoading: false,
        })
        mockUseWorkflow.mockReturnValue({
            data: {
                id: 'workflow-legacy',
                name: 'Legacy Status Workflow',
                description: null,
                scope: 'personal',
                trigger_type: 'status_changed',
                trigger_config: { to_status: 'qualified' },
                conditions: [],
                condition_logic: 'AND',
                actions: [
                    {
                        action_type: 'add_note',
                        content: 'Record status change',
                    },
                ],
            },
            isLoading: false,
        })
        mockUpdateWorkflow.mutate.mockImplementation(
            (_data: unknown, opts?: { onError?: (err: Error) => void }) => {
                opts?.onError?.(
                    new Error('Action 1: title is required; Action 1: assignee is required'),
                )
            },
        )

        const view = renderAutomationPage()

        fireEvent.click(
            screen.getByRole('button', {
                name: 'Actions for workflow Legacy Status Workflow',
            }),
        )
        fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
        expect(screen.getByDisplayValue('Legacy Status Workflow')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /save changes/i }))
        expect(screen.getByText(/Action 1: title is required/i)).toBeInTheDocument()

        mockUseWorkflowOptions.mockReturnValue({
            data: {
                ...initialOptions,
                statuses: [
                    {
                        id: 'stage-qualified',
                        value: 'qualified',
                        label: 'Qualified',
                    },
                ],
            },
            isLoading: false,
        })
        view.rerender(
            <AutomationPage
                initialTab="workflows"
                initialWorkflowScopeTab="personal"
                initialCreateOpen={false}
            />,
        )

        expect(screen.getByText(/Action 1: title is required/i)).toBeInTheDocument()
    })

    it('submits only the configuration for the selected trigger type', () => {
        renderAutomationPage()

        const createButtons = screen.getAllByRole('button', { name: /create workflow/i })
        fireEvent.click(getLastElement(createButtons, 'Expected a create workflow button'))

        fireEvent.change(screen.getByPlaceholderText('e.g., Welcome New Surrogates'), {
            target: { value: 'Task Due Reminder' },
        })

        const triggerSelect = getFirstElement(
            screen.getAllByTestId('select'),
            'Expected a trigger select',
        )
        fireEvent.change(triggerSelect, { target: { value: 'scheduled' } })
        fireEvent.change(screen.getByPlaceholderText('0 9 * * 1'), {
            target: { value: '0 8 * * *' },
        })
        fireEvent.change(screen.getByPlaceholderText('America/Los_Angeles'), {
            target: { value: 'America/New_York' },
        })

        fireEvent.change(triggerSelect, { target: { value: 'task_due' } })
        fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '48' } })

        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /next/i }))

        fireEvent.click(screen.getByRole('button', { name: /add action/i }))
        fireEvent.change(
            getFirstElement(screen.getAllByTestId('select'), 'Expected an action select'),
            { target: { value: 'add_note' } },
        )
        fireEvent.change(screen.getByPlaceholderText('Note content'), {
            target: { value: 'Task is due soon' },
        })

        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        const saveButtons = screen.getAllByRole('button', { name: /create workflow/i })
        fireEvent.click(getLastElement(saveButtons, 'Expected a save workflow button'))

        expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
            expect.objectContaining({
                trigger_type: 'task_due',
                trigger_config: { hours_before: 48 },
            }),
            expect.any(Object),
        )
    })

    it('uses entity-specific labels in the test workflow modal', () => {
        mockUseWorkflows.mockReturnValue({
            data: [
                {
                    id: 'wf-1',
                    name: 'Task Reminder',
                    description: null,
                    icon: 'check',
                    trigger_type: 'task_due',
                    is_enabled: true,
                    run_count: 0,
                    last_run_at: null,
                    last_error: null,
                    created_at: '2025-01-01T00:00:00Z',
                    can_edit: true,
                },
            ],
            isLoading: false,
        })

        renderAutomationPage()

        fireEvent.click(screen.getByRole('button', { name: /test workflow/i }))

        expect(screen.getByText('Task ID')).toBeInTheDocument()
    })
})
