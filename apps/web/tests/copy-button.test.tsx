import { act, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from "vitest"

import { CopyButton } from "@/components/ui/copy-button"

const mocks = vi.hoisted(() => ({ error: vi.fn() }))

vi.mock("@/components/ui/toast", () => ({ toast: { error: mocks.error } }))

function deferred() {
    let resolve!: () => void
    const promise = new Promise<void>((res) => {
        resolve = res
    })
    return { promise, resolve }
}

describe("CopyButton", () => {
    let writeText: MockInstance<(data: string) => Promise<void>>

    beforeEach(() => {
        writeText = vi.spyOn(navigator.clipboard, "writeText")
        mocks.error.mockClear()
    })

    afterEach(() => {
        vi.useRealTimers()
        writeText.mockRestore()
    })

    it("shows the copied state only after the clipboard write resolves", async () => {
        const write = deferred()
        writeText.mockReturnValue(write.promise)
        render(<CopyButton value="jane@example.com" aria-label="Copy email" />)

        const button = screen.getByRole("button", { name: "Copy email" })
        fireEvent.click(button)

        expect(writeText).toHaveBeenCalledWith("jane@example.com")
        expect(button).not.toHaveAttribute("data-copied")
        expect(screen.getByRole("status")).toBeEmptyDOMElement()

        await act(async () => {
            write.resolve()
            await write.promise
        })

        expect(button).toHaveAttribute("data-copied")
        expect(screen.getByRole("status")).toHaveTextContent("Copied")
        expect(mocks.error).not.toHaveBeenCalled()
    })

    it("reports a failed clipboard write without showing the copied state", async () => {
        writeText.mockRejectedValue(new Error("denied"))
        render(<CopyButton value="jane@example.com" aria-label="Copy email" />)

        const button = screen.getByRole("button", { name: "Copy email" })
        await act(async () => {
            fireEvent.click(button)
        })

        expect(button).not.toHaveAttribute("data-copied")
        expect(screen.getByRole("status")).toBeEmptyDOMElement()
        expect(mocks.error).toHaveBeenCalledWith("Failed to copy")
    })

    it("keeps the label and accessible name constant while stacking both decorative icons", async () => {
        writeText.mockResolvedValue(undefined)
        render(<CopyButton value={"CODE-1\nCODE-2"} variant="outline">Copy All</CopyButton>)

        const button = screen.getByRole("button", { name: "Copy All" })
        const icons = button.querySelectorAll("svg")
        expect(icons).toHaveLength(2)
        icons.forEach((icon) => {
            expect(icon).toHaveAttribute("aria-hidden", "true")
            expect(icon).toHaveClass("[grid-area:1/1]")
        })

        await act(async () => {
            fireEvent.click(button)
        })

        expect(button).toHaveAttribute("data-copied")
        expect(button).toHaveAccessibleName("Copy All")
        expect(button).toHaveTextContent(/^Copy All$/)
    })

    it("resets after 2000ms and restarts the timer on a repeated copy", async () => {
        vi.useFakeTimers()
        writeText.mockResolvedValue(undefined)
        render(<CopyButton value="https://example.com/book/abc" aria-label="Copy booking link" />)

        const button = screen.getByRole("button", { name: "Copy booking link" })
        await act(async () => {
            fireEvent.click(button)
        })
        expect(button).toHaveAttribute("data-copied")

        act(() => {
            vi.advanceTimersByTime(1500)
        })
        await act(async () => {
            fireEvent.click(button)
        })
        act(() => {
            vi.advanceTimersByTime(1500)
        })
        expect(button).toHaveAttribute("data-copied")

        act(() => {
            vi.advanceTimersByTime(500)
        })
        expect(button).not.toHaveAttribute("data-copied")
        expect(screen.getByRole("status")).toBeEmptyDOMElement()
        expect(vi.getTimerCount()).toBe(0)
    })

    it("clears the reset timer on unmount", async () => {
        vi.useFakeTimers()
        writeText.mockResolvedValue(undefined)
        const { unmount } = render(<CopyButton value="org-1" aria-label="Copy ID" />)

        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: "Copy ID" }))
        })
        expect(vi.getTimerCount()).toBe(1)

        unmount()

        expect(vi.getTimerCount()).toBe(0)
    })
})
