import { describe, it, expect, vi, afterEach } from "vitest"


describe("msw handlers", () => {
    afterEach(() => {
        vi.unstubAllEnvs()
    })

    it("uses NEXT_PUBLIC_API_BASE_URL when set", async () => {
        vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.test")
        vi.stubEnv("NEXT_PUBLIC_API_URL", "")
        vi.resetModules()

        const { handlers } = await import("./mocks/handlers")
        const authHandler = handlers.find((handler) => handler.info.path.endsWith("/auth/me"))

        expect(authHandler?.info.path).toBe("https://api.example.test/auth/me")
    })
})
