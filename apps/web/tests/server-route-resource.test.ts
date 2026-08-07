import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const mockHeaders = vi.fn()

vi.mock("next/headers", () => ({
    headers: () => mockHeaders(),
}))

import {
    fetchServerRouteResource,
    getServerRouteResourceStatus,
    ServerRouteResourceError,
} from "../lib/server-route-resource"

describe("getServerRouteResourceStatus", () => {
    beforeEach(() => {
        mockHeaders.mockResolvedValue(
            new Headers({
                cookie: "crm_session=session-token",
                "x-org-id": "org-1",
                "x-org-slug": "ewi",
                "x-org-name": "EWI",
            }),
        )
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    it("returns not_found for 404 responses and forwards auth context", async () => {
        const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
            new Response(null, { status: 404 }),
        )

        await expect(
            getServerRouteResourceStatus("/campaigns/camp-1"),
        ).resolves.toBe("not_found")

        const [, init] = fetchSpy.mock.calls[0] ?? []
        const requestHeaders = init?.headers as Headers

        expect(fetchSpy).toHaveBeenCalledWith(
            "http://localhost:8000/campaigns/camp-1",
            expect.objectContaining({ cache: "no-store" }),
        )
        expect(requestHeaders.get("cookie")).toBe("crm_session=session-token")
        expect(requestHeaders.get("x-org-id")).toBe("org-1")
        expect(requestHeaders.get("x-org-slug")).toBe("ewi")
        expect(requestHeaders.get("x-org-name")).toBe("EWI")
    })

    it("returns authenticated JSON for request-scoped query hydration", async () => {
        const resource = { id: "match-1", organization_id: "org-1" }
        const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
            Response.json(resource),
        )

        await expect(
            fetchServerRouteResource<typeof resource>("/matches/match-1"),
        ).resolves.toEqual(resource)

        const [, init] = fetchSpy.mock.calls[0] ?? []
        const requestHeaders = init?.headers as Headers
        expect(requestHeaders.get("cookie")).toBe("crm_session=session-token")
        expect(requestHeaders.get("x-org-id")).toBe("org-1")
    })

    it("preserves upstream status for server-owned route decisions", async () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValue(
            new Response(null, { status: 404 }),
        )

        await expect(
            fetchServerRouteResource("/matches/missing"),
        ).rejects.toEqual(
            expect.objectContaining<Partial<ServerRouteResourceError>>({ status: 404 }),
        )
    })

    it("returns pass_through for auth and permission responses", async () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValue(
            new Response(null, { status: 403 }),
        )

        await expect(
            getServerRouteResourceStatus("/matches/match-1"),
        ).resolves.toBe("pass_through")
    })

    it("throws for unexpected upstream failures", async () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValue(
            new Response("boom", { status: 500 }),
        )

        await expect(
            getServerRouteResourceStatus("/forms/form-1"),
        ).rejects.toThrow("Failed route resource check for /forms/form-1: 500")
    })
})
