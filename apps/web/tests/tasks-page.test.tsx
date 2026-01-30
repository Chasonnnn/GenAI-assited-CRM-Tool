import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import TasksPage from '../app/(app)/tasks/page'
import { TasksListView } from '@/components/tasks/TasksListView'
import { TasksCalendarView } from '@/components/tasks/TasksCalendarView'
import { TasksApprovalsSection } from '@/components/tasks/TasksApprovalsSection'
import type { TaskListItem } from '@/lib/types/task'
import type { StatusChangeRequestDetail } from '@/lib/api/status-change-requests'
import type { ImportApprovalItem } from '@/lib/api/import'

vi.mock('next/link', () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
    useSearchParams: () => ({
        get: () => null,
        toString: () => '',
    }),
    useRouter: () => ({
        push: vi.fn(),
        replace: vi.fn(),
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

const mockUseTasks = vi.fn()
const mockCompleteTask = vi.fn()
const mockUncompleteTask = vi.fn()
const mockUpdateTask = vi.fn()
const mockCreateTask = vi.fn()
const mockDeleteTask = vi.fn()
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

vi.mock('@/lib/hooks/use-tasks', () => ({
    useTasks: (params: unknown) => mockUseTasks(params),
    useCompleteTask: () => ({ mutateAsync: mockCompleteTask }),
    useUncompleteTask: () => ({ mutateAsync: mockUncompleteTask }),
    useUpdateTask: () => ({ mutateAsync: mockUpdateTask }),
    useCreateTask: () => ({ mutateAsync: mockCreateTask, isPending: false }),
    useDeleteTask: () => ({ mutateAsync: mockDeleteTask, isPending: false }),
    useResolveWorkflowApproval: () => ({ mutateAsync: mockResolveApproval, isPending: false }),
}))

vi.mock('@/lib/hooks/use-import', () => ({
    usePendingImportApprovals: () => mockUsePendingImportApprovals(),
    useApproveImport: () => ({ mutateAsync: mockApproveImport, isPending: false }),
    useRejectImport: () => ({ mutateAsync: mockRejectImport, isPending: false }),
    useRunImportInline: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/lib/hooks/use-status-change-requests', () => ({
    useStatusChangeRequests: (...args: unknown[]) => mockUseStatusChangeRequests(...args),
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
        setContext: vi.fn(),
        clearContext: vi.fn(),
    }),
}))

// Mock the UnifiedCalendar component to render nothing in tests
vi.mock('@/components/appointments/UnifiedCalendar', () => ({
    UnifiedCalendar: () => <div>Calendar View</div>,
}))

describe('TasksPage', () => {
    beforeEach(() => {
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
        mockResolveApproval.mockReset()
        mockApproveImport.mockReset()
        mockRejectImport.mockReset()
    })

    it('renders tasks and toggles completion', () => {
        render(<TasksPage />)

        expect(screen.getByText('Tasks')).toBeInTheDocument()
        expect(screen.getByText('Follow up with surrogate')).toBeInTheDocument()

        const checkbox = screen.getAllByRole('checkbox')[0]
        fireEvent.click(checkbox)

        expect(mockCompleteTask).toHaveBeenCalledWith('t1')
    })

    it('renders pending approvals section when approvals exist', () => {
        render(<TasksPage />)

        expect(screen.getByText('Pending Approvals')).toBeInTheDocument()
        expect(screen.getByText('Approve: Assign surrogate to John')).toBeInTheDocument()
        expect(screen.getByText('Assign surrogate to John Smith')).toBeInTheDocument()
    })

    it('shows approve and deny buttons for surrogate owner', () => {
        render(<TasksPage />)

        expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /deny/i })).toBeInTheDocument()
    })

    it('shows time remaining for approval', () => {
        render(<TasksPage />)

        // Should show hours remaining (24h from now = "24h remaining" or "1d 0h remaining")
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
})

describe('TasksListView', () => {
    it('renders tasks and toggles completion', () => {
        const onTaskToggle = vi.fn()
        const onTaskClick = vi.fn()
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
                completedTasks={{ items: [], total: 0 }}
                showCompleted={false}
                loadingCompleted={false}
                completedError={false}
                onToggleShowCompleted={() => {}}
                onTaskToggle={onTaskToggle}
                onTaskClick={onTaskClick}
            />
        )

        expect(screen.getByText('Follow up with surrogate')).toBeInTheDocument()
        const checkbox = screen.getAllByRole('checkbox')[0]
        fireEvent.click(checkbox)
        expect(onTaskToggle).toHaveBeenCalledWith('t1', false)
    })
})

describe('TasksCalendarView', () => {
    it('renders calendar view', () => {
        render(<TasksCalendarView filter="my_tasks" onTaskClick={() => {}} />)
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
})
