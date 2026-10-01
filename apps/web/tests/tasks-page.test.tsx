import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { renderToString } from 'react-dom/server'
import TasksPage from '../app/(app)/tasks/page'
import { TasksListView } from '@/components/tasks/TasksListView'
import { TasksCalendarView } from '@/components/tasks/TasksCalendarView'
import { TasksApprovalsSection } from '@/components/tasks/TasksApprovalsSection'
import type { TaskListItem } from '@/lib/types/task'
import type { StatusChangeRequestDetail } from '@/lib/api/status-change-requests'
import type { ImportApprovalItem } from '@/lib/api/import'

const mockNavigation = vi.hoisted(() => ({
    searchParams: new URLSearchParams(),
    push: vi.fn(),
    replace: vi.fn(),
}))

vi.mock('next/link', () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
    useSearchParams: () => ({
        get: (key: string) => mockNavigation.searchParams.get(key),
        toString: () => mockNavigation.searchParams.toString(),
    }),
    useRouter: () => ({
        push: mockNavigation.push,
        replace: mockNavigation.replace,
    }),
}))

// Mock localStorage to return "list" for tasks view
Object.defineProperty(window, 'localStorage', {
    value: {
        getItem: vi.fn(() => 'list'),
        setItem: vi.fn(),
        removeItem: vi.fn(),
    },
    writable: true,
})

const mockUseTask = vi.fn()
const mockUseTasks = vi.fn()
const mockCompleteTask = vi.fn()
const mockUncompleteTask = vi.fn()
const mockUpdateTask = vi.fn()
const mockCreateTask = vi.fn()
const mockCreateTaskBatch = vi.fn()
const mockDeleteTask = vi.fn()
const mockBulkCompleteTasks = vi.fn()
const mockResolveApproval = vi.fn()
const mockUsePendingImportApprovals = vi.fn()
const mockApproveImport = vi.fn()
const mockRejectImport = vi.fn()
const mockUseStatusChangeRequests = vi.fn(() => ({
    data: { items: [], total: 0 },
    isLoading: false,
    refetch: vi.fn(),
}))
const mockApproveStatusChange = vi.fn()
const mockRejectStatusChange = vi.fn()
const mockSetAIContext = vi.fn()
const mockClearAIContext = vi.fn()
const mockUseDonors = vi.fn()

const ALL_TASK_PERMISSIONS = ["edit_tasks", "delete_tasks", "view_surrogates", "view_intended_parents", "view_donors"]
const mockPermissions = vi.hoisted(() => ({ value: [] as string[] }))
vi.mock("@/lib/hooks/use-permissions", () => ({ useEffectivePermissions: () => ({ data: { permissions: mockPermissions.value } }) }))

vi.mock('@/lib/hooks/use-tasks', () => ({
    useTask: (id: string) => mockUseTask(id),
    useTasks: (params: unknown) => mockUseTasks(params),
    useCompleteTask: () => ({ mutateAsync: mockCompleteTask }),
    useUncompleteTask: () => ({ mutateAsync: mockUncompleteTask }),
    useUpdateTask: () => ({ mutateAsync: mockUpdateTask }),
    useCreateTask: () => ({ mutateAsync: mockCreateTask, isPending: false }),
    useCreateTaskBatch: () => ({ mutateAsync: mockCreateTaskBatch, isPending: false }),
    useDeleteTask: () => ({ mutateAsync: mockDeleteTask, isPending: false }),
    useBulkCompleteTasks: () => ({ mutateAsync: mockBulkCompleteTasks, isPending: false }),
    useResolveWorkflowApproval: () => ({ mutateAsync: mockResolveApproval, isPending: false }),
}))

vi.mock('@/lib/hooks/use-donors', () => ({
    useDonors: (params: unknown) => mockUseDonors(params),
}))

const mockUseAssignees = vi.fn()
const mockShowUndoToast = vi.fn()
const mockToast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn(), dismiss: vi.fn() }))

vi.mock('@/lib/hooks/use-surrogates', () => ({
    useSurrogates: () => ({ data: { items: [] }, isLoading: false }),
    useAssignees: (options: unknown) => mockUseAssignees(options),
}))

vi.mock('@/components/ui/toast', () => ({ toast: mockToast }))

vi.mock('@/components/ui/undo-toast', () => ({
    showUndoToast: (...args: unknown[]) => mockShowUndoToast(...args),
}))

vi.mock('@/lib/hooks/use-intended-parents', () => ({
    useIntendedParents: () => ({ data: { items: [] }, isLoading: false }),
}))

vi.mock('@/lib/hooks/use-import', () => ({
    usePendingImportApprovals: () => mockUsePendingImportApprovals(),
    useApproveImport: () => ({ mutateAsync: mockApproveImport, isPending: false }),
    useRejectImport: () => ({ mutateAsync: mockRejectImport, isPending: false }),
    useRunImportInline: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/lib/hooks/use-status-change-requests', () => ({
    useStatusChangeRequests: (...args: Parameters<typeof mockUseStatusChangeRequests>) => mockUseStatusChangeRequests(...args),
    useApproveStatusChangeRequest: () => ({ mutateAsync: mockApproveStatusChange, isPending: false }),
    useRejectStatusChangeRequest: () => ({ mutateAsync: mockRejectStatusChange, isPending: false }),
}))

