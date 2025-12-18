import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import TasksPage from '../app/(app)/tasks/page'

vi.mock('next/link', () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

const mockUseTasks = vi.fn()
const mockCompleteTask = vi.fn()
const mockUncompleteTask = vi.fn()

vi.mock('@/lib/hooks/use-tasks', () => ({
    useTasks: (params: any) => mockUseTasks(params),
    useCompleteTask: () => ({ mutateAsync: mockCompleteTask }),
    useUncompleteTask: () => ({ mutateAsync: mockUncompleteTask }),
}))

describe('TasksPage', () => {
    beforeEach(() => {
        mockUseTasks.mockImplementation((params: { is_completed?: boolean }) => {
            if (params?.is_completed) {
                return { data: { items: [] }, isLoading: false }
            }
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
                            assigned_to_name: 'Jane Doe',
                        },
                    ],
                },
                isLoading: false,
            }
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

