const reportClientError = vi.hoisted(() => vi.fn())

vi.mock("@/lib/client-error-telemetry", () => ({ reportClientError }))

describe("client error instrumentation", () => {
    it("captures uncaught errors and unhandled rejections", async () => {
        await import("../instrumentation-client")
        const error = new TypeError("private message")
        window.dispatchEvent(new ErrorEvent("error", { error }))
        const rejection = new Event("unhandledrejection")
        Object.defineProperty(rejection, "reason", { value: error })
        window.dispatchEvent(rejection)

        expect(reportClientError).toHaveBeenNthCalledWith(1, "window_error", error)
        expect(reportClientError).toHaveBeenNthCalledWith(2, "unhandled_rejection", error)
    })
})
