import type { PropsWithChildren, ButtonHTMLAttributes, ReactNode } from "react"
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import AutomationPage from '../app/(app)/automation/page.client'
import { ApiError } from '@/lib/api'

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
    Select: ({
        value,
        onValueChange,
        children,
        disabled,
        "aria-label": ariaLabel,
    }: PropsWithChildren<{
        value?: string
        onValueChange: (value: string) => void
        disabled?: boolean
        "aria-label"?: string
    }>) => (
        <select
            data-testid="select"
            value={value ?? ''}
            onChange={(e) => onValueChange(e.target.value)}
            disabled={disabled}
            aria-label={ariaLabel}
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
const mockPublishWorkflow = { mutate: vi.fn(), isPending: false }
const mockTestWorkflow = { mutate: vi.fn(), isPending: false }
const mockListDonors = vi.fn()

vi.mock('@/lib/api/donors', () => ({
    listDonors: (...args: unknown[]) => mockListDonors(...args),
}))

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
    useWorkflowOptions: (...args: unknown[]) => mockUseWorkflowOptions(...args),
    useWorkflowExecutions: () => mockUseWorkflowExecutions(),
    useCreateWorkflow: () => mockCreateWorkflow,
    useUpdateWorkflow: () => mockUpdateWorkflow,
    usePublishWorkflow: () => mockPublishWorkflow,
    useDuplicateWorkflow: () => ({ mutate: vi.fn(), isPending: false }),
    useTestWorkflow: () => mockTestWorkflow,
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
        mockTestWorkflow.mutate.mockReset()
        mockListDonors.mockReset().mockResolvedValue({
            items: [],
            total: 0,
            page: 1,
            per_page: 5,
            pages: 0,
        })
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

    it('scrolls the scope tabs and wraps the create actions at narrow widths', () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ['manage_automation'] },
        })
        renderAutomationPage()

        const tabList = screen.getByRole('tablist', { name: 'Workflow scope' })
        expect(tabList).toHaveClass('max-w-full', 'overflow-x-auto', 'justify-start')

        const row = tabList.parentElement
        expect(row).toHaveClass('flex-wrap')
        const createButton = getFirstElement(
            screen.getAllByRole('button', { name: 'Create Org Workflow' }),
            'Expected a create org workflow button',
        )
        expect(row).toContainElement(createButton)
        expect(createButton.parentElement).toHaveClass('flex-wrap')
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
            opts?.onError?.(
                new ApiError(422, 'Unprocessable Entity', 'Action 1: title is required; Action 1: assignee is required'),
            )
        })

        renderAutomationPage()

        const createButtons = screen.getAllByRole('button', { name: /create workflow/i })
        fireEvent.click(getLastElement(createButtons, 'Expected a create workflow button'))

        fireEvent.change(screen.getByPlaceholderText('e.g., Welcome New Surrogates'), { target: { value: 'Test Workflow' } })
        fireEvent.change(
            screen.getByRole('combobox', { name: 'Trigger type' }),
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
        expect(screen.queryByText('Please fill in all required fields')).not.toBeInTheDocument()
    })

    it('shows one plain message when saving an org workflow is forbidden', () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ['manage_automation'] },
        })
        mockCreateWorkflow.mutate.mockImplementation((_data: unknown, opts?: { onError?: (err: Error) => void }) => {
            opts?.onError?.(
                new ApiError(403, 'Forbidden', 'Cannot create org workflows without manage_automation permission'),
            )
        })

        renderAutomationPage()

        fireEvent.click(
            getFirstElement(
                screen.getAllByRole('button', { name: 'Create Org Workflow' }),
                'Expected a create org workflow button',
            ),
        )
        fireEvent.change(screen.getByPlaceholderText('e.g., Welcome New Surrogates'), { target: { value: 'Org Workflow' } })
        fireEvent.change(
            screen.getByRole('combobox', { name: 'Trigger type' }),
            { target: { value: 'surrogate_created' } },
        )
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /add action/i }))
        fireEvent.change(
            getFirstElement(screen.getAllByTestId('select'), 'Expected an action select'),
            { target: { value: 'add_note' } },
        )
        fireEvent.change(screen.getByPlaceholderText('Note content'), { target: { value: 'Note' } })
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        const saveButtons = screen.getAllByRole('button', { name: /create workflow/i })
        fireEvent.click(getLastElement(saveButtons, 'Expected a save workflow button'))

        expect(
            screen.getByText("You don't have permission to create organization workflows"),
        ).toBeInTheDocument()
        expect(screen.queryByText(/manage_automation/)).not.toBeInTheDocument()
        expect(screen.queryByText(/fix these errors/i)).not.toBeInTheDocument()
        expect(screen.queryByText('Please fill in all required fields')).not.toBeInTheDocument()
    })

    it('hides org workflow creation and Execution History without manage_automation', () => {
        mockUseEffectivePermissions.mockReturnValue({ data: { permissions: [] } })
        render(
            <AutomationPage
                initialTab="workflows"
                initialWorkflowScopeTab="org"
                initialCreateOpen={false}
                hasInitialScopeParam
            />,
        )

        expect(screen.queryByRole('button', { name: 'Create Org Workflow' })).not.toBeInTheDocument()
        expect(screen.queryByRole('button', { name: 'Execution History' })).not.toBeInTheDocument()
        expect(screen.getByText('No org workflows yet')).toBeInTheDocument()
    })

    it('shows a load error instead of the empty state when workflows fail to load', () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ['manage_automation'] },
        })
        const refetch = vi.fn()
        mockUseWorkflows.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            isFetching: false,
            error: new ApiError(500, 'Internal Server Error', 'database exploded'),
            refetch,
        })
        mockUseWorkflowStats.mockReturnValue({
            data: { total_workflows: 14, enabled_workflows: 3, success_rate_24h: 0, total_executions_24h: 0 },
            isLoading: false,
        })

        renderAutomationPage()

        expect(
            screen.getByRole('heading', { level: 3, name: "Couldn't load workflows" }),
        ).toBeInTheDocument()
        expect(screen.queryByText('No org workflows yet')).not.toBeInTheDocument()
        expect(screen.queryByText(/database exploded/)).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
        expect(refetch).toHaveBeenCalledTimes(1)
    })

    it('shows Execution History for managers', () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ['manage_automation'] },
        })
        renderAutomationPage()

        expect(screen.getByRole('button', { name: 'Execution History' })).toBeInTheDocument()
        expect(screen.getAllByRole('button', { name: 'Create Org Workflow' }).length).toBeGreaterThan(0)
    })

    it('labels the workflow wizard steps and the email template select', () => {
        renderAutomationPage()

        const createButtons = screen.getAllByRole('button', { name: /create workflow/i })
        fireEvent.click(getLastElement(createButtons, 'Expected a create workflow button'))

        const progress = screen.getByRole('list', { name: 'Progress' })
        expect(progress).toHaveTextContent('Trigger')
        expect(progress).toHaveTextContent('Conditions')
        expect(progress).toHaveTextContent('Actions')
        expect(progress).toHaveTextContent('Review')
        expect(screen.queryByText(/Step 1 of 4/)).not.toBeInTheDocument()
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
            screen.getByRole('combobox', { name: 'Trigger type' }),
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

    it('waits for the selected workflow response before hydrating the edit draft', () => {
        mockUseWorkflows.mockReturnValue({
            data: [
                {
                    id: 'workflow-b',
                    name: 'Selected Workflow B',
                    description: null,
                    icon: 'activity',
                    trigger_type: 'surrogate_created',
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
                id: 'workflow-a',
                name: 'Stale Workflow A',
                description: null,
                scope: 'personal',
                trigger_type: 'surrogate_created',
                trigger_config: {},
                conditions: [],
                condition_logic: 'AND',
                actions: [],
            },
            isLoading: false,
        })

        const view = renderAutomationPage()

        fireEvent.click(
            screen.getByRole('button', {
                name: 'Actions for workflow Selected Workflow B',
            }),
        )
        fireEvent.click(screen.getByRole('button', { name: 'Edit' }))

        mockUseWorkflow.mockReturnValue({
            data: {
                id: 'workflow-b',
                name: 'Selected Workflow B',
                description: null,
                scope: 'personal',
                trigger_type: 'surrogate_created',
                trigger_config: {},
                conditions: [],
                condition_logic: 'AND',
                actions: [],
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

        expect(screen.getByDisplayValue('Selected Workflow B')).toBeInTheDocument()
        expect(screen.queryByDisplayValue('Stale Workflow A')).not.toBeInTheDocument()
    })

    it('submits only the configuration for the selected trigger type', () => {
        renderAutomationPage()

        const createButtons = screen.getAllByRole('button', { name: /create workflow/i })
        fireEvent.click(getLastElement(createButtons, 'Expected a create workflow button'))

        fireEvent.change(screen.getByPlaceholderText('e.g., Welcome New Surrogates'), {
            target: { value: 'Task Due Reminder' },
        })

        const triggerSelect = screen.getByRole('combobox', { name: 'Trigger type' })
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

    it.each([
        { policyVersion: 1, permissions: [], labels: ['Surrogate'] },
        { policyVersion: 1, permissions: ['view_donors'], labels: ['Surrogate'] },
        {
            policyVersion: 1,
            permissions: ['view_donors', 'edit_donors'],
            labels: ['Surrogate', 'Egg Donor', 'Sperm Donor'],
        },
        { policyVersion: 2, permissions: ['manage_automation'], labels: ['Surrogate'] },
        {
            policyVersion: 2,
            permissions: ['manage_automation', 'view_donors'],
            labels: ['Surrogate', 'Egg Donor', 'Sperm Donor'],
        },
    ])('offers donor record types only with the donor create permission (v$policyVersion, $permissions)', ({ policyVersion, permissions, labels }) => {
        mockUseEffectivePermissions.mockReturnValue({ data: { policy_version: policyVersion, permissions } })

        renderAutomationPage()
        fireEvent.click(
            getLastElement(
                screen.getAllByRole('button', { name: /create workflow/i }),
                'Expected a create workflow button',
            ),
        )

        const recordTypeOptions = Array.from(
            screen.getByRole('combobox', { name: 'Record type' }).querySelectorAll('option'),
        )
            .filter((option) => option.value)
            .map((option) => option.textContent)
        expect(recordTypeOptions).toEqual(labels)
    })

    it('creates an egg donor workflow from subject-specific options', () => {
        mockUseEffectivePermissions.mockReturnValue({ data: { permissions: ['view_donors', 'edit_donors'] } })
        mockUseWorkflowOptions.mockImplementation(
            (_scope: string, subjectType: string) => ({
                data: subjectType === 'egg_donor'
                    ? {
                        trigger_types: [
                            { value: 'donor_created', label: 'Donor Created', description: '' },
                        ],
                        action_types: [
                            { value: 'add_note', label: 'Add Note', description: '' },
                        ],
                        action_types_by_trigger: { donor_created: ['add_note'] },
                        trigger_entity_types: { donor_created: 'egg_donor' },
                        condition_fields: ['education'],
                        condition_operators: [],
                        update_fields: ['education'],
                        email_variables: [],
                        email_templates: [],
                        users: [],
                        queues: [],
                        statuses: [],
                    }
                    : {
                        trigger_types: [
                            { value: 'surrogate_created', label: 'Surrogate Created', description: '' },
                        ],
                        action_types: [
                            { value: 'add_note', label: 'Add Note', description: '' },
                        ],
                        action_types_by_trigger: { surrogate_created: ['add_note'] },
                        trigger_entity_types: { surrogate_created: 'surrogate' },
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
            }),
        )

        renderAutomationPage()
        fireEvent.click(
            getLastElement(
                screen.getAllByRole('button', { name: /create workflow/i }),
                'Expected a create workflow button',
            ),
        )

        fireEvent.change(screen.getByRole('combobox', { name: 'Record type' }), {
            target: { value: 'egg_donor' },
        })
        fireEvent.change(screen.getByPlaceholderText('e.g., Welcome New Egg Donors'), {
            target: { value: 'Egg donor welcome' },
        })
        fireEvent.change(screen.getByRole('combobox', { name: 'Trigger type' }), {
            target: { value: 'donor_created' },
        })
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /add action/i }))
        fireEvent.change(screen.getByRole('combobox', { name: 'Action type 1' }), {
            target: { value: 'add_note' },
        })
        fireEvent.change(screen.getByPlaceholderText('Note content'), {
            target: { value: 'Welcome call requested' },
        })
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(
            getLastElement(
                screen.getAllByRole('button', { name: /create workflow/i }),
                'Expected a save workflow button',
            ),
        )

        expect(mockUseWorkflowOptions).toHaveBeenCalledWith('personal', 'egg_donor')
        expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
            expect.objectContaining({
                subject_type: 'egg_donor',
                trigger_type: 'donor_created',
            }),
            expect.any(Object),
        )
    })

    it('offers only canonical donor sources for an Update Field source action', () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ['view_donors', 'edit_donors'] },
        })
        mockUseWorkflowOptions.mockReturnValue({
            data: {
                trigger_types: [
                    { value: 'donor_created', label: 'Donor Created', description: '' },
                ],
                action_types: [
                    { value: 'update_field', label: 'Update Field', description: '' },
                ],
                action_types_by_trigger: { donor_created: ['update_field'] },
                trigger_entity_types: { donor_created: 'egg_donor' },
                condition_fields: [],
                condition_operators: [],
                update_fields: ['source', 'education'],
                email_variables: [],
                email_templates: [],
                users: [],
                queues: [],
                statuses: [],
            },
            isLoading: false,
        })

        renderAutomationPage()
        fireEvent.click(
            getLastElement(
                screen.getAllByRole('button', { name: /create workflow/i }),
                'Expected a create workflow button',
            ),
        )
        fireEvent.change(screen.getByRole('combobox', { name: 'Record type' }), {
            target: { value: 'egg_donor' },
        })
        fireEvent.change(screen.getByPlaceholderText('e.g., Welcome New Egg Donors'), {
            target: { value: 'Set donor source' },
        })
        fireEvent.change(screen.getByRole('combobox', { name: 'Trigger type' }), {
            target: { value: 'donor_created' },
        })
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /add action/i }))
        fireEvent.change(screen.getByRole('combobox', { name: 'Action type 1' }), {
            target: { value: 'update_field' },
        })
        fireEvent.change(screen.getByRole('combobox', { name: 'Field to update 1' }), {
            target: { value: 'source' },
        })

        expect(screen.queryByPlaceholderText('Value')).not.toBeInTheDocument()
        const sourceSelect = screen.getByRole('combobox', { name: 'Source value 1' })
        const sourceOptions = Array.from(sourceSelect.querySelectorAll('option'))
            .filter((option) => option.value)
            .map((option) => [option.value, option.textContent])
        expect(sourceOptions).toEqual([
            ['manual', 'Manual'],
            ['meta', 'Meta'],
            ['tiktok', 'TikTok'],
            ['google', 'Google'],
            ['website', 'Website'],
            ['referral', 'Referral'],
            ['agency', 'Agency'],
            ['import', 'Import'],
            ['other', 'Other'],
        ])
        fireEvent.change(sourceSelect, { target: { value: 'tiktok' } })
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(
            getLastElement(
                screen.getAllByRole('button', { name: /create workflow/i }),
                'Expected a save workflow button',
            ),
        )

        expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
            expect.objectContaining({
                subject_type: 'egg_donor',
                actions: [expect.objectContaining({
                    action_type: 'update_field',
                    field: 'source',
                    value: 'tiktok',
                })],
            }),
            expect.any(Object),
        )
    })

    it('keeps an existing donor workflow subject visible and immutable', () => {
        mockUseWorkflows.mockReturnValue({
            data: [{
                id: 'workflow-egg',
                name: 'Egg donor follow-up',
                description: null,
                icon: 'activity',
                subject_type: 'egg_donor',
                trigger_type: 'donor_created',
                is_enabled: true,
                run_count: 0,
                last_run_at: null,
                last_error: null,
                created_at: '2026-08-29T00:00:00Z',
                can_edit: true,
            }],
            isLoading: false,
        })
        mockUseWorkflow.mockReturnValue({
            data: {
                id: 'workflow-egg',
                name: 'Egg donor follow-up',
                description: null,
                scope: 'personal',
                subject_type: 'egg_donor',
                trigger_type: 'donor_created',
                trigger_config: {},
                conditions: [],
                condition_logic: 'AND',
                actions: [{ action_type: 'add_note', content: 'Call donor' }],
            },
            isLoading: false,
        })

        renderAutomationPage()
        expect(screen.getByText('Egg Donor')).toBeInTheDocument()
        fireEvent.click(
            screen.getByRole('button', { name: 'Actions for workflow Egg donor follow-up' }),
        )
        fireEvent.click(screen.getByRole('button', { name: 'Edit' }))

        const subject = screen.getByLabelText('Record type')
        expect(subject).toHaveValue('Egg Donor')
        expect(subject).toBeDisabled()
    })

    it('tests an egg donor workflow against egg donor records', async () => {
        mockTestWorkflow.mutate.mockImplementation((_payload, callbacks) => callbacks.onSuccess({
            conditions_matched: true,
            conditions_evaluated: [],
            actions_preview: [{ action_type: 'create_task', description: "create_task: Create task 'Call donor' due in 1 day(s)" }],
        }))
        mockUseWorkflows.mockReturnValue({
            data: [{
                id: 'workflow-egg',
                name: 'Egg donor follow-up',
                description: null,
                icon: 'activity',
                subject_type: 'egg_donor',
                trigger_type: 'task_due',
                is_enabled: true,
                run_count: 0,
                last_run_at: null,
                last_error: null,
                created_at: '2026-08-29T00:00:00Z',
                can_edit: true,
            }],
            isLoading: false,
        })
        mockListDonors.mockResolvedValue({
            items: [{
                id: 'donor-egg-1',
                donor_number: 'D10001',
                full_name: 'Maya Thompson',
                status_label: 'New',
            }],
            total: 1,
            page: 1,
            per_page: 5,
            pages: 1,
        })

        renderAutomationPage()
        fireEvent.click(screen.getByRole('button', { name: /test workflow/i }))

        const donorPicker = screen.getByLabelText('Egg Donor')
        expect(donorPicker).toHaveAttribute('placeholder', 'Search egg donors')
        expect(donorPicker).not.toHaveAttribute('list')
        await waitFor(() => {
            expect(mockListDonors).toHaveBeenCalledWith(expect.objectContaining({
                donor_type: 'egg',
                per_page: 5,
            }))
        })

        fireEvent.change(donorPicker, { target: { value: 'Maya' } })
        expect(screen.getByRole('button', { name: 'Run Test' })).toBeDisabled()

        fireEvent.click(await screen.findByRole('button', { name: /D10001 — Maya Thompson/ }))
        expect(donorPicker).toHaveValue('D10001 — Maya Thompson')
        expect(screen.queryByDisplayValue('donor-egg-1')).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Run Test' }))

        expect(mockTestWorkflow.mutate).toHaveBeenCalledWith(
            {
                id: 'workflow-egg',
                entityId: 'donor-egg-1',
                entityType: 'egg_donor',
            },
            expect.any(Object),
        )
        expect(screen.getByText("Create task 'Call donor' due in 1 day(s)")).toBeInTheDocument()
        expect(screen.queryByText(/create_task/)).not.toBeInTheDocument()
    })

    it('does not accept a free-form donor UUID in the test workflow picker', () => {
        mockUseWorkflows.mockReturnValue({
            data: [{
                id: 'workflow-egg',
                name: 'Egg donor follow-up',
                description: null,
                icon: 'activity',
                subject_type: 'egg_donor',
                trigger_type: 'task_due',
                is_enabled: true,
                run_count: 0,
                last_run_at: null,
                last_error: null,
                created_at: '2026-08-29T00:00:00Z',
                can_edit: true,
            }],
            isLoading: false,
        })

        renderAutomationPage()
        fireEvent.click(screen.getByRole('button', { name: /test workflow/i }))
        fireEvent.change(screen.getByLabelText('Egg Donor'), {
            target: { value: '9a3b51b0-4e20-4ba5-97fa-2721999d3cae' },
        })

        fireEvent.click(screen.getByRole('button', { name: 'Run Test' }))
        expect(mockTestWorkflow.mutate).not.toHaveBeenCalled()
        expect(screen.getByRole('button', { name: 'Run Test' })).toBeDisabled()
    })

    it('shows exact donor identities in execution history and hides unavailable IDs', () => {
        mockUseWorkflows.mockReturnValue({
            data: [{
                id: 'workflow-egg',
                name: 'Egg donor follow-up',
                description: null,
                icon: 'activity',
                subject_type: 'egg_donor',
                trigger_type: 'task_due',
                is_enabled: true,
                run_count: 2,
                last_run_at: '2026-08-29T00:00:00Z',
                last_error: null,
                created_at: '2026-08-29T00:00:00Z',
                can_edit: true,
            }],
            isLoading: false,
        })
        mockUseWorkflowExecutions.mockReturnValue({
            data: {
                items: [
                    {
                        id: 'execution-exact',
                        workflow_id: 'workflow-egg',
                        event_id: 'event-exact',
                        depth: 0,
                        event_source: 'user',
                        entity_type: 'task',
                        entity_id: 'task-exact',
                        subject_type: 'egg_donor',
                        subject_id: 'donor-private-id',
                        entity_name: 'Maya Thompson',
                        entity_number: 'D10001',
                        trigger_event: {},
                        matched_conditions: true,
                        actions_executed: [],
                        status: 'running',
                        error_message: null,
                        duration_ms: 8,
                        executed_at: '2026-08-29T00:00:00Z',
                    },
                    {
                        id: 'execution-unavailable',
                        workflow_id: 'workflow-egg',
                        event_id: 'event-unavailable',
                        depth: 0,
                        event_source: 'user',
                        entity_type: 'task',
                        entity_id: 'task-unavailable',
                        subject_type: 'egg_donor',
                        subject_id: 'donor-hidden-id',
                        entity_name: null,
                        entity_number: null,
                        trigger_event: {},
                        matched_conditions: true,
                        actions_executed: [],
                        status: 'success',
                        error_message: null,
                        duration_ms: 5,
                        executed_at: '2026-08-28T00:00:00Z',
                    },
                ],
                total: 2,
                page: 1,
                pages: 1,
            },
            isLoading: false,
        })

        renderAutomationPage()
        fireEvent.click(
            screen.getByRole('button', { name: 'Actions for workflow Egg donor follow-up' }),
        )
        fireEvent.click(screen.getByRole('button', { name: 'View History' }))

        expect(screen.getByRole('link', { name: 'D10001 — Maya Thompson' })).toHaveAttribute(
            'href',
            '/donors/donor-private-id',
        )
        expect(screen.getByText('Running')).toHaveClass('border-blue-500/20')
        expect(screen.getByText('Donor unavailable')).toBeInTheDocument()
        expect(screen.queryByRole('link', { name: 'Donor unavailable' })).not.toBeInTheDocument()
        expect(screen.queryByText(/donor-(private|hidden)-id/i)).not.toBeInTheDocument()
    })

    it('configures the returned assign-donor action without surrogate controls', () => {
        mockUseEffectivePermissions.mockReturnValue({ data: { permissions: ['view_donors', 'edit_donors'] } })
        mockUseWorkflowOptions.mockImplementation(
            (_scope: string, subjectType: string) => ({
                data: {
                    trigger_types: subjectType === 'sperm_donor'
                        ? [{ value: 'donor_created', label: 'Donor Created', description: '' }]
                        : [{ value: 'surrogate_created', label: 'Surrogate Created', description: '' }],
                    action_types: subjectType === 'sperm_donor'
                        ? [{ value: 'assign_donor', label: 'Assign Donor', description: '' }]
                        : [{ value: 'assign_surrogate', label: 'Assign Surrogate', description: '' }],
                    action_types_by_trigger: subjectType === 'sperm_donor'
                        ? { donor_created: ['assign_donor'] }
                        : { surrogate_created: ['assign_surrogate'] },
                    trigger_entity_types: subjectType === 'sperm_donor'
                        ? { donor_created: 'sperm_donor' }
                        : { surrogate_created: 'surrogate' },
                    condition_fields: [],
                    condition_operators: [],
                    update_fields: [],
                    email_variables: [],
                    email_templates: [],
                    users: [{ id: 'user-1', display_name: 'Alex Owner' }],
                    queues: [],
                    statuses: [],
                },
                isLoading: false,
            }),
        )

        renderAutomationPage()
        fireEvent.click(
            getLastElement(
                screen.getAllByRole('button', { name: /create workflow/i }),
                'Expected a create workflow button',
            ),
        )
        fireEvent.change(screen.getByRole('combobox', { name: 'Record type' }), {
            target: { value: 'sperm_donor' },
        })
        fireEvent.change(screen.getByPlaceholderText('e.g., Welcome New Sperm Donors'), {
            target: { value: 'Assign sperm donor' },
        })
        fireEvent.change(screen.getByRole('combobox', { name: 'Trigger type' }), {
            target: { value: 'donor_created' },
        })
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /add action/i }))
        fireEvent.change(screen.getByRole('combobox', { name: 'Action type 1' }), {
            target: { value: 'assign_donor' },
        })

        expect(screen.getByRole('option', { name: 'Assign Donor' })).toBeInTheDocument()
        expect(screen.queryByRole('option', { name: 'Assign Surrogate' })).not.toBeInTheDocument()
        fireEvent.change(screen.getByRole('combobox', { name: 'Assignment owner type' }), {
            target: { value: 'user' },
        })
        fireEvent.change(screen.getByRole('combobox', { name: 'Assignment owner' }), {
            target: { value: 'user-1' },
        })
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(
            getLastElement(
                screen.getAllByRole('button', { name: /create workflow/i }),
                'Expected a save workflow button',
            ),
        )

        expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
            expect.objectContaining({
                subject_type: 'sperm_donor',
                actions: [{
                    action_type: 'assign_donor',
                    owner_type: 'user',
                    owner_id: 'user-1',
                }],
            }),
            expect.any(Object),
        )
    })

    it('configures a returned donor messaging action with mandatory approval', () => {
        mockUseEffectivePermissions.mockReturnValue({ data: { permissions: ['view_donors', 'edit_donors'] } })
        mockUseWorkflowOptions.mockImplementation(
            (_scope: string, subjectType: string) => ({
                data: {
                    trigger_types: subjectType === 'egg_donor'
                        ? [{ value: 'donor_created', label: 'Donor Created', description: '' }]
                        : [{ value: 'surrogate_created', label: 'Surrogate Created', description: '' }],
                    action_types: [{ value: 'send_message', label: 'Send SMS/MMS', description: '' }],
                    action_types_by_trigger: subjectType === 'egg_donor'
                        ? { donor_created: ['send_message'] }
                        : { surrogate_created: ['send_message'] },
                    trigger_entity_types: subjectType === 'egg_donor'
                        ? { donor_created: 'egg_donor' }
                        : { surrogate_created: 'surrogate' },
                    condition_fields: [],
                    condition_operators: [],
                    update_fields: [],
                    email_variables: [],
                    email_templates: [],
                    message_templates: [{
                        id: 'message-template-1',
                        name: 'Screening reminder',
                        purpose: 'operational',
                        version: 2,
                    }],
                    users: [],
                    queues: [],
                    statuses: [],
                },
                isLoading: false,
            }),
        )

        renderAutomationPage()
        fireEvent.click(
            getLastElement(
                screen.getAllByRole('button', { name: /create workflow/i }),
                'Expected a create workflow button',
            ),
        )
        fireEvent.change(screen.getByRole('combobox', { name: 'Record type' }), {
            target: { value: 'egg_donor' },
        })
        fireEvent.change(screen.getByPlaceholderText('e.g., Welcome New Egg Donors'), {
            target: { value: 'Egg donor SMS reminder' },
        })
        fireEvent.change(screen.getByRole('combobox', { name: 'Trigger type' }), {
            target: { value: 'donor_created' },
        })
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /add action/i }))
        fireEvent.change(screen.getByRole('combobox', { name: 'Action type 1' }), {
            target: { value: 'send_message' },
        })
        fireEvent.change(screen.getByRole('combobox', { name: 'Message purpose' }), {
            target: { value: 'operational' },
        })
        fireEvent.change(screen.getByRole('combobox', { name: 'Message template' }), {
            target: { value: 'message-template-1' },
        })
        expect(screen.getByRole('switch', { name: 'Requires Approval' }))
            .toHaveAttribute('aria-disabled', 'true')
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(
            getLastElement(
                screen.getAllByRole('button', { name: /create workflow/i }),
                'Expected a save workflow button',
            ),
        )
        expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
            expect.objectContaining({
                subject_type: 'egg_donor',
                actions: [{
                    action_type: 'send_message',
                    purpose: 'operational',
                    message_template_version_id: 'message-template-1',
                    requires_approval: true,
                }],
            }),
            expect.any(Object),
        )
    })

    it('saves a form-submitted workflow with the form submission subject', () => {
        mockUseWorkflowOptions.mockReturnValue({
            data: {
                trigger_types: [
                    { value: 'form_submitted', label: 'Application Submitted', description: '' },
                ],
                action_types: [
                    { value: 'create_intake_lead', label: 'Create Intake Lead', description: '' },
                ],
                action_types_by_trigger: { form_submitted: ['create_intake_lead'] },
                trigger_entity_types: { form_submitted: 'form_submission' },
                condition_fields: [],
                condition_operators: [],
                update_fields: [],
                email_variables: [],
                email_templates: [],
                users: [],
                queues: [],
                statuses: [],
                forms: [{ id: 'form-surrogate', name: 'Surrogate Application', lead_kind: 'surrogate' }],
            },
            isLoading: false,
        })

        renderAutomationPage()
        fireEvent.click(
            getLastElement(
                screen.getAllByRole('button', { name: /create workflow/i }),
                'Expected a create workflow button',
            ),
        )
        fireEvent.change(screen.getByPlaceholderText('e.g., Welcome New Surrogates'), {
            target: { value: 'Route applications' },
        })
        fireEvent.change(screen.getByRole('combobox', { name: 'Trigger type' }), {
            target: { value: 'form_submitted' },
        })
        const formSelect = getFirstElement(
            screen.getAllByTestId('select').filter((select) =>
                select.querySelector('option[value="form-surrogate"]'),
            ),
            'Expected a form select',
        )
        fireEvent.change(formSelect, { target: { value: 'form-surrogate' } })
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /add action/i }))
        fireEvent.change(screen.getByRole('combobox', { name: 'Action type 1' }), {
            target: { value: 'create_intake_lead' },
        })
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        expect(screen.getByText('Form Submission')).toBeInTheDocument()
        fireEvent.click(
            getLastElement(
                screen.getAllByRole('button', { name: /create workflow/i }),
                'Expected a save workflow button',
            ),
        )

        expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
            expect.objectContaining({
                subject_type: 'form_submission',
                trigger_type: 'form_submitted',
                trigger_config: { form_id: 'form-surrogate' },
            }),
            expect.any(Object),
        )
    })

    describe('Application Submitted stage updates', () => {
        const intakeOptions = (subjectType: string) => {
            const isEggDonor = subjectType === 'egg_donor'
            return {
                data: {
                    trigger_types: [
                        { value: 'form_submitted', label: 'Application Submitted', description: '' },
                    ],
                    action_types: [
                        { value: 'update_field', label: 'Update Field', description: '' },
                    ],
                    action_types_by_trigger: { form_submitted: ['update_field'] },
                    trigger_entity_types: { form_submitted: 'form_submission' },
                    condition_fields: ['stage_id', 'lead_kind'],
                    condition_operators: [{ value: 'in', label: 'Is one of' }],
                    update_fields: isEggDonor
                        ? ['stage_id', 'education', 'source']
                        : ['stage_id', 'is_priority'],
                    email_variables: [],
                    email_templates: [],
                    users: [],
                    queues: [],
                    statuses: isEggDonor
                        ? [{ id: 'egg-contacted', value: 'contacted', label: 'Egg Donor Contacted', is_active: true }]
                        : [{ id: 'surrogate-contacted', value: 'contacted', label: 'Surrogate Contacted', is_active: true }],
                    forms: [
                        { id: 'form-surrogate', name: 'Surrogate Application', lead_kind: 'surrogate' },
                        { id: 'form-egg-donor', name: 'Egg Donor Application', lead_kind: 'egg_donor' },
                        {
                            id: 'form-shared-donor',
                            name: 'Donor Application',
                            lead_kind: 'egg_donor',
                            lead_kinds: ['egg_donor', 'sperm_donor'],
                        },
                    ],
                },
                isLoading: false,
            }
        }

        const createStageUpdate = (formId: string) => {
            renderAutomationPage()
            fireEvent.click(
                getLastElement(
                    screen.getAllByRole('button', { name: /create workflow/i }),
                    'Expected a create workflow button',
                ),
            )
            fireEvent.change(screen.getByPlaceholderText('e.g., Welcome New Surrogates'), {
                target: { value: 'Move applicants' },
            })
            fireEvent.change(screen.getByRole('combobox', { name: 'Trigger type' }), {
                target: { value: 'form_submitted' },
            })
            const formSelect = getFirstElement(
                screen.getAllByTestId('select').filter((select) =>
                    select.querySelector(`option[value="${formId}"]`),
                ),
                'Expected a form select',
            )
            fireEvent.change(formSelect, { target: { value: formId } })
            fireEvent.click(screen.getByRole('button', { name: /next/i }))
            fireEvent.click(screen.getByRole('button', { name: /next/i }))
            fireEvent.click(screen.getByRole('button', { name: /add action/i }))
            fireEvent.change(screen.getByRole('combobox', { name: 'Action type 1' }), {
                target: { value: 'update_field' },
            })
        }

        const optionLabels = (select: HTMLElement) =>
            Array.from(select.querySelectorAll('option'))
                .filter((option) => option.value)
                .map((option) => option.textContent)

        beforeEach(() => {
            mockUseEffectivePermissions.mockReturnValue({
                data: { permissions: ['view_donors', 'edit_donors'] },
            })
            mockUseWorkflowOptions.mockImplementation(
                (_scope: string, subjectType: string) => intakeOptions(subjectType),
            )
        })

        it.each([
            {
                formId: 'form-surrogate',
                fields: ['Stage', 'Is Priority'],
                stages: ['Surrogate Contacted'],
                stageId: 'surrogate-contacted',
            },
            {
                formId: 'form-egg-donor',
                fields: ['Stage', 'Education', 'Source'],
                stages: ['Egg Donor Contacted'],
                stageId: 'egg-contacted',
            },
        ])('offers the $formId record fields and stages and saves the stage', ({ formId, fields, stages, stageId }) => {
            createStageUpdate(formId)

            expect(optionLabels(screen.getByRole('combobox', { name: 'Field to update 1' }))).toEqual(fields)
            fireEvent.change(screen.getByRole('combobox', { name: 'Field to update 1' }), {
                target: { value: 'stage_id' },
            })
            const stageSelect = screen.getByRole('combobox', { name: 'Stage value 1' })
            expect(optionLabels(stageSelect)).toEqual(stages)
            fireEvent.change(stageSelect, { target: { value: stageId } })
            fireEvent.click(screen.getByRole('button', { name: /next/i }))
            fireEvent.click(
                getLastElement(
                    screen.getAllByRole('button', { name: /create workflow/i }),
                    'Expected a save workflow button',
                ),
            )

            expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
                expect.objectContaining({
                    subject_type: 'form_submission',
                    trigger_type: 'form_submitted',
                    trigger_config: { form_id: formId },
                    actions: [expect.objectContaining({
                        action_type: 'update_field',
                        field: 'stage_id',
                        value: stageId,
                    })],
                }),
                expect.any(Object),
            )
        })

        it('offers no stage references for a form shared by both donor types', () => {
            renderAutomationPage()
            fireEvent.click(
                getLastElement(
                    screen.getAllByRole('button', { name: /create workflow/i }),
                    'Expected a create workflow button',
                ),
            )
            fireEvent.change(screen.getByPlaceholderText('e.g., Welcome New Surrogates'), {
                target: { value: 'Donor applicants' },
            })
            fireEvent.change(screen.getByRole('combobox', { name: 'Trigger type' }), {
                target: { value: 'form_submitted' },
            })
            const formSelect = getFirstElement(
                screen.getAllByTestId('select').filter((select) =>
                    select.querySelector('option[value="form-shared-donor"]'),
                ),
                'Expected a form select',
            )
            fireEvent.change(formSelect, { target: { value: 'form-shared-donor' } })
            fireEvent.click(screen.getByRole('button', { name: /next/i }))
            fireEvent.click(screen.getByRole('button', { name: /add condition/i }))

            const conditionFieldSelect = getFirstElement(
                screen.getAllByTestId('select').filter((select) =>
                    select.querySelector('option[value="lead_kind"]'),
                ),
                'Expected a condition field select',
            )
            expect(optionLabels(conditionFieldSelect)).toEqual(['Applicant Type'])

            fireEvent.click(screen.getByRole('button', { name: /next/i }))
            fireEvent.click(screen.getByRole('button', { name: /add action/i }))
            fireEvent.change(screen.getByRole('combobox', { name: 'Action type 1' }), {
                target: { value: 'update_field' },
            })

            expect(optionLabels(screen.getByRole('combobox', { name: 'Field to update 1' }))).toEqual([
                'Education',
                'Source',
            ])
        })

        it('blocks saving an existing shared donor form workflow that references a stage', () => {
            mockUseWorkflows.mockReturnValue({
                data: [{
                    id: 'workflow-shared-application',
                    name: 'Shared donor applications',
                    description: null,
                    icon: 'activity',
                    subject_type: 'form_submission',
                    trigger_type: 'form_submitted',
                    is_enabled: true,
                    run_count: 0,
                    last_run_at: null,
                    last_error: null,
                    created_at: '2026-09-28T00:00:00Z',
                    can_edit: true,
                }],
                isLoading: false,
            })
            mockUseWorkflow.mockReturnValue({
                data: {
                    id: 'workflow-shared-application',
                    name: 'Shared donor applications',
                    description: null,
                    scope: 'personal',
                    subject_type: 'form_submission',
                    trigger_type: 'form_submitted',
                    trigger_config: { form_id: 'form-shared-donor' },
                    conditions: [{ field: 'stage_id', operator: 'in', value: [] }],
                    condition_logic: 'AND',
                    actions: [{ action_type: 'add_note', content: 'Review' }],
                },
                isLoading: false,
            })

            renderAutomationPage()
            fireEvent.click(
                screen.getByRole('button', { name: 'Actions for workflow Shared donor applications' }),
            )
            fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
            fireEvent.click(screen.getByRole('button', { name: /next/i }))
            fireEvent.click(screen.getByRole('button', { name: /next/i }))

            expect(screen.getByText('Stage references need a form for one donor type.')).toBeInTheDocument()
            expect(mockUpdateWorkflow.mutate).not.toHaveBeenCalled()
        })

        it('keeps stage conditions when an existing donor application workflow is saved', () => {
            mockUseWorkflows.mockReturnValue({
                data: [{
                    id: 'workflow-egg-application',
                    name: 'Egg donor applications',
                    description: null,
                    icon: 'activity',
                    subject_type: 'form_submission',
                    trigger_type: 'form_submitted',
                    is_enabled: true,
                    run_count: 0,
                    last_run_at: null,
                    last_error: null,
                    created_at: '2026-09-28T00:00:00Z',
                    can_edit: true,
                }],
                isLoading: false,
            })
            mockUseWorkflow.mockReturnValue({
                data: {
                    id: 'workflow-egg-application',
                    name: 'Egg donor applications',
                    description: null,
                    scope: 'personal',
                    subject_type: 'form_submission',
                    trigger_type: 'form_submitted',
                    trigger_config: { form_id: 'form-egg-donor', lead_kind: 'egg_donor' },
                    conditions: [
                        { field: 'stage_id', operator: 'in', value: ['egg-contacted'], stage_keys: ['contacted'] },
                    ],
                    condition_logic: 'AND',
                    actions: [
                        { action_type: 'update_field', field: 'stage_id', value: 'egg-contacted', value_stage_key: 'contacted' },
                    ],
                },
                isLoading: false,
            })

            renderAutomationPage()
            fireEvent.click(
                screen.getByRole('button', { name: 'Actions for workflow Egg donor applications' }),
            )
            fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
            fireEvent.click(screen.getByRole('button', { name: /next/i }))
            fireEvent.click(screen.getByRole('button', { name: /next/i }))
            expect(optionLabels(screen.getByRole('combobox', { name: 'Stage value 1' }))).toEqual([
                'Egg Donor Contacted',
            ])
            fireEvent.click(screen.getByRole('button', { name: /next/i }))
            fireEvent.click(screen.getByRole('button', { name: /save changes/i }))

            expect(mockUseWorkflowOptions).toHaveBeenCalledWith('personal', 'egg_donor')
            expect(mockUpdateWorkflow.mutate).toHaveBeenCalledWith(
                expect.objectContaining({
                    id: 'workflow-egg-application',
                    data: expect.objectContaining({
                        conditions: [
                            expect.objectContaining({ field: 'stage_id', operator: 'in', value: ['egg-contacted'] }),
                        ],
                        actions: [expect.objectContaining({ field: 'stage_id', value: 'egg-contacted' })],
                    }),
                }),
                expect.any(Object),
            )
        })
    })

    it('drops surrogate-only promotion options for donor intake forms', () => {
        mockUseWorkflowOptions.mockReturnValue({
            data: {
                trigger_types: [
                    { value: 'intake_lead_created', label: 'Intake Lead Created', description: '' },
                ],
                action_types: [
                    { value: 'promote_intake_lead', label: 'Promote Intake Lead', description: '' },
                ],
                action_types_by_trigger: { intake_lead_created: ['promote_intake_lead'] },
                trigger_entity_types: { intake_lead_created: 'intake_lead' },
                condition_fields: [],
                condition_operators: [],
                update_fields: [],
                email_variables: [],
                email_templates: [],
                users: [],
                queues: [],
                statuses: [],
                forms: [
                    { id: 'form-surrogate', name: 'Surrogate Application', lead_kind: 'surrogate' },
                    { id: 'form-egg-donor', name: 'Egg Donor Application', lead_kind: 'egg_donor' },
                ],
            },
            isLoading: false,
        })
        const selectForm = (formId: string) => {
            const formSelect = getFirstElement(
                screen.getAllByTestId('select').filter((select) =>
                    select.querySelector(`option[value="${formId}"]`),
                ),
                'Expected a form select',
            )
            fireEvent.change(formSelect, { target: { value: formId } })
        }
        const promotionSwitch = (label: string) => {
            const promotionSwitchElement = screen.getByText(label).parentElement?.querySelector('[role="switch"]')
            if (!promotionSwitchElement) throw new Error(`Expected the ${label} switch`)
            return promotionSwitchElement
        }

        renderAutomationPage()
        fireEvent.click(
            getLastElement(
                screen.getAllByRole('button', { name: /create workflow/i }),
                'Expected a create workflow button',
            ),
        )
        fireEvent.change(screen.getByPlaceholderText('e.g., Welcome New Surrogates'), {
            target: { value: 'Promote leads' },
        })
        fireEvent.change(screen.getByRole('combobox', { name: 'Trigger type' }), {
            target: { value: 'intake_lead_created' },
        })
        selectForm('form-surrogate')
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /add action/i }))
        fireEvent.change(screen.getByRole('combobox', { name: 'Action type 1' }), {
            target: { value: 'promote_intake_lead' },
        })
        fireEvent.click(promotionSwitch('Mark as priority'))
        fireEvent.click(promotionSwitch('Assign to workflow owner if available'))

        fireEvent.click(screen.getByRole('button', { name: /back/i }))
        fireEvent.click(screen.getByRole('button', { name: /back/i }))
        selectForm('form-egg-donor')
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        expect(screen.queryByText('Mark as priority')).not.toBeInTheDocument()
        expect(screen.queryByText('Assign to workflow owner if available')).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(
            getLastElement(
                screen.getAllByRole('button', { name: /create workflow/i }),
                'Expected a save workflow button',
            ),
        )

        const payload = mockCreateWorkflow.mutate.mock.calls.at(-1)?.[0]
        expect(payload).toMatchObject({
            subject_type: 'intake_lead',
            trigger_type: 'intake_lead_created',
            trigger_config: { form_id: 'form-egg-donor' },
        })
        expect(payload.actions).toHaveLength(1)
        expect(payload.actions[0].action_type).toBe('promote_intake_lead')
        expect(payload.actions[0]).not.toHaveProperty('is_priority')
        expect(payload.actions[0]).not.toHaveProperty('assign_to_user')
    })

    it('keeps approval optional for donor email actions', () => {
        mockUseEffectivePermissions.mockReturnValue({ data: { permissions: ['view_donors', 'edit_donors'] } })
        mockUseWorkflowOptions.mockImplementation(
            (_scope: string, subjectType: string) => ({
                data: {
                    trigger_types: subjectType === 'egg_donor'
                        ? [{ value: 'donor_created', label: 'Donor Created', description: '' }]
                        : [{ value: 'surrogate_created', label: 'Surrogate Created', description: '' }],
                    action_types: [{ value: 'send_email', label: 'Send Email', description: '' }],
                    action_types_by_trigger: subjectType === 'egg_donor'
                        ? { donor_created: ['send_email'] }
                        : { surrogate_created: ['send_email'] },
                    trigger_entity_types: subjectType === 'egg_donor'
                        ? { donor_created: 'egg_donor' }
                        : { surrogate_created: 'surrogate' },
                    condition_fields: [],
                    condition_operators: [],
                    update_fields: [],
                    email_variables: [],
                    email_templates: [{ id: 'email-template-1', name: 'Donor welcome' }],
                    users: [],
                    queues: [],
                    statuses: [],
                },
                isLoading: false,
            }),
        )

        renderAutomationPage()
        fireEvent.click(
            getLastElement(
                screen.getAllByRole('button', { name: /create workflow/i }),
                'Expected a create workflow button',
            ),
        )
        fireEvent.change(screen.getByRole('combobox', { name: 'Record type' }), {
            target: { value: 'egg_donor' },
        })
        fireEvent.change(screen.getByPlaceholderText('e.g., Welcome New Egg Donors'), {
            target: { value: 'Egg donor welcome email' },
        })
        fireEvent.change(screen.getByRole('combobox', { name: 'Trigger type' }), {
            target: { value: 'donor_created' },
        })
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /add action/i }))
        fireEvent.change(screen.getByRole('combobox', { name: 'Action type 1' }), {
            target: { value: 'send_email' },
        })
        const templateSelect = getFirstElement(
            screen.getAllByTestId('select').filter((select) =>
                select.querySelector('option[value="email-template-1"]'),
            ),
            'Expected an email template select',
        )
        fireEvent.change(templateSelect, { target: { value: 'email-template-1' } })
        const approval = screen.getByRole('switch', { name: 'Requires Approval' })
        expect(approval).not.toHaveAttribute('aria-disabled', 'true')
        expect(approval).toHaveAttribute('aria-checked', 'false')
        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(
            getLastElement(
                screen.getAllByRole('button', { name: /create workflow/i }),
                'Expected a save workflow button',
            ),
        )

        expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
            expect.objectContaining({
                subject_type: 'egg_donor',
                actions: [{
                    action_type: 'send_email',
                    template_id: 'email-template-1',
                    recipients: 'donor',
                }],
            }),
            expect.any(Object),
        )
    })

    it('names the workflow in its history dialog and shows the shared empty state', () => {
        mockUseWorkflows.mockReturnValue({
            data: [{
                id: 'workflow-follow-up',
                name: 'Application Follow-up',
                description: null,
                icon: 'activity',
                subject_type: 'surrogate',
                trigger_type: 'surrogate_created',
                is_enabled: true,
                run_count: 0,
                last_run_at: null,
                last_error: null,
                created_at: '2026-08-29T00:00:00Z',
                can_edit: true,
            }],
            isLoading: false,
        })
        renderAutomationPage()

        fireEvent.click(
            screen.getByRole('button', { name: 'Actions for workflow Application Follow-up' }),
        )
        fireEvent.click(screen.getByRole('button', { name: 'View History' }))

        expect(screen.getByText('History: Application Follow-up')).toBeInTheDocument()
        expect(screen.getByText('No runs yet')).toBeInTheDocument()
        expect(screen.queryByText('Recent workflow execution logs')).not.toBeInTheDocument()
    })

    it("requires organization workflow management for org creation and executions under version 2", () => {
        mockUseEffectivePermissions.mockReturnValue({ data: { policy_version: 2, permissions: ["manage_automation"] } })
        renderAutomationPage()
        const createButtons = screen.getAllByRole("button", { name: "Create Workflow" })
        expect(createButtons.length).toBeGreaterThan(0)
        for (const button of createButtons) expect(button).toBeEnabled()
        expect(screen.queryByRole("button", { name: "Execution History" })).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("tab", { name: "Org Workflows" }))
        expect(screen.queryByRole("button", { name: "Create Org Workflow" })).not.toBeInTheDocument()
    })

    it("hides personal workflow creation without manage_automation under version 2", () => {
        mockUseEffectivePermissions.mockReturnValue({ data: { policy_version: 2, permissions: [] } })
        renderAutomationPage()
        expect(screen.getByText("No personal workflows yet")).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Create Workflow" })).not.toBeInTheDocument()
    })

    it("shows org creation and Execution History with manage_org_workflows under version 2", () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: { policy_version: 2, permissions: ["manage_automation", "manage_org_workflows"] },
        })
        renderAutomationPage()
        expect(screen.getByRole("button", { name: "Execution History" })).toBeInTheDocument()
        expect(screen.getAllByRole("button", { name: "Create Org Workflow" }).length).toBeGreaterThan(0)
    })

    it("publishes eligible personal workflows and preserves proposer credit in details", () => {
        mockUseWorkflows.mockReturnValue({ data: [{ id: "private-workflow", name: "Personal workflow", scope: "personal", owner_name: "Owner", proposed_by_name: "Former teammate", can_edit: true, can_publish: true, trigger_type: "status_changed", is_enabled: false, run_count: 0, created_at: "2026-09-01T00:00:00Z" }], isLoading: false })
        renderAutomationPage()
        fireEvent.click(screen.getByRole("button", { name: "Details" }))
        expect(screen.getByText("Former teammate")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Publish to organization" }))
        expect(mockPublishWorkflow.mutate).toHaveBeenCalledWith("private-workflow", expect.any(Object))
    })

})
