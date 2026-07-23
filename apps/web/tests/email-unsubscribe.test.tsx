import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mockHeaders = vi.fn()

vi.mock("next/headers", () => ({
    headers: () => mockHeaders(),
}))

import UnsubscribePage from "@/app/email/unsubscribe/[token]/page"
import { POST as confirmUnsubscribe } from "@/app/email/unsubscribe/[token]/confirm/route"
import { POST as oneClickPost } from "@/app/email/unsubscribe/[token]/one-click/route"

describe("email unsubscribe routes", () => {
    beforeEach(() => {
        vi.restoreAllMocks()
        mockHeaders.mockResolvedValue(new Headers({ "x-org-name": "EWI" }))
        process.env.NEXT_PUBLIC_API_BASE_URL = "https://api.example.com"
    })

    it("renders a non-mutating confirmation page on GET", async () => {
        const fetchSpy = vi.spyOn(globalThis, "fetch")
        const element = await UnsubscribePage({
            params: Promise.resolve({ token: "token-123" }),
            searchParams: Promise.resolve({}),
        })

        render(element)

        expect(fetchSpy).not.toHaveBeenCalled()
        expect(screen.getByRole("heading", { name: /confirm unsubscribe/i })).toBeInTheDocument()
        expect(screen.getByText(/marketing emails from/i)).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /unsubscribe/i })).toBeInTheDocument()
    })

    it("shows the success state without calling the API after POST redirect", async () => {
        const fetchSpy = vi.spyOn(globalThis, "fetch")
        const element = await UnsubscribePage({
            params: Promise.resolve({ token: "token-123" }),
            searchParams: Promise.resolve({ status: "unsubscribed" }),
        })

        render(element)

        expect(fetchSpy).not.toHaveBeenCalled()
        expect(screen.getByRole("heading", { name: /you're unsubscribed/i })).toBeInTheDocument()
    })

    it("performs unsubscribe only on explicit confirmation POST", async () => {
        const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }))

        const res = await confirmUnsubscribe(
            new Request("https://app.example.com/email/unsubscribe/token-123/confirm", {
                method: "POST",
            }),
            { params: Promise.resolve({ token: "token-123" }) },
        )

        expect(fetchSpy).toHaveBeenCalledWith(
            "https://api.example.com/email/unsubscribe/token-123",
            expect.objectContaining({ method: "POST", cache: "no-store" }),
        )
        expect(res.status).toBe(303)
        expect(res.headers.get("location")).toBe(
            "https://app.example.com/email/unsubscribe/token-123?status=unsubscribed",
        )
    })

    it("keeps one-click unsubscribe POST-only", async () => {
        const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }))

        const postRes = await oneClickPost(
            new Request("https://app.example.com/email/unsubscribe/token-123/one-click", {
                method: "POST",
            }),
            { params: Promise.resolve({ token: "token-123" }) },
        )
        expect(postRes.status).toBe(200)
        expect(fetchSpy).toHaveBeenCalledTimes(1)
    })

    it("returns a retryable failure when the one-click API request cannot reach the backend", async () => {
        vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("network unavailable"))

        const postRes = await oneClickPost(
            new Request("https://app.example.com/email/unsubscribe/token-123/one-click", {
                method: "POST",
            }),
            { params: Promise.resolve({ token: "token-123" }) },
        )

        expect(postRes.status).toBe(503)
        expect(postRes.headers.get("retry-after")).toBe("60")
    })

    it("returns a retryable failure when the backend does not persist the one-click suppression", async () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValue(
            new Response("temporarily unavailable", { status: 503 }),
        )

        const postRes = await oneClickPost(
            new Request("https://app.example.com/email/unsubscribe/token-123/one-click", {
                method: "POST",
            }),
            { params: Promise.resolve({ token: "token-123" }) },
        )

        expect(postRes.status).toBe(503)
    })

    it("does not redirect a confirmation request when the backend rejects the suppression", async () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValue(
            new Response("temporarily unavailable", { status: 503 }),
        )

        await expect(
            confirmUnsubscribe(
                new Request("https://app.example.com/email/unsubscribe/token-123/confirm", {
                    method: "POST",
                }),
                { params: Promise.resolve({ token: "token-123" }) },
            ),
        ).rejects.toThrow("Unsubscribe API request failed")
    })

    it("keeps the backend's generic invalid-token response indistinguishable from success", async () => {
        vi.spyOn(globalThis, "fetch").mockResolvedValue(
            new Response("If this email address exists, it has been unsubscribed.", {
                status: 200,
            }),
        )

        const postRes = await oneClickPost(
            new Request("https://app.example.com/email/unsubscribe/invalid-token/one-click", {
                method: "POST",
            }),
            { params: Promise.resolve({ token: "invalid-token" }) },
        )

        expect(postRes.status).toBe(200)
    })
})
