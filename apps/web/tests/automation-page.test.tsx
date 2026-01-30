import type { PropsWithChildren, ButtonHTMLAttributes, ReactNode } from "react"
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
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
    }: { children?: ReactNode; render?: (props: ButtonHTMLAttributes<HTMLButtonElement>) => ReactNode } & ButtonHTMLAttributes<HTMLButtonElement>) => {
        if (render) {
            return <>{render({ ...props })}</>
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

vi.mock('@/lib/hooks/use-workflows', () => ({
    useWorkflows: () => mockUseWorkflows(),
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

describe('AutomationPage', () => {
    beforeEach(() => {
        mockUseWorkflows.mockReturnValue({ data: [], isLoading: false })
        mockUseWorkflow.mockReturnValue({ data: null, isLoading: false })
        mockUseWorkflowStats.mockReturnValue({ data: { total_workflows: 0, enabled_workflows: 0, success_rate_24h: 0, total_executions_24h: 0 }, isLoading: false })
        mockUseWorkflowOptions.mockReturnValue({
            data: {
                trigger_types: [
                    { value: 'surrogate_created', label: 'Surrogate Created', description: '' },
                    { value: 'task_due', label: 'Task Due', description: '' },
                ],
                action_types: [
                    { value: 'add_note', label: 'Add Note', description: '' },
                ],
                action_types_by_trigger: { surrogate_created: ['add_note'], task_due: ['add_note'] },
                trigger_entity_types: { surrogate_created: 'surrogate', task_due: 'task' },
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
        render(<AutomationPage />)
        expect(screen.getAllByText('Workflows').length).toBeGreaterThan(0)
    })

    it('shows server validation errors in the wizard', () => {
        mockCreateWorkflow.mutate.mockImplementation((_data: unknown, opts?: { onError?: (err: Error) => void }) => {
            opts?.onError?.(new Error('Action 1: title is required; Action 1: assignee is required'))
        })

        render(<AutomationPage />)

        const createButtons = screen.getAllByRole('button', { name: /create workflow/i })
        fireEvent.click(createButtons[createButtons.length - 1])

        fireEvent.change(screen.getByPlaceholderText('e.g., Welcome New Surrogates'), { target: { value: 'Test Workflow' } })
        fireEvent.change(screen.getAllByTestId('select')[0], { target: { value: 'surrogate_created' } })

        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        fireEvent.click(screen.getByRole('button', { name: /next/i }))

        fireEvent.click(screen.getByRole('button', { name: /add action/i }))
        fireEvent.change(screen.getAllByTestId('select')[0], { target: { value: 'add_note' } })
        fireEvent.change(screen.getByPlaceholderText('Note content'), { target: { value: 'Test note' } })

        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        const saveButtons = screen.getAllByRole('button', { name: /create workflow/i })
        fireEvent.click(saveButtons[saveButtons.length - 1])

        expect(screen.getByText(/fix these errors/i)).toBeInTheDocument()
        expect(screen.getByText(/Action 1: title is required/i)).toBeInTheDocument()
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

        render(<AutomationPage />)

        fireEvent.click(screen.getByRole('button', { name: /test workflow/i }))

        expect(screen.getByText('Task ID')).toBeInTheDocument()
    })
})
