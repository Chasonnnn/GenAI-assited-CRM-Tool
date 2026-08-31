import { POST } from "@/app/client-errors/route"

describe("client error telemetry route", () => {
    afterEach(() => {
        vi.restoreAllMocks()
        vi.unstubAllGlobals()
        vi.unstubAllEnvs()
    })

    it("rejects anonymous submissions even when fetch metadata is omitted or spoofed", async () => {
        const log = vi.spyOn(console, "error").mockImplementation(() => undefined)

        for (const fetchSite of [undefined, "same-origin"]) {
            const headers: Record<string, string> = {
                "content-type": "application/json",
            }
            if (fetchSite) {
                headers["sec-fetch-site"] = fetchSite
            }
            const request = new Request("https://app.example.com/client-errors", {
                method: "POST",
                headers,
                body: JSON.stringify({ kind: "window_error", errorClass: "TypeError" }),
            })

            const response = await POST(request)

            expect(response.status).toBe(401)
        }
        expect(log).not.toHaveBeenCalled()
    })

    it("rejects forged session cookies before emitting telemetry", async () => {
        vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
        const authenticate = vi.fn().mockResolvedValue(new Response(null, { status: 401 }))
        vi.stubGlobal("fetch", authenticate)
        const log = vi.spyOn(console, "error").mockImplementation(() => undefined)
        const request = new Request("https://app.example.com/client-errors", {
            method: "POST",
            headers: {
                "content-type": "application/json",
                "sec-fetch-site": "same-origin",
                "x-csrf-token": "csrf-token",
                cookie: "crm_session=forged-session; crm_csrf=csrf-token",
            },
            body: JSON.stringify({ kind: "window_error", errorClass: "TypeError" }),
        })

        const response = await POST(request)

        expect(response.status).toBe(401)
        expect(log).not.toHaveBeenCalled()
        expect(authenticate).toHaveBeenCalledWith(
            "https://api.example.com/auth/me",
            expect.objectContaining({
                cache: "no-store",
                headers: {
                    cookie: "crm_session=forged-session; crm_csrf=csrf-token",
                    origin: "https://app.example.com",
                },
            }),
        )
    })

    it("rejects authenticated-cookie submissions without matching CSRF", async () => {
        const authenticate = vi.fn().mockResolvedValue(new Response(null, { status: 200 }))
        vi.stubGlobal("fetch", authenticate)
        const log = vi.spyOn(console, "error").mockImplementation(() => undefined)

        for (const csrfHeader of [undefined, "wrong-token"]) {
            const headers: Record<string, string> = {
                "content-type": "application/json",
                "sec-fetch-site": "same-origin",
                cookie: "crm_session=valid-session; crm_csrf=valid-token",
            }
            if (csrfHeader) {
                headers["x-csrf-token"] = csrfHeader
            }
            const request = new Request("https://app.example.com/client-errors", {
                method: "POST",
                headers,
                body: JSON.stringify({ kind: "window_error", errorClass: "TypeError" }),
            })

            const response = await POST(request)

            expect(response.status).toBe(403)
        }
        expect(authenticate).not.toHaveBeenCalled()
        expect(log).not.toHaveBeenCalled()
    })

    it("forwards the validated public proxy origin instead of the internal Next origin", async () => {
        vi.stubEnv("NODE_ENV", "production")
        vi.stubEnv("PLATFORM_BASE_DOMAIN", "example.com")
        vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
        const authenticate = vi.fn().mockResolvedValue(new Response(null, { status: 200 }))
        vi.stubGlobal("fetch", authenticate)
        const log = vi.spyOn(console, "error").mockImplementation(() => undefined)
        const request = new Request("http://localhost:3000/client-errors", {
            method: "POST",
            headers: {
                "content-type": "application/json",
                "sec-fetch-site": "same-origin",
                "x-forwarded-host": "agency.example.com",
                "x-forwarded-proto": "https",
                "x-csrf-token": "csrf-token",
                cookie: "crm_session=valid-session; crm_csrf=csrf-token",
            },
            body: JSON.stringify({ kind: "window_error", errorClass: "TypeError" }),
        })

        const response = await POST(request)

        expect(response.status).toBe(204)
        expect(log).toHaveBeenCalledOnce()
        expect(authenticate).toHaveBeenCalledWith(
            "https://api.example.com/auth/me",
            expect.objectContaining({
                headers: expect.objectContaining({ origin: "https://agency.example.com" }),
            }),
        )
    })

    it("rejects untrusted production host and protocol metadata before authentication", async () => {
        vi.stubEnv("NODE_ENV", "production")
        vi.stubEnv("PLATFORM_BASE_DOMAIN", "example.com")
        const authenticate = vi.fn().mockResolvedValue(new Response(null, { status: 200 }))
        vi.stubGlobal("fetch", authenticate)
        const log = vi.spyOn(console, "error").mockImplementation(() => undefined)

        for (const [host, protocol] of [
            ["attacker.example.net", "https"],
            ["agency.example.com", "http"],
        ]) {
            const request = new Request("http://localhost:3000/client-errors", {
                method: "POST",
                headers: {
                    "content-type": "application/json",
                    "sec-fetch-site": "same-origin",
                    "x-forwarded-host": host,
                    "x-forwarded-proto": protocol,
                    "x-csrf-token": "csrf-token",
                    cookie: "crm_session=valid-session; crm_csrf=csrf-token",
                },
                body: JSON.stringify({ kind: "window_error", errorClass: "TypeError" }),
            })

            const response = await POST(request)

            expect(response.status).toBe(401)
        }
        expect(authenticate).not.toHaveBeenCalled()
        expect(log).not.toHaveBeenCalled()
    })

    it("logs a fixed-schema event with server-side build metadata", async () => {
        vi.stubEnv("K_REVISION", "crm-web-test-revision")
        vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
        vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 200 })))
        const log = vi.spyOn(console, "error").mockImplementation(() => undefined)
        const request = new Request("https://app.example.com/client-errors", {
            method: "POST",
            headers: {
                "content-type": "application/json",
                "sec-fetch-site": "same-origin",
                "x-csrf-token": "csrf-token",
                cookie: "crm_session=valid-session; crm_csrf=csrf-token",
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
        vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com")
        vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 200 })))
        const log = vi.spyOn(console, "error").mockImplementation(() => undefined)
        const request = new Request("https://app.example.com/client-errors", {
            method: "POST",
            headers: {
                "content-type": "application/json",
                "sec-fetch-site": "same-origin",
                "x-csrf-token": "csrf-token",
                cookie: "crm_session=valid-session; crm_csrf=csrf-token",
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
