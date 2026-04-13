import { afterEach, describe, expect, it, vi } from "vitest"

describe("WebSocket URL resolution", () => {
    afterEach(() => {
        vi.unstubAllEnvs()
        vi.resetModules()
    })

    it("aligns loopback websocket hosts with the current browser hostname", async () => {
        const { resolveWebSocketUrl } = await import("@/lib/websocket-url")

        expect(
            resolveWebSocketUrl("http://localhost:8000", "/ws/notifications", {
                protocol: "http:",
                hostname: "127.0.0.1",
                host: "127.0.0.1:3000",
            })
        ).toBe("ws://127.0.0.1:8000/ws/notifications")
    })

    it("upgrades secure api bases to wss", async () => {
        const { resolveWebSocketUrl } = await import("@/lib/websocket-url")

        expect(
            resolveWebSocketUrl("https://app.example.com/api", "/ws/notifications", {
                protocol: "https:",
                hostname: "app.example.com",
                host: "app.example.com",
            })
        ).toBe("wss://app.example.com/api/ws/notifications")
    })
})
