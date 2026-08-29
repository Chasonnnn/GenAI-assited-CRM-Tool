import * as React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mockUseAIContext = vi.fn()
const mockClosePanel = vi.fn()

vi.mock("@/lib/context/ai-context", () => ({
    useAIContext: () => mockUseAIContext(),
}))

vi.mock("@/components/ai/AIChatPanel", () => ({
    AIChatPanel: ({ onClose }: { onClose?: () => void }) => (
        <div className="flex h-full flex-col">
            <textarea aria-label="Message AI Assistant" />
            <button type="button" onClick={onClose} aria-label="Close AI Assistant">
                Close
            </button>
        </div>
    ),
}))

import { AIChatDrawer } from "@/components/ai/AIChatDrawer"

function DrawerHarness() {
    const [isOpen, setIsOpen] = React.useState(false)
    const closePanel = () => {
        mockClosePanel()
        setIsOpen(false)
    }

    mockUseAIContext.mockReturnValue({
        isOpen,
        closePanel,
        entityType: "surrogate",
        entityId: "sur-1",
        entityName: "Surrogate S10001",
        canUseAI: true,
    })

    return (
        <>
            <button type="button" onClick={() => setIsOpen(true)}>
                Open AI Assistant
            </button>
            <AIChatDrawer />
        </>
    )
}

describe("AIChatDrawer", () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it("opens a named non-modal dialog and restores focus after Escape", async () => {
        render(<DrawerHarness />)

        const launcher = screen.getByRole("button", { name: "Open AI Assistant" })
        launcher.focus()
        fireEvent.click(launcher)

        const dialog = await screen.findByRole("dialog", { name: "AI Assistant" })
        expect(dialog).not.toHaveAttribute("aria-modal", "true")
        expect(dialog).toHaveClass("w-full!", "max-w-none!", "md:w-[400px]!")
        await waitFor(() => {
            expect(
                screen.getByRole("textbox", { name: "Message AI Assistant" })
            ).toHaveFocus()
        })

        fireEvent.keyDown(document, { key: "Escape" })

        await waitFor(() => {
            expect(mockClosePanel).toHaveBeenCalledTimes(1)
            expect(screen.queryByRole("dialog", { name: "AI Assistant" })).not.toBeInTheDocument()
            expect(launcher).toHaveFocus()
        })
    })

    it("restores focus after the panel close control is used", async () => {
        render(<DrawerHarness />)

        const launcher = screen.getByRole("button", { name: "Open AI Assistant" })
        launcher.focus()
        fireEvent.click(launcher)

        await screen.findByRole("dialog", { name: "AI Assistant" })
        fireEvent.click(screen.getByRole("button", { name: "Close AI Assistant" }))

        await waitFor(() => {
            expect(screen.queryByRole("dialog", { name: "AI Assistant" })).not.toBeInTheDocument()
            expect(launcher).toHaveFocus()
        })
    })

})
