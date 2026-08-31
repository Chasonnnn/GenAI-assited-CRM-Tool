import { render } from "@testing-library/react"

import { ErrorState } from "@/components/error-state"

const reportClientError = vi.hoisted(() => vi.fn())

vi.mock("@/lib/client-error-telemetry", () => ({ reportClientError }))

describe("error state telemetry", () => {
    it("reports errors caught by React boundaries", () => {
        const error = new TypeError("private render failure")

        render(<ErrorState error={error} reset={vi.fn()} />)

        expect(reportClientError).toHaveBeenCalledWith("react_error_boundary", error)
    })
})
