import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
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

    it('saves edits for the selected queue', async () => {
        mockUseAuth.mockReturnValue({ user: { role: 'admin' } })
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
