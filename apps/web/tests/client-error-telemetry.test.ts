describe("client error telemetry", () => {
    it("reports only a normalized error class and deduplicates repeats", async () => {
        const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
        vi.stubGlobal("fetch", fetchMock)
        const { reportClientError } = await import("@/lib/client-error-telemetry")
        const error = new TypeError("Candidate Jane at /surrogates/private-id")

        reportClientError("window_error", error)
        reportClientError("window_error", error)

        expect(fetchMock).toHaveBeenCalledOnce()
        expect(fetchMock).toHaveBeenCalledWith(
            "/client-errors",
            expect.objectContaining({
                method: "POST",
                credentials: "same-origin",
                keepalive: true,
                body: JSON.stringify({ kind: "window_error", errorClass: "TypeError" }),
            }),
        )
        const request = fetchMock.mock.calls[0]![1] as RequestInit
        expect(request.body).not.toContain("Candidate Jane")
        expect(request.body).not.toContain("surrogates")
    })
})
