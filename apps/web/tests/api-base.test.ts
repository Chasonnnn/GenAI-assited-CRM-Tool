import { afterEach, describe, expect, it, vi } from "vitest"

describe("API base resolution", () => {
    afterEach(() => {
        vi.unstubAllEnvs()
        vi.resetModules()
    })

    it("aligns the API host with the current loopback hostname", async () => {
        const { resolveApiBase } = await import("../lib/api-base")

        expect(resolveApiBase("http://localhost:8000", { protocol: "http:", hostname: "127.0.0.1" })).toBe(
            "http://127.0.0.1:8000"
        )
    })

    it("aligns auth login URLs with the current loopback hostname", async () => {
        const { resolveAuthApiBase } = await import("../lib/auth-utils")

        expect(
            resolveAuthApiBase("http://localhost:8000", { protocol: "http:", hostname: "127.0.0.1" })
        ).toBe("http://127.0.0.1:8000")
    })
})
