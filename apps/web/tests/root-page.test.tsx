import { describe, expect, it, vi } from "vitest"

const mockRedirect = vi.fn(() => {
    throw new Error("NEXT_REDIRECT")
})

vi.mock("next/navigation", async () => {
    const actual = await vi.importActual("next/navigation")
    return {
        ...actual,
        redirect: (...args: unknown[]) => mockRedirect(...args),
    }
})

import RootPage from "../app/page"

describe("RootPage", () => {
    it("redirects the root route to dashboard", () => {
        expect(() => RootPage()).toThrow("NEXT_REDIRECT")
        expect(mockRedirect).toHaveBeenCalledWith("/dashboard")
    })
})
