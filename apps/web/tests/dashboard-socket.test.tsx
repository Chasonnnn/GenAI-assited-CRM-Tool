import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, act } from '@testing-library/react'
import { useDashboardSocket } from '@/lib/hooks/use-dashboard-socket'

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({ user: { id: 'user-1' } }),
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
})
