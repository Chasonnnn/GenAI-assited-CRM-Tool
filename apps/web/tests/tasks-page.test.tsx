import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import TasksPage from '../app/(app)/tasks/page'

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

vi.mock('@/lib/hooks/use-tasks', () => ({
    useTasks: (params: unknown) => mockUseTasks(params),
    useCompleteTask: () => ({ mutateAsync: mockCompleteTask }),
    useUncompleteTask: () => ({ mutateAsync: mockUncompleteTask }),
    useUpdateTask: () => ({ mutateAsync: mockUpdateTask }),
    useCreateTask: () => ({ mutateAsync: mockCreateTask, isPending: false }),
    useDeleteTask: () => ({ mutateAsync: mockDeleteTask, isPending: false }),
    useResolveWorkflowApproval: () => ({ mutateAsync: mockResolveApproval, isPending: false }),
}))

// Mock auth context
const mockCurrentUser = { user_id: 'u1', display_name: 'Test User' }
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
vi.mock('@/components/appointments', () => ({
    UnifiedCalendar: () => <div>Calendar View</div>,
}))

describe('TasksPage', () => {
    beforeEach(() => {
        mockUseTasks.mockImplementation((params: { is_completed?: boolean; task_type?: string; exclude_approvals?: boolean }) => {
            // Return workflow approvals for approval query
            if (params?.task_type === 'workflow_approval' && params?.exclude_approvals === false) {
                return {
                    data: {
                        items: [
                            {
                                id: 'approval-1',
                                title: 'Approve: Assign case to John',
                                task_type: 'workflow_approval',
                                status: 'pending',
                                is_completed: false,
                                due_date: null,
                                due_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(), // 24h from now
                                case_id: 'c1',
                                case_number: '12345',
                                owner_type: 'user',
                                owner_id: 'u1', // Same as mockCurrentUser
                                owner_name: 'Test User',
                                workflow_action_preview: 'Assign case to John Smith',
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
                                title: 'Follow up with case',
                                is_completed: false,
                                due_date: null,
                                case_id: 'c1',
                                case_number: '12345',
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
        mockCompleteTask.mockReset()
        mockUncompleteTask.mockReset()
        mockResolveApproval.mockReset()
    })

    it('renders tasks and toggles completion', () => {
        render(<TasksPage />)

        expect(screen.getByText('Tasks')).toBeInTheDocument()
        expect(screen.getByText('Follow up with case')).toBeInTheDocument()

        const checkbox = screen.getAllByRole('checkbox')[0]
        fireEvent.click(checkbox)

        expect(mockCompleteTask).toHaveBeenCalledWith('t1')
    })

    it('renders pending approvals section when approvals exist', () => {
        render(<TasksPage />)

        expect(screen.getByText('Pending Approvals')).toBeInTheDocument()
        expect(screen.getByText('Approve: Assign case to John')).toBeInTheDocument()
        expect(screen.getByText('Assign case to John Smith')).toBeInTheDocument()
    })

    it('shows approve and deny buttons for case owner', () => {
        render(<TasksPage />)

        expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /deny/i })).toBeInTheDocument()
    })

    it('shows time remaining for approval', () => {
        render(<TasksPage />)

        // Should show hours remaining (24h from now = "24h remaining" or "1d 0h remaining")
        expect(screen.getByText(/remaining/i)).toBeInTheDocument()
    })

    it('shows case links in approval and task items', () => {
        render(<TasksPage />)

        const caseLinks = screen.getAllByText('Case #12345')
        expect(caseLinks).toHaveLength(2) // One in approvals, one in tasks
        caseLinks.forEach(link => {
            expect(link.closest('a')).toHaveAttribute('href', '/cases/c1')
        })
    })
})
