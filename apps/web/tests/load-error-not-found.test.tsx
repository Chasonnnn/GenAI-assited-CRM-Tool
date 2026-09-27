import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { ApiError } from "@/lib/api"

vi.mock("@/components/app-link", () => ({
    default: ({ children, href, ...props }: React.ComponentProps<"a">) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

import AppNotFound from "@/app/(app)/not-found"
import RootNotFound from "@/app/not-found"
import { LoadErrorState, NotFoundState, QueryErrorState } from "@/components/error-state"
import { getErrorStatus, getQueryErrorKind, isNotFoundError } from "@/lib/error-utils"

const surrogateNotFound = {
    title: "Surrogate not found",
    backHref: "/surrogates",
    backLabel: "Back to Surrogates",
}

describe("LoadErrorState", () => {
    it("names what failed and retries without showing the raw error", () => {
        const onRetry = vi.fn()
        const { container } = render(<LoadErrorState title="Couldn't load alerts" onRetry={onRetry} />)

        expect(screen.getByText("Couldn't load alerts")).toBeInTheDocument()
        expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true")

        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(onRetry).toHaveBeenCalledOnce()
    })

    it("blocks repeat retries and keeps focus while the retry is in flight", () => {
        const onRetry = vi.fn()
        const { rerender } = render(<LoadErrorState title="Couldn't load alerts" onRetry={onRetry} />)

        const retry = screen.getByRole("button", { name: "Try again" })
        retry.focus()
        rerender(<LoadErrorState title="Couldn't load alerts" onRetry={onRetry} isRetrying />)

        expect(retry).toHaveAttribute("aria-disabled", "true")
        expect(retry).toHaveFocus()
        expect(retry.querySelector("svg.animate-spin")).toHaveAttribute("aria-hidden", "true")
        fireEvent.click(retry)
        expect(onRetry).not.toHaveBeenCalled()
    })
})

describe("NotFoundState", () => {
    it("names the missing record with one back action", () => {
        render(<NotFoundState {...surrogateNotFound} />)

        expect(screen.getByText("Surrogate not found")).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Back to Surrogates" })).toHaveAttribute("href", "/surrogates")
        expect(screen.queryByRole("button")).not.toBeInTheDocument()
    })
})

describe("QueryErrorState", () => {
    it("renders a load error with retry for a 500 and hides the server message", () => {
        const onRetry = vi.fn()
        render(
            <QueryErrorState
                error={new ApiError(500, "Internal Server Error", "boom")}
                onRetry={onRetry}
                title="Couldn't load queues"
                notFound={surrogateNotFound}
            />
        )

        expect(screen.getByText("Couldn't load queues")).toBeInTheDocument()
        expect(screen.queryByText(/boom/)).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(onRetry).toHaveBeenCalledOnce()
    })

    it("renders the not-found state for a 404 on a record route", () => {
        render(
            <QueryErrorState
                error={new ApiError(404, "Not Found", "Surrogate not found")}
                onRetry={vi.fn()}
                title="Couldn't load surrogate"
                notFound={surrogateNotFound}
            />
        )

        expect(screen.getByRole("link", { name: "Back to Surrogates" })).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument()
    })

    it("gives the title heading semantics only when a level is passed", () => {
        const { unmount } = render(
            <QueryErrorState
                error={new ApiError(404, "Not Found")}
                onRetry={vi.fn()}
                title="Couldn't load intended parent"
                notFound={{ title: "Intended parent not found", backHref: "/intended-parents", backLabel: "Back to Intended Parents" }}
                headingLevel={1}
            />
        )
        expect(screen.getByRole("heading", { level: 1, name: "Intended parent not found" })).toBeInTheDocument()
        unmount()

        render(<LoadErrorState title="Couldn't load alerts" onRetry={vi.fn()} />)
        expect(screen.queryByRole("heading")).not.toBeInTheDocument()
    })

    it("treats a 422 from a malformed id as not found on record routes only", () => {
        const invalidId = new ApiError(422, "Unprocessable Entity", "invite_id: Input should be a valid UUID")

        const { unmount } = render(
            <QueryErrorState error={invalidId} onRetry={vi.fn()} title="Couldn't load invite" notFound={surrogateNotFound} />
        )
        expect(screen.getByText("Surrogate not found")).toBeInTheDocument()
        expect(screen.queryByText(/valid UUID/)).not.toBeInTheDocument()
        unmount()

        render(<QueryErrorState error={invalidId} onRetry={vi.fn()} title="Couldn't load agencies" />)
        expect(screen.getByText("Couldn't load agencies")).toBeInTheDocument()
    })

    it("passes retry progress to the load error", () => {
        render(
            <QueryErrorState
                error={new ApiError(500, "Internal Server Error")}
                onRetry={vi.fn()}
                isRetrying
                title="Couldn't load agencies"
            />
        )

        expect(screen.getByRole("button", { name: "Try again" })).toHaveAttribute("aria-disabled", "true")
    })

    it("renders a load error for a 404 on a list without not-found copy", () => {
        render(
            <QueryErrorState error={new ApiError(404, "Not Found")} onRetry={vi.fn()} title="Couldn't load agencies" />
        )

        expect(screen.getByText("Couldn't load agencies")).toBeInTheDocument()
    })
})

describe("error classification", () => {
    it("reads the status from ApiError only", () => {
        expect(getErrorStatus(new ApiError(404, "Not Found"))).toBe(404)
        expect(getErrorStatus(new Error("404"))).toBeNull()
        expect(getErrorStatus(undefined)).toBeNull()
    })

    it("maps statuses to query error kinds", () => {
        expect(getQueryErrorKind(new ApiError(404, "Not Found"))).toBe("not_found")
        expect(getQueryErrorKind(new ApiError(422, "Unprocessable Entity"))).toBe("error")
        expect(getQueryErrorKind(new ApiError(422, "Unprocessable Entity"), { includeInvalidId: true })).toBe("not_found")
        expect(getQueryErrorKind(new ApiError(500, "Internal Server Error"))).toBe("error")
        expect(getQueryErrorKind(new TypeError("Failed to fetch"))).toBe("error")
        expect(isNotFoundError(new ApiError(404, "Not Found"))).toBe(true)
    })
})

describe("not-found routes", () => {
    it("renders the in-shell not-found page with a Dashboard link", () => {
        render(<AppNotFound />)

        expect(screen.getByRole("heading", { level: 1, name: "Page not found" })).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Go to Dashboard" })).toHaveAttribute("href", "/dashboard")
    })

    it("renders the public not-found page with a home link", () => {
        render(<RootNotFound />)

        expect(screen.getByRole("main")).toContainElement(
            screen.getByRole("heading", { level: 1, name: "Page not found" })
        )
        expect(screen.getByRole("link", { name: "Go home" })).toHaveAttribute("href", "/")
    })
})
