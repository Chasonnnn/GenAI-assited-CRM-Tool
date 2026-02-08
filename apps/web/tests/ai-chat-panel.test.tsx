import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AIChatPanel } from '../components/ai/AIChatPanel'

// Mocks
const mockStreamMessage = vi.fn()
const mockApproveAction = vi.fn()
const mockRejectAction = vi.fn()
const mockUseConversation = vi.fn()

vi.mock('@/lib/hooks/use-ai', () => ({
    useConversation: () => mockUseConversation(),
    useStreamChatMessage: () => mockStreamMessage,
    useApproveAction: () => ({ mutate: mockApproveAction, isPending: false }),
    useRejectAction: () => ({ mutate: mockRejectAction, isPending: false }),
}))

// Mock ScheduleParserDialog to avoid deep rendering issues
vi.mock('@/components/ai/ScheduleParserDialog', () => ({
    ScheduleParserDialog: () => <div data-testid="schedule-parser-dialog">Dialog</div>
}))

describe('AIChatPanel', () => {
    beforeEach(() => {
        vi.clearAllMocks()

        // Default mock implementation
        mockUseConversation.mockReturnValue({
            data: { messages: [] },
            isLoading: false
        })
    })

    it('renders with accessible close button when onClose is provided', () => {
        const onClose = vi.fn()
        render(<AIChatPanel onClose={onClose} />)

        const closeButton = screen.getByRole('button', { name: /close ai assistant/i })
        expect(closeButton).toBeInTheDocument()

        fireEvent.click(closeButton)
        expect(onClose).toHaveBeenCalled()
    })

    it('does not render close button when onClose is not provided', () => {
        render(<AIChatPanel />)
        const closeButton = screen.queryByRole('button', { name: /close ai assistant/i })
        expect(closeButton).not.toBeInTheDocument()
    })

    it('renders accessible action buttons when actions are proposed', () => {
        mockUseConversation.mockReturnValue({
            data: {
                messages: [
                    {
                        id: 'msg1',
                        role: 'assistant',
                        content: 'Here is a proposal',
                        status: 'done',
                        proposed_actions: [
                            {
                                approval_id: 'action1',
                                action_type: 'add_note',
                                action_data: { content: 'test note' }
                            }
                        ]
                    }
                ]
            },
            isLoading: false
        })

        render(<AIChatPanel />)

        const approveButton = screen.getByRole('button', { name: /approve action/i })
        const rejectButton = screen.getByRole('button', { name: /reject action/i })

        expect(approveButton).toBeInTheDocument()
        expect(rejectButton).toBeInTheDocument()

        fireEvent.click(approveButton)
        expect(mockApproveAction).toHaveBeenCalledWith('action1')

        fireEvent.click(rejectButton)
        expect(mockRejectAction).toHaveBeenCalledWith('action1')
    })
})
