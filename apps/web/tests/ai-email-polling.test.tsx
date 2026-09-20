import { act, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import * as aiApi from '@/lib/api/ai'
import { useConversation } from '@/lib/hooks/use-ai'

vi.mock('@/lib/api/ai', () => ({ getConversation: vi.fn() }))

afterEach(() => { vi.useRealTimers(); vi.clearAllMocks() })

it.each(['executed', 'failed', 'delivery_unknown'])('polls queued email until %s, then stops', async (terminal) => {
    vi.useFakeTimers()
    const conversation = (status: string): aiApi.AIConversation => ({ messages: [{
        id: 'message', role: 'assistant', content: 'Reviewed draft', created_at: '2026-09-20T00:00:00Z',
        action_approvals: [{ id: 'approval', action_index: 0, action_type: 'send_email', status }],
    }] })
    vi.mocked(aiApi.getConversation)
        .mockResolvedValueOnce(conversation('approved'))
        .mockResolvedValue(conversation(terminal))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const wrapper = ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )
    const { result, unmount } = renderHook(() => useConversation('surrogate', 's1'), { wrapper })
    await act(async () => { await vi.advanceTimersByTimeAsync(100) })
    expect(result.current.data?.messages[0]?.action_approvals?.[0]?.status).toBe('approved')
    await act(async () => { await vi.advanceTimersByTimeAsync(2100) })
    expect(result.current.data?.messages[0]?.action_approvals?.[0]?.status).toBe(terminal)
    expect(aiApi.getConversation).toHaveBeenCalledTimes(2)
    await act(async () => { await vi.advanceTimersByTimeAsync(6000) })
    expect(aiApi.getConversation).toHaveBeenCalledTimes(2)
    unmount()
    client.clear()
})
