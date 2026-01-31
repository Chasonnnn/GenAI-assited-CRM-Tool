import type { PropsWithChildren } from "react"
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import AIAssistantPage from '../app/(app)/ai-assistant/page'

// Avoid Sidebar context requirements in tests
vi.mock('@/components/ui/sidebar', () => ({
    SidebarTrigger: () => <button type="button">Sidebar</button>,
}))

// Use a simple native <select> for deterministic tests
vi.mock('@/components/ui/select', () => ({
    Select: ({ value, onValueChange, children }: PropsWithChildren<{ value?: string; onValueChange: (value: string) => void }>) => (
        <select
            data-testid="select"
            value={value ?? ''}
            onChange={(e) => onValueChange(e.target.value)}
        >
            <option value="">Select</option>
            {children}
        </select>
    ),
    SelectTrigger: () => null,
    SelectValue: () => null,
    SelectContent: ({ children }: PropsWithChildren) => <>{children}</>,
    SelectItem: ({ value, children }: PropsWithChildren<{ value: string }>) => <option value={value}>{children}</option>,
}))

const mockUseQuery = vi.fn()
vi.mock('@tanstack/react-query', () => ({
    useQuery: (opts: unknown) => mockUseQuery(opts),
}))

const mockSendMessage = vi.fn()
const mockApproveAction = vi.fn()
const mockRejectAction = vi.fn()
const mockUseConversation = vi.fn()

vi.mock('@/lib/hooks/use-ai', () => ({
    useAISettings: () => ({ data: { is_enabled: true } }),
    useSendMessage: () => ({ mutateAsync: mockSendMessage, isPending: false }),
    useApproveAction: () => ({ mutateAsync: mockApproveAction, isPending: false }),
    useRejectAction: () => ({ mutateAsync: mockRejectAction, isPending: false }),
    useConversation: () => mockUseConversation(),
}))

describe('AIAssistantPage', () => {
    beforeEach(() => {
        mockUseQuery.mockReturnValue({
            data: [
                { id: 's1', surrogate_number: 'S12345', full_name: 'Jane Applicant' },
            ],
            isLoading: false,
        })
        mockUseConversation.mockReturnValue({
            data: { messages: [] },
            isLoading: false,
            isFetching: false,
        })

        mockSendMessage.mockResolvedValue({
            content: 'Here is a quick summary.',
            proposed_actions: [
                {
                    approval_id: 'a1',
                    action_type: 'add_note',
                    action_data: { content: 'Add note' },
                    status: 'pending',
                },
            ],
            tokens_used: { prompt: 1, completion: 1, total: 2 },
        })

        mockApproveAction.mockResolvedValue({ success: true })
        mockSendMessage.mockClear()
        mockApproveAction.mockClear()
        mockRejectAction.mockClear()
    })

    it('sends a message and can approve a proposed action', async () => {
        render(<AIAssistantPage />)

        fireEvent.change(screen.getByTestId('select'), { target: { value: 's1' } })

        const input = screen.getByPlaceholderText('Type your message...')
        fireEvent.change(input, { target: { value: 'Summarize this surrogate' } })
        fireEvent.keyDown(input, { key: 'Enter', shiftKey: false })

        expect(mockSendMessage).toHaveBeenCalledWith({
            entity_type: 'surrogate',
            entity_id: 's1',
            message: 'Summarize this surrogate',
        })

        expect(await screen.findByText('Here is a quick summary.')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /approve/i }))
        expect(mockApproveAction).toHaveBeenCalledWith('a1')

        expect(await screen.findByText('approved')).toBeInTheDocument()
    })
})
