import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import QueuesSettingsPage from '../app/(app)/settings/queues/page'

const mockPush = vi.fn()

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: mockPush }),
}))

const mockUseAuth = vi.fn()

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => mockUseAuth(),
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
        mockPush.mockReset()
        mockUseAuth.mockReset()
        mockUseQueues.mockReset()
        mockCreateQueue.mockReset()
        mockUpdateQueue.mockReset()
        mockDeleteQueue.mockReset()
    })

    it('redirects non-admin users', async () => {
        mockUseAuth.mockReturnValue({ user: { role: 'intake_specialist' } })
        mockUseQueues.mockReturnValue({ data: [], isLoading: false, error: null })

        render(<QueuesSettingsPage />)

        await waitFor(() => {
            expect(mockPush).toHaveBeenCalledWith('/settings')
        })
    })

    it('renders queues for admin users', () => {
        mockUseAuth.mockReturnValue({ user: { role: 'admin' } })
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

        expect(screen.getByText('Queue Management')).toBeInTheDocument()
        expect(screen.getByText('Queue A')).toBeInTheDocument()
    })
})