// Mock auth context
const mockCurrentUser = { user_id: 'u1', display_name: 'Test User', role: 'case_manager' }
vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({ user: mockCurrentUser }),
}))

// Mock AI context
vi.mock('@/lib/context/ai-context', () => ({
    useAIContext: () => ({
        setContext: mockSetAIContext,
        clearContext: mockClearAIContext,
    }),
}))

// Mock the UnifiedCalendar component to render nothing in tests
vi.mock('@/components/appointments/UnifiedCalendar', () => ({
    UnifiedCalendar: () => <div>Calendar View</div>,
}))

describe('TasksPage', () => {
    beforeEach(() => {
        mockUseTask.mockReset().mockReturnValue({ isLoading: true })
        mockNavigation.searchParams = new URLSearchParams()
        mockNavigation.push.mockReset()
        mockNavigation.replace.mockReset()
        mockPermissions.value = [...ALL_TASK_PERMISSIONS]
        vi.mocked(window.localStorage.getItem).mockReturnValue('list')
        vi.mocked(window.localStorage.setItem).mockClear()
        Object.defineProperty(Element.prototype, 'scrollIntoView', {
            configurable: true,
            value: vi.fn(),
        })
        mockCurrentUser.role = 'case_manager'
        mockUseTasks.mockImplementation((params: { is_completed?: boolean; task_type?: string; exclude_approvals?: boolean }) => {
            // Return workflow approvals for approval query
            if (params?.task_type === 'workflow_approval' && params?.exclude_approvals === false) {
                return {
                    data: {
                        items: [
                            {
                                id: 'approval-1',
                                title: 'Approve: Assign surrogate to John',
                                task_type: 'workflow_approval',
                                status: 'pending',
                                is_completed: false,
                                due_date: null,
                                due_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(), // 24h from now
                                surrogate_id: 's1',
                                surrogate_number: 'S12345',
                                owner_type: 'user',
                                owner_id: 'u1', // Same as mockCurrentUser
                                owner_name: 'Test User',
                                workflow_action_preview: 'Assign surrogate to John Smith',
                            },
                        ],
                        total: 1,
                    },
                    isLoading: false,
                }
            }
            // Return regular tasks for incomplete tasks query
            if (params?.is_completed === false && params?.exclude_approvals === true) {
                return {
                    data: {
                        items: [
                            {
                                id: 't1',
                                title: 'Follow up with surrogate',
                                is_completed: false,
                                due_date: null,
                                surrogate_id: 's1',
                                surrogate_number: 'S12345',
                                owner_type: 'user',
                                owner_id: 'u1',
                                owner_name: 'Jane Doe',
                            },
                            {
                                id: 't2',
                                title: 'Call fertility clinic',
                                is_completed: false,
                                due_date: null,
                                surrogate_id: 's2',
                                surrogate_number: 'S12346',
                                owner_type: 'user',
                                owner_id: 'u1',
                                owner_name: 'Jane Doe',
                            },
                        ],
                    },
                    isLoading: false,
                }
            }
            return { data: { items: [], total: 0 }, isLoading: false }
        })
        mockUsePendingImportApprovals.mockReturnValue({
            data: [],
            isLoading: false,
            refetch: vi.fn(),
        })
        mockCompleteTask.mockReset()
        mockUncompleteTask.mockReset()
        mockCreateTask.mockReset()
        mockCreateTaskBatch.mockReset()
        mockBulkCompleteTasks.mockReset()
        mockResolveApproval.mockReset()
        mockApproveImport.mockReset()
        mockRejectImport.mockReset()
        mockSetAIContext.mockReset()
        mockClearAIContext.mockReset()
        mockUseDonors.mockReset()
        mockUseDonors.mockReturnValue({ data: { items: [] }, isLoading: false })
        mockUseAssignees.mockReset().mockReturnValue({ data: [{ id: 'u2', name: 'Riley Case', role: 'case_manager' }] })
        mockShowUndoToast.mockReset()
        Object.values(mockToast).forEach((fn) => fn.mockReset())
    })

    it('renders tasks and toggles completion', async () => {
        render(<TasksPage />)

        expect(screen.getByRole('heading', { level: 1, name: 'Tasks' })).toBeInTheDocument()
        expect(screen.queryByText('Manage your tasks and appointments in one unified view.')).not.toBeInTheDocument()
        expect(screen.getByText('Follow up with surrogate')).toBeInTheDocument()

        const checkbox = screen.getByLabelText('Mark task Follow up with surrogate complete')
        fireEvent.click(checkbox)

        expect(mockCompleteTask).toHaveBeenCalledWith('t1')
        await waitFor(() => expect(mockShowUndoToast).toHaveBeenCalledWith('Task completed', expect.any(Function)))
        mockShowUndoToast.mock.calls[0]![1]()
        expect(mockUncompleteTask).toHaveBeenCalledWith('t1')
    })

    it('shows an error toast and no undo when completing fails', async () => {
        mockCompleteTask.mockRejectedValue(new Error('offline'))
        render(<TasksPage />)

        fireEvent.click(screen.getByLabelText('Mark task Follow up with surrogate complete'))

        await waitFor(() => expect(mockToast.error).toHaveBeenCalledWith("Couldn't update task. Try again."))
        expect(mockShowUndoToast).not.toHaveBeenCalled()
    })

    it('renders the Surrogates-style toolbar and sends list filters to the task query', async () => {
        render(<TasksPage />)

        expect(screen.getByRole('group', { name: 'Task scope' })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'My Tasks' })).toHaveAttribute('aria-pressed', 'true')
        expect(screen.getByRole('group', { name: 'Tasks view' })).toBeInTheDocument()
        expect(screen.getByRole('combobox', { name: 'Filter by status' })).toHaveTextContent('Open')
        expect(screen.getByRole('combobox', { name: 'Filter by due date' })).toHaveTextContent('Any Due Date')
        expect(screen.getByRole('combobox', { name: 'Filter by linked record' })).toHaveTextContent('All Records')
        // Assignee is limited to admins and developers.
        expect(screen.queryByRole('combobox', { name: 'Filter by assignee' })).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole('combobox', { name: 'Filter by linked record' }))
        const donors = await screen.findByRole('option', { name: 'Donors' })
        fireEvent.mouseMove(donors)
        fireEvent.click(donors)
        fireEvent.click(screen.getByRole('combobox', { name: 'Filter by due date' }))
        const today = await screen.findByRole('option', { name: 'Due today' })
        fireEvent.mouseMove(today)
        fireEvent.click(today)
        fireEvent.change(screen.getByRole('textbox', { name: 'Search tasks' }), { target: { value: 'clinic' } })

        await waitFor(() => expect(mockUseTasks).toHaveBeenCalledWith(expect.objectContaining({
            is_completed: false,
            linked_type: 'donor',
            q: 'clinic',
            due_after: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
            due_before: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        })))
        expect(screen.getByRole('combobox', { name: 'Filter by linked record' })).toHaveTextContent('Donors')
        expect(screen.getByRole('button', { name: 'Remove filter: Linked: Donors' })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Remove filter: Due: Due today' })).toBeInTheDocument()
    })

    it('offers only the linked record types the viewer can open', async () => {
        mockPermissions.value = ["edit_tasks", "view_surrogates"]
        render(<TasksPage />)

        fireEvent.click(screen.getByRole('combobox', { name: 'Filter by linked record' }))
        expect(await screen.findByRole('option', { name: 'Surrogates' })).toBeInTheDocument()
        expect(screen.getByRole('option', { name: 'No linked record' })).toBeInTheDocument()
        expect(screen.queryByRole('option', { name: 'Intended Parents' })).not.toBeInTheDocument()
        expect(screen.queryByRole('option', { name: 'Donors' })).not.toBeInTheDocument()
    })

    it('shows the assignee filter to admins and writes it to the URL', async () => {
        mockCurrentUser.role = 'admin'
        render(<TasksPage />)

        expect(mockUseAssignees).toHaveBeenCalledWith({ enabled: true })
        fireEvent.click(screen.getByRole('combobox', { name: 'Filter by assignee' }))
        const riley = await screen.findByRole('option', { name: 'Riley Case' })
        fireEvent.mouseMove(riley)
        fireEvent.click(riley)

        expect(mockNavigation.replace).toHaveBeenCalledWith('/tasks?filter=all&owner_id=u2', { scroll: false })
    })

    it('replaces Show completed with the Status filter', async () => {
        mockUseTasks.mockImplementation((params: { is_completed?: boolean }) => (
            params?.is_completed === true
                ? { data: { items: [{ id: 'done-1', title: 'Closed follow-up', is_completed: true, task_type: 'other', due_date: null, due_time: null, owner_type: 'user', owner_id: 'u1' }], total: 1 }, isLoading: false }
                : { data: { items: [], total: 0 }, isLoading: false }
        ))
        render(<TasksPage />)

        expect(screen.queryByRole('button', { name: /completed tasks/i })).not.toBeInTheDocument()
        expect(screen.getByText('No open tasks')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('combobox', { name: 'Filter by status' }))
        const completed = await screen.findByRole('option', { name: 'Completed' })
        fireEvent.mouseMove(completed)
        fireEvent.click(completed)

        expect(await screen.findByText('Closed follow-up')).toBeInTheDocument()
        expect(screen.getByRole('heading', { name: 'Completed (1)' })).toBeInTheDocument()
        expect(screen.getByLabelText('Mark task Closed follow-up incomplete')).toBeChecked()
    })

    it('offers Clear filters when a search finds no tasks', async () => {
        mockUseTasks.mockReturnValue({ data: { items: [], total: 0 }, isLoading: false })
        render(<TasksPage />)

        fireEvent.change(screen.getByRole('textbox', { name: 'Search tasks' }), { target: { value: 'zzz' } })

        expect(await screen.findByText('No matching tasks')).toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
        expect(screen.getByRole('textbox', { name: 'Search tasks' })).toHaveValue('')
        expect(screen.getByText('No open tasks')).toBeInTheDocument()
    })

    it('shows a retryable load error for the task list without raw server text', () => {
        const refetch = vi.fn()
        mockUseTasks.mockImplementation((params: { is_completed?: boolean; task_type?: string }) => (
            params?.is_completed === false && params?.task_type === undefined
                ? { data: undefined, isLoading: false, isError: true, error: new Error('boom'), refetch, isFetching: false }
                : { data: { items: [], total: 0 }, isLoading: false }
        ))
        render(<TasksPage />)

        expect(screen.getByRole('heading', { level: 2, name: "Couldn't load tasks" })).toBeInTheDocument()
        expect(screen.queryByText(/boom|Please try again/)).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
        expect(refetch).toHaveBeenCalledTimes(1)
    })

    it('hides the approvals section when nothing awaits review', () => {
        mockUseTasks.mockImplementation((params: { task_type?: string }) => (
            params?.task_type === 'workflow_approval'
                ? { data: { items: [], total: 0 }, isLoading: false }
                : { data: { items: [], total: 0 }, isLoading: false }
        ))
        vi.mocked(window.localStorage.getItem).mockReturnValue('calendar')
        render(<TasksPage />)

        expect(screen.queryByText('Pending Approvals')).not.toBeInTheDocument()
        expect(document.getElementById('tasks-approvals')).toBeNull()
        expect(screen.getByText('Calendar View')).toBeInTheDocument()
    })

    it('renders the list immediately for focused task URLs even when calendar is saved', async () => {
        mockNavigation.searchParams = new URLSearchParams('focus=tasks')
        vi.mocked(window.localStorage.getItem).mockReturnValue('calendar')

        const firstRenderHtml = renderToString(<TasksPage />)
        expect(firstRenderHtml).not.toContain('Calendar View')
        expect(firstRenderHtml).toContain('Follow up with surrogate')

        render(<TasksPage />)

        expect(screen.queryByText('Calendar View')).not.toBeInTheDocument()
        expect(screen.getByText('Follow up with surrogate')).toBeInTheDocument()

        await waitFor(() => {
            expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({
                behavior: 'smooth',
                block: 'start',
            })
        })
        expect(window.localStorage.setItem).toHaveBeenCalledWith('tasks-view', 'list')
    })

    it('renders pending approvals section when approvals exist', () => {
        render(<TasksPage />)

        expect(screen.getByText('Pending Approvals')).toBeInTheDocument()
        expect(screen.getByText('Approve: Assign surrogate to John')).toBeInTheDocument()
        expect(screen.getByText('Assign surrogate to John Smith')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /deny/i })).toBeInTheDocument()
        expect(screen.getByText(/remaining/i)).toBeInTheDocument()
    })

    it('shows surrogate links in approval and task items', () => {
        render(<TasksPage />)

        const surrogateLinks = screen.getAllByText('Surrogate #S12345')
        expect(surrogateLinks).toHaveLength(2) // One in approvals, one in tasks
        surrogateLinks.forEach(link => {
            expect(link.closest('a')).toHaveAttribute('href', '/surrogates/s1')
        })
    })

    it('renders pending import approvals for admins', () => {
        mockCurrentUser.role = 'admin'
        mockUsePendingImportApprovals.mockReturnValue({
            data: [
                {
                    id: 'import-1',
                    filename: 'surrogates.csv',
                    status: 'awaiting_approval',
                    total_rows: 120,
                    created_at: new Date().toISOString(),
                    created_by_name: 'Admin User',
                    deduplication_stats: {
                        total: 120,
                        new_records: 115,
                        duplicates: [{ email: 'dup@example.com', existing_id: 's1' }],
                    },
                    column_mapping_snapshot: [],
                },
            ],
            isLoading: false,
            refetch: vi.fn(),
        })

        render(<TasksPage />)

        expect(screen.getByText('Import Approval')).toBeInTheDocument()
        expect(screen.getByText('surrogates.csv')).toBeInTheDocument()
        expect(screen.getByText(/120 rows/i)).toBeInTheDocument()
        expect(screen.getByText(/1 duplicate/i)).toBeInTheDocument()
    })

    it('bulk completes selected tasks from the list view', async () => {
        mockBulkCompleteTasks.mockResolvedValue({ completed: 2, failed: [] })

        render(<TasksPage />)

        expect(screen.queryByRole('toolbar', { name: 'Selected tasks' })).not.toBeInTheDocument()
        fireEvent.click(screen.getByLabelText('Select task Follow up with surrogate'))
        fireEvent.click(screen.getByLabelText('Select task Call fertility clinic'))
        const bulkBar = screen.getByRole('toolbar', { name: 'Selected tasks' })
        expect(bulkBar).toHaveTextContent('2 tasks selected')
        fireEvent.click(within(bulkBar).getByRole('button', { name: 'Complete' }))

        await waitFor(() => {
            expect(mockBulkCompleteTasks).toHaveBeenCalledWith(['t1', 't2'])
        })
    })

    it('clears selected tasks when the task scope changes', () => {
        render(<TasksPage />)

        fireEvent.click(screen.getByLabelText('Select task Follow up with surrogate'))
        expect(screen.getByRole('toolbar', { name: 'Selected tasks' })).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: 'All Tasks' }))

        expect(screen.queryByRole('toolbar', { name: 'Selected tasks' })).not.toBeInTheDocument()
        expect(screen.getByLabelText('Select task Follow up with surrogate')).not.toBeChecked()
        expect(mockNavigation.replace).toHaveBeenCalledWith('/tasks?filter=all', { scroll: false })
    })

    it('renders pending approvals above the calendar view', () => {
        vi.mocked(window.localStorage.getItem).mockReturnValue('calendar')
        render(<TasksPage />)

        const approvals = document.getElementById('tasks-approvals')
        const calendar = screen.getByText('Calendar View')
        expect(approvals).not.toBeNull()
        expect(approvals!.compareDocumentPosition(calendar) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
        expect(within(approvals!).getByText('1')).toBeInTheDocument()
    })

    it("preserves full task description when editing from the global list", async () => {
        mockUseTask.mockReturnValue({ data: {
            id: "t1", title: "Follow up with surrogate", description: "Existing follow-up instructions", task_type: "follow_up", surrogate_id: "s1", surrogate_number: "S12345", intended_parent_id: null, donor_id: null,
            owner_type: "user", owner_id: "u1", created_by_user_id: "u1", due_date: null, due_time: null, is_completed: false,
        }, isError: false })
        mockUpdateTask.mockResolvedValue({})
        render(<TasksPage />)
        fireEvent.click(screen.getByText("Follow up with surrogate"))
        expect(mockUseTask).toHaveBeenCalledWith("t1")
        expect(screen.getByLabelText("Description")).toHaveValue("Existing follow-up instructions")
        fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Updated follow-up" } })
        fireEvent.click(screen.getByRole("button", { name: "Save changes" }))
        await waitFor(() => expect(mockUpdateTask).toHaveBeenCalledWith({ taskId: "t1", data: expect.objectContaining({ title: "Updated follow-up", description: "Existing follow-up instructions" }) }))
    })

    it('updates AI context directly from the task editor lifecycle', () => {
        render(<TasksPage />)

        expect(mockClearAIContext).not.toHaveBeenCalled()

        fireEvent.click(screen.getByText('Follow up with surrogate'))

        expect(mockSetAIContext).toHaveBeenCalledWith({
            entityType: 'task',
            entityId: 't1',
            entityName: 'Follow up with surrogate',
        })

        fireEvent.click(screen.getByRole('button', { name: 'Close' }))

        expect(mockClearAIContext).toHaveBeenCalledTimes(1)
    })

    it('creates recurring tasks with the batch task mutation', async () => {
        mockCreateTaskBatch.mockResolvedValue([])

        render(<TasksPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Add task' }))
        fireEvent.change(screen.getByLabelText('Title *'), {
            target: { value: 'Weekly check-in' },
        })
        fireEvent.change(screen.getByLabelText('Due Date'), {
            target: { value: '2026-05-01' },
        })
        fireEvent.click(screen.getByRole('combobox', { name: 'Repeat' }))
        const weeklyOption = await screen.findByRole('option', { name: 'Weekly' })
        fireEvent.mouseMove(weeklyOption)
        fireEvent.click(weeklyOption)
        fireEvent.change(await screen.findByLabelText('Repeat Until'), {
            target: { value: '2026-05-15' },
        })
        fireEvent.click(screen.getByRole('button', { name: 'Create task' }))

        await waitFor(() => {
            expect(mockCreateTaskBatch).toHaveBeenCalledWith([
                {
                    title: 'Weekly check-in',
                    task_type: 'other',
                    due_date: '2026-05-01',
                },
                {
                    title: 'Weekly check-in',
                    task_type: 'other',
                    due_date: '2026-05-08',
                },
                {
                    title: 'Weekly check-in',
                    task_type: 'other',
                    due_date: '2026-05-15',
                },
            ])
        })
        expect(mockCreateTask).not.toHaveBeenCalled()
        await waitFor(() => expect(mockToast.success).toHaveBeenCalledWith('Tasks created'))
    })

    it('creates a task linked to an egg donor', async () => {
        mockCreateTask.mockResolvedValue({})
        mockUseDonors.mockImplementation((params: { donor_type?: string }) => ({
            data: {
                items: params.donor_type === 'egg'
                    ? [{
                        id: 'donor-1',
                        donor_number: 'D10001',
                        donor_type: 'egg',
                        full_name: 'Maya Thompson',
                    }]
                    : [],
            },
            isLoading: false,
        }))

        render(<TasksPage />)
        fireEvent.click(screen.getByRole('button', { name: 'Add task' }))
        fireEvent.change(screen.getByLabelText('Title *'), {
            target: { value: 'Review donor profile' },
        })
        fireEvent.click(screen.getByRole('button', { name: /^Linked record/ }))
        fireEvent.click(await screen.findByRole('option', { name: 'Maya Thompson · Egg Donor D10001' }))
        expect(screen.getByRole('button', { name: /^Linked record/ })).toHaveTextContent('Egg Donor D10001 — Maya Thompson')
        fireEvent.click(screen.getByRole('button', { name: 'Create task' }))

        await waitFor(() => expect(mockCreateTask).toHaveBeenCalledWith({
            title: 'Review donor profile',
            task_type: 'other',
            donor_id: 'donor-1',
        }))
        await waitFor(() => expect(mockToast.success).toHaveBeenCalledWith('Task created'))
    })
})

