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

vi.mock('@/lib/hooks/use-tasks', () => ({
    useTasks: (params: unknown) => mockUseTasks(params),
    useCompleteTask: () => ({ mutateAsync: mockCompleteTask }),
    useUncompleteTask: () => ({ mutateAsync: mockUncompleteTask }),
    useUpdateTask: () => ({ mutateAsync: mockUpdateTask }),
}))

// Mock the UnifiedCalendar component to render nothing in tests
vi.mock('@/components/appointments', () => ({
    UnifiedCalendar: () => <div>Calendar View</div>,
}))

describe('TasksPage', () => {
    beforeEach(() => {
        mockUseTasks.mockImplementation((params: { is_completed?: boolean }) => {
            if (params?.is_completed === false) {
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
            return { data: { items: [] }, isLoading: false }
        })
        mockCompleteTask.mockReset()
        mockUncompleteTask.mockReset()
    })

    it('renders tasks and toggles completion', () => {
        render(<TasksPage />)

        expect(screen.getByText('Tasks')).toBeInTheDocument()
        expect(screen.getByText('Follow up with case')).toBeInTheDocument()

        const checkbox = screen.getAllByRole('checkbox')[0]
        fireEvent.click(checkbox)

        expect(mockCompleteTask).toHaveBeenCalledWith('t1')
    })
})
