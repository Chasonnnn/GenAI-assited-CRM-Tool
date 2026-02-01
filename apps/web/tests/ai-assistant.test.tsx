import type { PropsWithChildren } from "react"
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
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
    useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}))

const mockStreamMessage = vi.fn()
const mockApproveAction = vi.fn()
const mockRejectAction = vi.fn()
const mockUseConversation = vi.fn()
const mockUseAuth = vi.fn()

let mockUser: { user_id: string } | null = { user_id: 'u1' }

vi.mock('@/lib/hooks/use-ai', () => ({
    useAISettings: () => ({ data: { is_enabled: true } }),
    useStreamChatMessage: () => mockStreamMessage,
    useApproveAction: () => ({ mutateAsync: mockApproveAction, isPending: false }),
    useRejectAction: () => ({ mutateAsync: mockRejectAction, isPending: false }),
    useConversation: () => mockUseConversation(),
}))

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => mockUseAuth(),
}))

describe('AIAssistantPage', () => {
    beforeEach(() => {
        mockUser = { user_id: 'u1' }
        mockUseAuth.mockReturnValue({ user: mockUser, isLoading: false, error: null, refetch: vi.fn() })
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

    it('sends a message and can approve a proposed action', async () => {
        render(<AIAssistantPage />)

        fireEvent.change(screen.getByTestId('select'), { target: { value: 's1' } })

        const input = screen.getByRole('textbox')
        fireEvent.change(input, { target: { value: 'Summarize this surrogate' } })
        fireEvent.keyDown(input, { key: 'Enter', shiftKey: false })

        expect(mockStreamMessage).toHaveBeenCalledWith(
            {
                entity_type: 'surrogate',
                entity_id: 's1',
                message: 'Summarize this surrogate',
            },
            expect.any(Function),
            expect.anything()
        )

        expect(await screen.findByText('Here is a quick summary.')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /approve/i }))
        expect(mockApproveAction).toHaveBeenCalledWith('a1')

        expect(await screen.findByText('approved')).toBeInTheDocument()
    })

    it('allows global chat without selecting a surrogate and records history', async () => {
        render(<AIAssistantPage />)

        const input = screen.getByRole('textbox')
        fireEvent.change(input, { target: { value: 'Hello there' } })
        fireEvent.keyDown(input, { key: 'Enter', shiftKey: false })

        await waitFor(() => expect(mockStreamMessage).toHaveBeenCalled())

        const call = mockStreamMessage.mock.calls[0]?.[0]
        expect(call).toEqual({ message: 'Hello there' })

        expect(
            await screen.findByText(/Global mode.*select a surrogate to add context/i),
        ).toBeInTheDocument()
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
        expect(screen.getByText('No chat history yet')).toBeInTheDocument()
    })
})
