import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ApprovalTaskActions } from '../components/tasks/ApprovalTaskActions'

const mockResolveApproval = vi.fn()

vi.mock('@/lib/hooks/use-tasks', () => ({
    useResolveWorkflowApproval: () => ({
        mutateAsync: mockResolveApproval,
        isPending: false,
    }),
}))

describe('ApprovalTaskActions', () => {
    beforeEach(() => {
        mockResolveApproval.mockReset()
        mockResolveApproval.mockResolvedValue({})
    })

    it('renders approve and deny buttons for owner', () => {
        render(<ApprovalTaskActions taskId="task-1" isOwner={true} />)

        expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /deny/i })).toBeInTheDocument()
    })

    it('shows message for non-owners instead of buttons', () => {
        render(<ApprovalTaskActions taskId="task-1" isOwner={false} />)

        expect(screen.queryByRole('button', { name: /approve/i })).not.toBeInTheDocument()
        expect(screen.queryByRole('button', { name: /deny/i })).not.toBeInTheDocument()
        expect(screen.getByText(/only the surrogate owner/i)).toBeInTheDocument()
    })

    it('calls resolve with approve decision when approve clicked', async () => {
        render(<ApprovalTaskActions taskId="task-1" isOwner={true} />)

        fireEvent.click(screen.getByRole('button', { name: /approve/i }))

        await waitFor(() => {
            expect(mockResolveApproval).toHaveBeenCalledWith({
                taskId: 'task-1',
                decision: 'approve',
            })
        })
    })

    it('opens deny dialog when deny clicked', async () => {
        render(<ApprovalTaskActions taskId="task-1" isOwner={true} />)

        fireEvent.click(screen.getByRole('button', { name: /deny/i }))

        await waitFor(() => {
            expect(screen.getByText('Deny Workflow Action')).toBeInTheDocument()
        })
    })

    it('calls resolve with deny decision and reason when denied', async () => {
        render(<ApprovalTaskActions taskId="task-1" isOwner={true} />)

        // Open deny dialog
        fireEvent.click(screen.getByRole('button', { name: /deny/i }))

        // Enter reason
        const textarea = screen.getByPlaceholderText(/why are you denying/i)
        fireEvent.change(textarea, { target: { value: 'Not appropriate' } })

        // Confirm deny
        const denyButtons = screen.getAllByRole('button', { name: /deny/i })
        fireEvent.click(denyButtons[denyButtons.length - 1]) // Click dialog's deny button

        await waitFor(() => {
            expect(mockResolveApproval).toHaveBeenCalledWith({
                taskId: 'task-1',
                decision: 'deny',
                reason: 'Not appropriate',
            })
        })
    })

    it('disables buttons when disabled prop is true', () => {
        render(<ApprovalTaskActions taskId="task-1" isOwner={true} disabled={true} />)

        expect(screen.getByRole('button', { name: /approve/i })).toBeDisabled()
        expect(screen.getByRole('button', { name: /deny/i })).toBeDisabled()
    })
})
