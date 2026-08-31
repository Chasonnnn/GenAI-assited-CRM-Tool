import { POST } from "@/app/client-errors/route"

describe("client error telemetry route", () => {
    afterEach(() => {
        vi.restoreAllMocks()
        vi.unstubAllEnvs()
    })

    it("logs a fixed-schema event with server-side build metadata", async () => {
        vi.stubEnv("K_REVISION", "crm-web-test-revision")
        const log = vi.spyOn(console, "error").mockImplementation(() => undefined)
        const request = new Request("https://app.example.com/client-errors", {
            method: "POST",
            headers: {
                "content-type": "application/json",
                "sec-fetch-site": "same-origin",
            },
            body: JSON.stringify({ kind: "window_error", errorClass: "TypeError" }),
        })

        const response = await POST(request)

        expect(response.status).toBe(204)
        expect(log).toHaveBeenCalledOnce()
        expect(JSON.parse(log.mock.calls[0]![0])).toEqual({
            severity: "ERROR",
            event: "frontend_client_error",
            service: "crm-web",
            revision: "crm-web-test-revision",
            kind: "window_error",
            error_class: "TypeError",
        })
    })

    it("rejects payloads containing sensitive or free-form fields", async () => {
        const log = vi.spyOn(console, "error").mockImplementation(() => undefined)
        const request = new Request("https://app.example.com/client-errors", {
            method: "POST",
            headers: {
                "content-type": "application/json",
                "sec-fetch-site": "same-origin",
            },
            body: JSON.stringify({
                kind: "window_error",
                errorClass: "TypeError",
                message: "candidate name",
                stack: "private stack",
                url: "/surrogates/private-id",
                userId: "private-user-id",
            }),
        })

        const response = await POST(request)

        expect(response.status).toBe(400)
        expect(log).not.toHaveBeenCalled()
    })

    it("rejects cross-site submissions", async () => {
        const log = vi.spyOn(console, "error").mockImplementation(() => undefined)
        const request = new Request("https://app.example.com/client-errors", {
            method: "POST",
            headers: {
                "content-type": "application/json",
                "sec-fetch-site": "cross-site",
            },
            body: JSON.stringify({ kind: "window_error", errorClass: "TypeError" }),
        })

        const response = await POST(request)

        expect(response.status).toBe(403)
        expect(log).not.toHaveBeenCalled()
    })

    it("requires JSON requests", async () => {
        const log = vi.spyOn(console, "error").mockImplementation(() => undefined)
        const request = new Request("https://app.example.com/client-errors", {
            method: "POST",
            headers: {
                "content-type": "text/plain",
                "sec-fetch-site": "same-origin",
            },
            body: JSON.stringify({ kind: "window_error", errorClass: "TypeError" }),
        })

        const response = await POST(request)

        expect(response.status).toBe(415)
        expect(log).not.toHaveBeenCalled()
    })
})
