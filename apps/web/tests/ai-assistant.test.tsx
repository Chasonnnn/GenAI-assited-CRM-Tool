import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import AIAssistantPage from '../app/(app)/ai-assistant/page'

// Avoid Sidebar context requirements in tests
vi.mock('@/components/ui/sidebar', () => ({
    SidebarTrigger: () => <button type="button">Sidebar</button>,
}))

const mockStreamMessage = vi.fn()
const mockApproveAction = vi.fn()
const mockRejectAction = vi.fn()
const mockUseAuth = vi.fn()

let mockUser: { user_id: string } | null = { user_id: 'u1' }

vi.mock('@/lib/hooks/use-ai', () => ({
    useAISettings: () => ({ data: { is_enabled: true } }),
    useStreamChatMessage: () => mockStreamMessage,
    useApproveAction: () => ({ mutateAsync: mockApproveAction, isPending: false }),
    useRejectAction: () => ({ mutateAsync: mockRejectAction, isPending: false }),
}))

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => mockUseAuth(),
}))

describe('AIAssistantPage', () => {
    beforeEach(() => {
        mockUser = { user_id: 'u1' }
        mockUseAuth.mockReturnValue({ user: mockUser, isLoading: false, error: null, refetch: vi.fn() })

        mockStreamMessage.mockImplementation(async (_request, onEvent) => {
            onEvent({ type: 'start', data: { status: 'thinking' } })
            onEvent({ type: 'delta', data: { text: 'Here is a quick ' } })
            onEvent({ type: 'delta', data: { text: 'summary.' } })
            onEvent({
                type: 'done',
                data: {
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
                },
            })
        })

        mockApproveAction.mockResolvedValue({ success: true })
        mockStreamMessage.mockClear()
        mockApproveAction.mockClear()
        mockRejectAction.mockClear()
        sessionStorage.clear()
    })

    it('sends a message and can approve a proposed action in global mode', async () => {
        render(<AIAssistantPage />)

        const input = screen.getByRole('textbox')
        fireEvent.change(input, { target: { value: 'Summarize this workflow' } })
        fireEvent.keyDown(input, { key: 'Enter', shiftKey: false })

        expect(mockStreamMessage).toHaveBeenCalledWith(
            {
                message: 'Summarize this workflow',
            },
            expect.any(Function),
            expect.anything()
        )

        expect(await screen.findByText('Here is a quick summary.')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /approve/i }))
        expect(mockApproveAction).toHaveBeenCalledWith('a1')

        expect(await screen.findByText('approved')).toBeInTheDocument()
    })

    it('shows global-only mode without raw selector values and records history', async () => {
        render(<AIAssistantPage />)

        expect(screen.getByText('Global mode')).toBeInTheDocument()
        expect(screen.queryByText('__global__')).not.toBeInTheDocument()
        expect(screen.queryByText(/S12345/)).not.toBeInTheDocument()

        const input = screen.getByRole('textbox')
        fireEvent.change(input, { target: { value: 'Hello there' } })
        fireEvent.keyDown(input, { key: 'Enter', shiftKey: false })

        await waitFor(() => expect(mockStreamMessage).toHaveBeenCalled())

        const call = mockStreamMessage.mock.calls[0]?.[0]
        expect(call).toEqual({ message: 'Hello there' })

        expect(await screen.findByText('Global mode · Press Enter to send')).toBeInTheDocument()
        expect(screen.getByText('Hello there', { selector: 'p' })).toBeInTheDocument()
    })

    it('limits chat history to the 10 most recent sessions', async () => {
        const history = Array.from({ length: 11 }, (_, index) => ({
            id: `session-${index}`,
            label: `Session ${index}`,
            preview: `Message ${index}`,
            updatedAt: new Date().toISOString(),
            entityType: 'global',
            entityId: null,
        }))
        sessionStorage.setItem('ai-assistant-chat-history-v1', JSON.stringify(history))

        render(<AIAssistantPage />)

        const items = await screen.findAllByTestId('chat-history-item')
        expect(items).toHaveLength(10)
        expect(screen.queryByText('Session 10')).not.toBeInTheDocument()
        expect(screen.getByText('Session 0')).toBeInTheDocument()
    })

    it('hides legacy surrogate-scoped sessions from chat history', async () => {
        sessionStorage.setItem(
            'ai-assistant-chat-history-v1',
            JSON.stringify([
                {
                    id: 'session-surrogate',
                    label: 'Surrogate Session',
                    preview: 'Should be hidden',
                    updatedAt: new Date().toISOString(),
                    entityType: 'surrogate',
                    entityId: 's1',
                    conversationId: 'conv-surrogate',
                    messages: [],
                },
                {
                    id: 'session-global',
                    label: 'Global Session',
                    preview: 'Should stay',
                    updatedAt: new Date().toISOString(),
                    entityType: 'global',
                    entityId: null,
                    conversationId: 'conv-global',
                    messages: [],
                },
            ])
        )

        render(<AIAssistantPage />)

        expect(await screen.findByText('Global Session')).toBeInTheDocument()
        expect(screen.queryByText('Surrogate Session')).not.toBeInTheDocument()
    })

    it('clears chat history when the user changes', async () => {
        sessionStorage.setItem(
            'ai-assistant-chat-history-v1',
            JSON.stringify([
                {
                    id: 'session-1',
                    label: 'Session 1',
                    preview: 'Message 1',
                    updatedAt: new Date().toISOString(),
                    entityType: 'global',
                    entityId: null,
                },
            ])
        )

        const { rerender } = render(<AIAssistantPage />)
        expect(await screen.findByText('Session 1')).toBeInTheDocument()

        mockUser = { user_id: 'u2' }
        mockUseAuth.mockReturnValue({ user: mockUser, isLoading: false, error: null, refetch: vi.fn() })
        rerender(<AIAssistantPage />)

        await waitFor(() => expect(screen.queryByText('Session 1')).not.toBeInTheDocument())
        expect(screen.getByText('Global Chat')).toBeInTheDocument()
    })

    it('starts with a fresh chat session by default even when history exists', async () => {
        sessionStorage.setItem(
            'ai-assistant-chat-history-v1',
            JSON.stringify([
                {
                    id: 'session-old',
                    label: 'Session Old',
                    preview: 'Existing preview',
                    updatedAt: new Date().toISOString(),
                    entityType: 'global',
                    entityId: null,
                    conversationId: 'conv-old',
                    messages: [
                        {
                            id: 'user-old',
                            role: 'user',
                            content: 'Old conversation content',
                            timestamp: '9:00 AM',
                            status: 'done',
                        },
                    ],
                },
            ])
        )

        render(<AIAssistantPage />)

        expect(screen.getByText('Session Old')).toBeInTheDocument()
        expect(screen.queryByText('Old conversation content', { selector: 'p' })).not.toBeInTheDocument()
        expect(
            screen.getByText("Hello! I'm your AI assistant. Ask me anything about your workflows.")
        ).toBeInTheDocument()
    })

    it('continues prior chat only when selected from chat history', async () => {
        sessionStorage.setItem(
            'ai-assistant-chat-history-v1',
            JSON.stringify([
                {
                    id: 'session-previous',
                    label: 'Previous Session',
                    preview: 'Earlier message',
                    updatedAt: new Date().toISOString(),
                    entityType: 'global',
                    entityId: null,
                    conversationId: 'conv-previous',
                    messages: [
                        {
                            id: 'user-previous',
                            role: 'user',
                            content: 'Earlier message',
                            timestamp: '9:00 AM',
                            status: 'done',
                        },
                    ],
                },
            ])
        )

        render(<AIAssistantPage />)

        fireEvent.click(screen.getByText('Previous Session'))

        const input = screen.getByRole('textbox')
        fireEvent.change(input, { target: { value: 'Continue this thread' } })
        fireEvent.keyDown(input, { key: 'Enter', shiftKey: false })

        await waitFor(() => expect(mockStreamMessage).toHaveBeenCalled())
        const request = mockStreamMessage.mock.calls[0]?.[0]
        expect(request).toEqual({
            message: 'Continue this thread',
            conversation_id: 'conv-previous',
        })
    })
})
