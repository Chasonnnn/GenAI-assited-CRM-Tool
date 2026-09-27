import { act, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from "vitest"

import { CopyField } from "@/components/ui/copy-field"

vi.mock("@/components/ui/toast", () => ({ toast: { error: vi.fn() } }))

const WEBHOOK_URL = "https://test-org.surrogacyforce.com/webhooks/zapier/dfadbd66-074f-442e-9281-5c1e0a7b3d42"

describe("CopyField", () => {
    let writeText: MockInstance<(data: string) => Promise<void>>

    beforeEach(() => {
        writeText = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue(undefined)
    })

    afterEach(() => {
        writeText.mockRestore()
    })

    it("shows the value in a read-only monospace input with a named copy button", async () => {
        render(<CopyField value={WEBHOOK_URL} aria-label="Webhook URL" copyLabel="Copy webhook URL" />)

        const input = screen.getByRole("textbox", { name: "Webhook URL" })
        expect(input).toHaveValue(WEBHOOK_URL)
        expect(input).toHaveAttribute("readonly")
        expect(input).toHaveClass("font-mono", "text-ellipsis")
        // Mobile keeps the Input's 16px text so iOS does not zoom on focus.
        expect(input).toHaveClass("text-base", "md:text-sm")
        expect(input).not.toHaveClass("text-sm")

        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: "Copy webhook URL" }))
        })
        expect(writeText).toHaveBeenCalledWith(WEBHOOK_URL)
    })

    it("scrolls to the start of the value when the input receives focus", () => {
        render(<CopyField value={WEBHOOK_URL} aria-label="Webhook URL" copyLabel="Copy webhook URL" />)

        const input = screen.getByRole("textbox", { name: "Webhook URL" }) as HTMLInputElement
        input.setSelectionRange(WEBHOOK_URL.length, WEBHOOK_URL.length)
        input.scrollLeft = 120

        fireEvent.focus(input)

        expect(input.selectionStart).toBe(0)
        expect(input.selectionEnd).toBe(0)
        expect(input.scrollLeft).toBe(0)
    })

    it("pairs with a visible label through id", () => {
        render(
            <div>
                <label htmlFor="booking-link">Booking link</label>
                <CopyField id="booking-link" value={WEBHOOK_URL} copyLabel="Copy booking link" />
            </div>
        )

        expect(screen.getByRole("textbox", { name: "Booking link" })).toHaveValue(WEBHOOK_URL)
    })

    it("disables the copy button while the value is empty", () => {
        render(<CopyField value="" aria-label="Booking link" copyLabel="Copy booking link" />)

        expect(screen.getByRole("button", { name: "Copy booking link" })).toBeDisabled()
    })

    it("requires a name for the input", () => {
        // @ts-expect-error CopyField needs `id` (with a visible label) or `aria-label`.
        const unnamed = <CopyField value={WEBHOOK_URL} copyLabel="Copy webhook URL" />
        expect(unnamed).toBeTruthy()
    })
})
