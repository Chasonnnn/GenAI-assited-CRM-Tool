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
const { mockPush } = vi.hoisted(() => ({ mockPush: vi.fn() }))
vi.mock('next/navigation', () => ({
    useSearchParams: () => ({
        get: vi.fn(() => null),
    }),
    useRouter: () => ({
        push: mockPush,
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
        mockPush.mockReset()
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

    it('hides org workflow creation and Execution History without manage_automation', () => {
        mockUseEffectivePermissions.mockReturnValue({ data: { permissions: [] } })
        render(
            <AutomationPage
                initialTab="workflows"
                initialWorkflowScopeTab="org"
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

    it('opens the editor route for create and edit', () => {
        mockUseWorkflows.mockReturnValue({
            data: [{
                id: 'workflow-edit',
                name: 'Editable workflow',
                description: null,
                icon: 'activity',
                subject_type: 'surrogate',
                trigger_type: 'surrogate_created',
                is_enabled: true,
                run_count: 0,
                last_run_at: null,
                last_error: null,
                created_at: '2026-09-01T00:00:00Z',
                can_edit: true,
            }],
            isLoading: false,
        })
        renderAutomationPage()

        fireEvent.click(screen.getByRole('button', { name: 'Create Workflow' }))
        expect(mockPush).toHaveBeenLastCalledWith('/automation/workflows/new?scope=personal')

        fireEvent.click(screen.getByRole('button', { name: 'Actions for workflow Editable workflow' }))
        fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
        expect(mockPush).toHaveBeenLastCalledWith('/automation/workflows/workflow-edit')
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