describe('TasksListView', () => {
    it('renders tasks and toggles completion', () => {
        const onTaskToggle = vi.fn()
        const onTaskClick = vi.fn()
        const onSelectTask = vi.fn()
        const onSelectAll = vi.fn()
        const onBulkCompleteSelected = vi.fn()
        render(
            <TasksListView
                incompleteTasks={[
                    {
                        id: 't1',
                        title: 'Follow up with surrogate',
                        is_completed: false,
                        due_date: null,
                        surrogate_id: 's1',
                        surrogate_number: 'S12345',
                        owner_type: 'user',
                        owner_id: 'u1',
                        owner_name: 'Jane Doe',
                    } as TaskListItem,
                ]}
                status="open"
                completedTasks={[]}
                completedTotal={0}
                onRetryCompleted={() => {}}
                onClearFilters={null}
                selectedTaskIds={new Set()}
                loadingCompleted={false}
                completedError={false}
                onTaskToggle={onTaskToggle}
                onTaskClick={onTaskClick}
                onSelectTask={onSelectTask}
                onSelectAll={onSelectAll}
                onBulkCompleteSelected={onBulkCompleteSelected}
                bulkCompletePending={false}
            />
        )

        expect(screen.getByText('Follow up with surrogate')).toBeInTheDocument()
        const checkbox = screen.getByLabelText('Mark task Follow up with surrogate complete')
        fireEvent.click(checkbox)
        expect(onTaskToggle).toHaveBeenCalledWith('t1', false)
    })

    it('uses a dedicated open-task control instead of making the whole row a faux button', () => {
        const onTaskToggle = vi.fn()
        const onTaskClick = vi.fn()
        const onSelectTask = vi.fn()
        const onSelectAll = vi.fn()
        const onBulkCompleteSelected = vi.fn()

        render(
            <TasksListView
                incompleteTasks={[
                    {
                        id: 't1',
                        title: 'Follow up with surrogate',
                        is_completed: false,
                        due_date: null,
                        surrogate_id: 's1',
                        surrogate_number: 'S12345',
                        owner_type: 'user',
                        owner_id: 'u1',
                        owner_name: 'Jane Doe',
                    } as TaskListItem,
                ]}
                status="open"
                completedTasks={[]}
                completedTotal={0}
                onRetryCompleted={() => {}}
                onClearFilters={null}
                selectedTaskIds={new Set()}
                loadingCompleted={false}
                completedError={false}
                onTaskToggle={onTaskToggle}
                onTaskClick={onTaskClick}
                onSelectTask={onSelectTask}
                onSelectAll={onSelectAll}
                onBulkCompleteSelected={onBulkCompleteSelected}
                bulkCompletePending={false}
            />
        )

        const openTaskButton = screen.getByRole('button', {
            name: /open task follow up with surrogate/i,
        })
        fireEvent.click(openTaskButton)

        expect(onTaskClick).toHaveBeenCalledWith(
            expect.objectContaining({ id: 't1', title: 'Follow up with surrogate' })
        )

        const surrogateLink = screen.getByRole('link', { name: 'Surrogate #S12345' })
        expect(surrogateLink.closest('button')).toBeNull()
        expect(surrogateLink.closest('[role="button"]')).toBeNull()
    })

    it('links donor tasks with subtype and donor number, and fails closed without metadata', () => {
        render(
            <TasksListView
                incompleteTasks={[
                    {
                        id: 'donor-task',
                        title: 'Review donor profile',
                        is_completed: false,
                        due_date: null,
                        donor_id: 'donor-1',
                        donor_number: 'D10001',
                        donor_type: 'egg',
                        donor_name: 'Maya Thompson',
                        owner_type: 'user',
                        owner_id: 'u1',
                    } as TaskListItem,
                    {
                        id: 'missing-donor-task',
                        title: 'Follow up on removed donor',
                        is_completed: false,
                        due_date: null,
                        donor_id: 'donor-missing',
                        donor_number: null,
                        donor_type: null,
                        donor_name: null,
                        owner_type: 'user',
                        owner_id: 'u1',
                    } as TaskListItem,
                ]}
                status="open"
                completedTasks={[]}
                completedTotal={0}
                onRetryCompleted={() => {}}
                onClearFilters={null}
                selectedTaskIds={new Set()}
                loadingCompleted={false}
                completedError={false}
                onTaskToggle={() => {}}
                onTaskClick={() => {}}
                onSelectTask={() => {}}
                onSelectAll={() => {}}
                onBulkCompleteSelected={() => {}}
                bulkCompletePending={false}
            />
        )

        expect(screen.getByRole('link', { name: 'Egg Donor D10001' })).toHaveAttribute(
            'href',
            '/donors/donor-1',
        )
        expect(screen.getByText('Donor unavailable').closest('a')).toBeNull()
    })

    describe('due, type and selection columns', () => {
        const localDate = (offsetDays: number) => {
            const date = new Date()
            date.setDate(date.getDate() + offsetDays)
            return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
        }
        const task = (overrides: Partial<TaskListItem>) => ({
            id: 'task',
            title: 'Task',
            is_completed: false,
            task_type: 'other',
            due_date: null,
            due_time: null,
            owner_type: 'user',
            owner_id: 'u1',
            ...overrides,
        }) as TaskListItem
        const renderList = (props: Partial<React.ComponentProps<typeof TasksListView>> = {}) => render(
            <TasksListView
                status="open"
                incompleteTasks={[]}
                completedTasks={[]}
                completedTotal={0}
                loadingCompleted={false}
                completedError={false}
                onRetryCompleted={() => {}}
                selectedTaskIds={new Set()}
                onTaskToggle={() => {}}
                onTaskClick={() => {}}
                onSelectTask={() => {}}
                onSelectAll={() => {}}
                onBulkCompleteSelected={() => {}}
                bulkCompletePending={false}
                onClearFilters={null}
                {...props}
            />,
        )

        it('shows the due time, date, overdue state and task type on each row', () => {
            renderList({
                incompleteTasks: [
                    task({ id: 'late', title: 'Late review', task_type: 'review', due_date: localDate(-3), due_time: '10:00:00' }),
                    task({ id: 'today', title: 'Call surrogate', task_type: 'contact', due_date: localDate(0), due_time: '14:30:00' }),
                    task({ id: 'undated', title: 'Someday', task_type: 'follow_up' }),
                ],
            })

            const rows = screen.getAllByTestId('task-row')
            const lateRow = rows.find((row) => row.textContent?.includes('Late review'))!
            const lateDue = within(lateRow).getByText(/10:00 AM/)
            expect(lateDue).toHaveTextContent(/^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}(, \d{4})? · 10:00 AM$/)
            expect(lateDue).toHaveClass('text-destructive')
            expect(within(lateRow).getByText('Review')).toBeInTheDocument()

            const todayRow = rows.find((row) => row.textContent?.includes('Call surrogate'))!
            expect(within(todayRow).getByText('2:30 PM')).not.toHaveClass('text-destructive')
            expect(within(todayRow).getByText('Contact')).toBeInTheDocument()

            const undatedRow = rows.find((row) => row.textContent?.includes('Someday'))!
            expect(within(undatedRow).getByText('No due date')).toHaveClass('sr-only')
            expect(within(undatedRow).getByText('Follow Up')).toBeInTheDocument()
        })

        it('orders same-day tasks by due time with untimed tasks last', () => {
            renderList({
                incompleteTasks: [
                    task({ id: 'untimed', title: 'Untimed', due_date: localDate(0) }),
                    task({ id: 'afternoon', title: 'Afternoon', due_date: localDate(0), due_time: '15:00:00' }),
                    task({ id: 'morning', title: 'Morning', due_date: localDate(0), due_time: '09:00:00' }),
                ],
            })

            const titles = screen.getAllByTestId('task-row').map((row) =>
                ['Morning', 'Afternoon', 'Untimed'].find((title) => row.textContent?.includes(title)),
            )
            expect(titles).toEqual(['Morning', 'Afternoon', 'Untimed'])
        })

        it('uses a round completion control and reveals select boxes on hover until a row is selected', () => {
            const { rerender } = renderList({ incompleteTasks: [task({ id: 't1', title: 'First' })] })

            expect(screen.getByLabelText('Mark task First complete')).toHaveClass('rounded-full')
            expect(screen.getByLabelText('Select task First')).toHaveClass('opacity-0')
            expect(screen.queryByRole('toolbar', { name: 'Selected tasks' })).not.toBeInTheDocument()

            rerender(
                <TasksListView
                    status="open"
                    incompleteTasks={[task({ id: 't1', title: 'First' })]}
                    completedTasks={[]}
                    completedTotal={0}
                    loadingCompleted={false}
                    completedError={false}
                    onRetryCompleted={() => {}}
                    selectedTaskIds={new Set(['t1'])}
                    onTaskToggle={() => {}}
                    onTaskClick={() => {}}
                    onSelectTask={() => {}}
                    onSelectAll={() => {}}
                    onBulkCompleteSelected={() => {}}
                    bulkCompletePending={false}
                    onClearFilters={null}
                />,
            )
            expect(screen.getByLabelText('Select task First')).not.toHaveClass('opacity-0')
            expect(screen.getByRole('toolbar', { name: 'Selected tasks' })).toHaveTextContent('1 task selected')
        })

        it('keeps completed rows on the same grid with an empty select column', () => {
            renderList({
                status: 'all',
                incompleteTasks: [task({ id: 'open', title: 'Open task' })],
                completedTasks: [task({ id: 'done', title: 'Done task', is_completed: true, due_date: '2026-09-24' })],
                completedTotal: 1,
            })

            const [openRow, doneRow] = screen.getAllByTestId('task-row')
            expect(openRow!.className).toBe(doneRow!.className.replace(' opacity-60', ''))
            expect(within(doneRow!).queryByLabelText(/Select task/)).not.toBeInTheDocument()
            expect(within(doneRow!).getByLabelText('Mark task Done task incomplete')).toBeChecked()
            expect(screen.getByRole('heading', { name: 'Completed (1)' })).toBeInTheDocument()
        })

        it('shows a neutral empty state, and Clear filters when filters are active', () => {
            const onClearFilters = vi.fn()
            const { unmount } = renderList()
            expect(screen.getByText('No open tasks')).toBeInTheDocument()
            expect(screen.queryByText(/Nice work/)).not.toBeInTheDocument()
            unmount()

            renderList({ onClearFilters })
            expect(screen.getByText('No matching tasks')).toBeInTheDocument()
            fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
            expect(onClearFilters).toHaveBeenCalledOnce()
        })
    })
})

