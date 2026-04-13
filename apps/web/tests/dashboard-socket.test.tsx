import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, act } from '@testing-library/react'
import { useQueryClient } from '@tanstack/react-query'
import { useDashboardSocket } from '@/lib/hooks/use-dashboard-socket'
import { getWebSocketUrl } from '@/lib/websocket-url'

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({ user: { id: 'user-1' } }),
}))

vi.mock('@/lib/websocket-url', () => ({
    getWebSocketUrl: vi.fn(() => 'ws://127.0.0.1:8000/ws/notifications'),
}))

class MockWebSocket {
    static OPEN = 1
    static CLOSED = 3
    static instances: MockWebSocket[] = []

    readyState = MockWebSocket.OPEN
    url: string
    onopen?: () => void
    onmessage?: (event: { data: string }) => void
    onerror?: () => void
    onclose?: (event: { code: number; reason: string }) => void

    constructor(url: string) {
        this.url = url
        MockWebSocket.instances.push(this)
    }

    send() {}

    close(code = 1000, reason = 'closed') {
        this.readyState = MockWebSocket.CLOSED
        this.onclose?.({ code, reason })
    }

    emitMessage(data: string) {
        this.onmessage?.({ data })
    }
}

function DashboardSocketHarness() {
    useDashboardSocket(true)
    return null
}

describe('useDashboardSocket', () => {
    let errorSpy: ReturnType<typeof vi.spyOn>

    beforeEach(() => {
        MockWebSocket.instances = []
        vi.stubGlobal('WebSocket', MockWebSocket)
        errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    })

    afterEach(() => {
        errorSpy.mockRestore()
        vi.unstubAllGlobals()
    })

    it('ignores pong and non-JSON messages without logging errors', () => {
        render(<DashboardSocketHarness />)

        const ws = MockWebSocket.instances[0]
        if (!ws) {
            throw new Error('WebSocket instance was not created')
        }

        act(() => {
            ws.emitMessage('pong')
            ws.emitMessage('not-json')
            ws.emitMessage('still-not-json')
        })

        expect(errorSpy).not.toHaveBeenCalled()
    })

    it('invalidates all surrogate stats queries on stats updates', () => {
        render(<DashboardSocketHarness />)

        const ws = MockWebSocket.instances[0]
        if (!ws) {
            throw new Error('WebSocket instance was not created')
        }

        const queryClient = vi.mocked(useQueryClient).mock.results.at(-1)?.value
        if (!queryClient) {
            throw new Error('Query client mock was not initialized')
        }

        act(() => {
            ws.emitMessage(JSON.stringify({ type: 'stats_update', data: { total: 123 } }))
        })

        expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
            queryKey: ['surrogates', 'stats'],
            refetchType: 'active',
        })
    })

    it('uses the shared websocket URL resolver for loopback-safe connections', () => {
        render(<DashboardSocketHarness />)

        const ws = MockWebSocket.instances[0]
        if (!ws) {
            throw new Error('WebSocket instance was not created')
        }

        expect(getWebSocketUrl).toHaveBeenCalledWith('/ws/notifications')
        expect(ws.url).toBe('ws://127.0.0.1:8000/ws/notifications')
    })
})
