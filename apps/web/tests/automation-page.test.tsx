import type { PropsWithChildren, ButtonHTMLAttributes, ReactNode } from "react"
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
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

    it('creates an egg donor workflow from subject-specific options', () => {
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
                        status: 'success',
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
        expect(screen.getByText('Donor unavailable')).toBeInTheDocument()
        expect(screen.queryByRole('link', { name: 'Donor unavailable' })).not.toBeInTheDocument()
        expect(screen.queryByText(/donor-(private|hidden)-id/i)).not.toBeInTheDocument()
    })

    it('configures the returned assign-donor action without surrogate controls', () => {
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

})