describe('TasksCalendarView', () => {
    it('renders calendar view', () => {
        render(<TasksCalendarView taskFilter={{ my_tasks: true }} onTaskClick={() => {}} />)
        expect(screen.getByText('Calendar View')).toBeInTheDocument()
    })
})

describe('TasksApprovalsSection', () => {
    it('renders approvals, status requests, and import approvals', () => {
        const pendingApprovals: TaskListItem[] = [
            {
                id: 'approval-1',
                title: 'Approve: Assign surrogate to John',
                task_type: 'workflow_approval',
                status: 'pending',
                is_completed: false,
                due_date: null,
                due_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
                surrogate_id: 's1',
                surrogate_number: 'S12345',
                owner_type: 'user',
                owner_id: 'u1',
                owner_name: 'Test User',
                workflow_action_preview: 'Assign surrogate to John Smith',
            } as TaskListItem,
        ]
        const pendingStatusRequests: StatusChangeRequestDetail[] = [
            {
                request: {
                    id: 'req-1',
                    organization_id: 'org-1',
                    entity_type: 'surrogate',
                    entity_id: 's1',
                    target_stage_id: 'stage-2',
                    target_status: null,
                    effective_at: new Date().toISOString(),
                    reason: 'Needs regression',
                    requested_by_user_id: 'u2',
                    requested_at: new Date().toISOString(),
                    status: 'pending',
                    approved_by_user_id: null,
                    approved_at: null,
                    rejected_by_user_id: null,
                    rejected_at: null,
                    cancelled_by_user_id: null,
                    cancelled_at: null,
                },
                entity_name: 'Jane Applicant',
                entity_number: 'S12345',
                requester_name: 'Admin User',
                target_stage_label: 'Qualified',
                current_stage_label: 'Approved',
            },
        ]
        const pendingImportApprovals: ImportApprovalItem[] = [
            {
                id: 'import-1',
                filename: 'surrogates.csv',
                status: 'awaiting_approval',
                total_rows: 120,
                created_at: new Date().toISOString(),
                created_by_name: 'Admin User',
                deduplication_stats: {
                    total: 120,
                    new_records: 115,
                    duplicates: [{ email: 'dup@example.com', existing_id: 's1' }],
                },
                column_mapping_snapshot: [],
            },
        ]

        render(
            <TasksApprovalsSection
                pendingApprovals={pendingApprovals}
                pendingStatusRequests={pendingStatusRequests}
                pendingImportApprovals={pendingImportApprovals}
                loadingApprovals={false}
                loadingStatusRequests={false}
                loadingImportApprovals={false}
                onResolvedStatusRequests={() => {}}
                onResolvedImportApprovals={() => {}}
                currentUserId="u1"
            />
        )

        expect(screen.getByText('Pending Approvals')).toBeInTheDocument()
        expect(screen.getByText('Stage Regression Request')).toBeInTheDocument()
        expect(screen.getByText('Import Approval')).toBeInTheDocument()
        expect(screen.getByText('Approve: Assign surrogate to John')).toBeInTheDocument()
    })

    it('server-renders approval timestamps as deterministic UTC fallback labels', () => {
        const html = renderToString(
            <TasksApprovalsSection
                pendingApprovals={[
                    {
                        id: 'approval-1',
                        title: 'Approve: Assign surrogate to John',
                        task_type: 'workflow_approval',
                        status: 'pending',
                        is_completed: false,
                        due_date: null,
                        due_at: '2026-06-04T00:30:00.000Z',
                        surrogate_id: 's1',
                        surrogate_number: 'S12345',
                        owner_type: 'user',
                        owner_id: 'u1',
                        owner_name: 'Test User',
                        workflow_action_preview: 'Assign surrogate to John Smith',
                    } as TaskListItem,
                ]}
                pendingStatusRequests={[]}
                pendingImportApprovals={[
                    {
                        id: 'import-1',
                        filename: 'surrogates.csv',
                        status: 'awaiting_approval',
                        total_rows: 120,
                        created_at: '2026-06-03T00:30:00.000Z',
                        created_by_name: 'Admin User',
                        deduplication_stats: {
                            total: 120,
                            new_records: 115,
                            duplicates: [],
                        },
                        column_mapping_snapshot: [],
                    },
                ]}
                loadingApprovals={false}
                loadingStatusRequests={false}
                loadingImportApprovals={false}
                onResolvedStatusRequests={() => {}}
                onResolvedImportApprovals={() => {}}
                currentUserId="u1"
            />,
        )

        expect(html).toContain('Jun 3, 2026')
        expect(html).toContain('Jun 4, 2026')
        expect(html).not.toContain('remaining')
    })

    it('routes donor workflow approvals to the donor detail', () => {
        render(
            <TasksApprovalsSection
                pendingApprovals={[
                    {
                        id: 'approval-donor',
                        title: 'Approve donor stage change',
                        task_type: 'workflow_approval',
                        status: 'pending',
                        is_completed: false,
                        due_date: null,
                        donor_id: 'donor-1',
                        donor_number: 'D10001',
                        donor_type: 'sperm',
                        donor_name: 'Ethan Reed',
                        owner_type: 'user',
                        owner_id: 'u1',
                    } as TaskListItem,
                ]}
                pendingStatusRequests={[]}
                pendingImportApprovals={[]}
                loadingApprovals={false}
                loadingStatusRequests={false}
                loadingImportApprovals={false}
                onResolvedStatusRequests={() => {}}
                onResolvedImportApprovals={() => {}}
                currentUserId="u1"
            />,
        )

        expect(screen.getByRole('link', { name: 'Sperm Donor D10001' })).toHaveAttribute(
            'href',
            '/donors/donor-1',
        )
    })
})
