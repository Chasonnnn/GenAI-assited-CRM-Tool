import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { render } from "@testing-library/react"

import { useNotificationSocket } from "@/lib/hooks/use-notification-socket"
import { getWebSocketUrl } from "@/lib/websocket-url"

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({ user: { id: "user-1" } }),
}))

vi.mock("@/lib/websocket-url", () => ({
    getWebSocketUrl: vi.fn(() => "ws://127.0.0.1:8000/ws/notifications"),
}))

class MockWebSocket {
    static OPEN = 1
    static CLOSED = 3
    static CONNECTING = 0
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

    close(code = 1000, reason = "closed") {
        this.readyState = MockWebSocket.CLOSED
        this.onclose?.({ code, reason })
    }
}

function NotificationSocketHarness() {
    useNotificationSocket()
    return null
}

describe("useNotificationSocket", () => {
    beforeEach(() => {
        MockWebSocket.instances = []
        vi.stubGlobal("WebSocket", MockWebSocket)
    })

    afterEach(() => {
        vi.unstubAllGlobals()
    })

    it("uses the shared websocket URL resolver for loopback-safe connections", () => {
        render(<NotificationSocketHarness />)

        const ws = MockWebSocket.instances[0]
        if (!ws) {
            throw new Error("WebSocket instance was not created")
        }

        expect(getWebSocketUrl).toHaveBeenCalledWith("/ws/notifications")
        expect(ws.url).toBe("ws://127.0.0.1:8000/ws/notifications")
    })
})
