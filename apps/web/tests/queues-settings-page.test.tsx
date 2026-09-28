import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ApiError } from '@/lib/api'
import QueuesSettingsPage from '../app/(app)/settings/queues/page'

const mockCan = vi.fn()

vi.mock('@/lib/hooks/use-permission-check', () => ({
    usePermissionCheck: () => ({
        isLoading: false,
        isError: false,
        retry: vi.fn(),
        isRetrying: false,
        can: (permission: string) => mockCan(permission),
    }),
}))

vi.mock('@/components/app-link', () => ({
    default: ({ children, href, ...props }: React.ComponentProps<'a'>) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

const mockUseQueues = vi.fn()
const mockCreateQueue = vi.fn()
const mockUpdateQueue = vi.fn()
const mockDeleteQueue = vi.fn()

vi.mock('@/lib/hooks/use-queues', () => ({
    useQueues: (includeInactive?: boolean) => mockUseQueues(includeInactive),
    useCreateQueue: () => ({ mutateAsync: mockCreateQueue, isPending: false }),
    useUpdateQueue: () => ({ mutateAsync: mockUpdateQueue, isPending: false }),
    useDeleteQueue: () => ({ mutateAsync: mockDeleteQueue, isPending: false }),
    useQueueMembers: () => ({ data: [], isLoading: false }),
    useAddQueueMember: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useRemoveQueueMember: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/lib/hooks/use-permissions', () => ({
    useMembers: () => ({ data: [] }),
}))

describe('QueuesSettingsPage', () => {
    beforeEach(() => {
        mockCan.mockReset()
        mockCan.mockImplementation((permission: string) => permission === 'manage_queues')
        mockUseQueues.mockReset()
        mockCreateQueue.mockReset()
        mockUpdateQueue.mockReset()
        mockDeleteQueue.mockReset()
    })

    it('shows the denied state without loading queues when manage_queues is missing', () => {
        mockCan.mockReturnValue(false)
        mockUseQueues.mockReturnValue({ data: [], isLoading: false, error: null })

        render(<QueuesSettingsPage />)

        expect(screen.getByRole('heading', { level: 1, name: 'Queues' })).toBeInTheDocument()
        expect(screen.getByText('Permission required')).toBeInTheDocument()
        expect(screen.getByRole('link', { name: 'Back to Settings' })).toHaveAttribute('href', '/settings')
        expect(screen.queryByRole('button', { name: /create queue/i })).not.toBeInTheDocument()
        expect(mockUseQueues).not.toHaveBeenCalled()
    })

    it('shows a sanitized load error with retry instead of the raw message', () => {
        const refetch = vi.fn()
        mockUseQueues.mockReturnValue({
            data: undefined,
            isLoading: false,
            error: new ApiError(500, 'Internal Server Error', 'boom'),
            refetch,
            isFetching: false,
        })

        render(<QueuesSettingsPage />)

        expect(screen.getByText("Couldn't load queues")).toBeInTheDocument()
        expect(screen.queryByText(/boom/)).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
        expect(refetch).toHaveBeenCalledTimes(1)
    })

    it('renders queues for admin users', () => {
        mockUseQueues.mockReturnValue({
            data: [
                {
                    id: 'q1',
                    organization_id: 'org1',
                    name: 'Queue A',
                    description: null,
                    is_active: true,
                },
            ],
            isLoading: false,
            error: null,
        })

        render(<QueuesSettingsPage />)

        expect(screen.getByRole('heading', { level: 1, name: 'Queues' })).toBeInTheDocument()
        expect(screen.getByText('Queue A')).toBeInTheDocument()
    })

    it('saves edits for the selected queue', async () => {
        mockUseQueues.mockReturnValue({
            data: [
                {
                    id: 'q1',
                    organization_id: 'org1',
                    name: 'Queue A',
                    description: 'Original description',
                    is_active: true,
                },
            ],
            isLoading: false,
            error: null,
        })

        render(<QueuesSettingsPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Queue actions for Queue A' }))
        fireEvent.click(await screen.findByRole('menuitem', { name: 'Edit' }))
        fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Queue Alpha' } })
        fireEvent.change(screen.getByLabelText(/Description/i), {
            target: { value: 'Updated description' },
        })
        fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))

        await waitFor(() => {
            expect(mockUpdateQueue).toHaveBeenCalledWith({
                queueId: 'q1',
                data: {
                    name: 'Queue Alpha',
                    description: 'Updated description',
                },
            })
        })
    })
})
