import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

vi.unmock("@/lib/context/ai-context")

let mockPathname = "/surrogates/surrogate-1"

vi.mock("next/navigation", () => ({
    usePathname: () => mockPathname,
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({
        user: {
            user_id: "user-1",
            ai_enabled: true,
        },
    }),
}))

vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: () => ({
        data: {
            permissions: ["use_ai_assistant"],
        },
    }),
}))

import { AIContextProvider, useAIContext } from "@/lib/context/ai-context"

function AIContextProbe() {
    const context = useAIContext()

    return (
        <div>
            <output aria-label="entity type">{context.entityType ?? "none"}</output>
            <output aria-label="entity id">{context.entityId ?? "none"}</output>
            <output aria-label="entity name">{context.entityName ?? "none"}</output>
            <output aria-label="panel state">{context.isOpen ? "open" : "closed"}</output>
            <output aria-label="ai access">{context.canUseAI ? "allowed" : "blocked"}</output>
            <button
                type="button"
                onClick={() =>
                    context.setContext({
                        entityType: "surrogate",
                        entityId: "surrogate-1",
                        entityName: "Jane Candidate",
                    })
                }
            >
                Set context
            </button>
            <button type="button" onClick={context.clearContext}>
                Clear context
            </button>
        </div>
    )
}

function renderAIContextProbe() {
    return render(
        <AIContextProvider>
            <AIContextProbe />
        </AIContextProvider>
    )
}

describe("AIContextProvider", () => {
    beforeEach(() => {
        mockPathname = "/surrogates/surrogate-1"
    })

    it("sets and clears entity context through the public hook API", () => {
        renderAIContextProbe()

        fireEvent.click(screen.getByRole("button", { name: "Set context" }))

        expect(screen.getByLabelText("entity type")).toHaveTextContent("surrogate")
        expect(screen.getByLabelText("entity id")).toHaveTextContent("surrogate-1")
        expect(screen.getByLabelText("entity name")).toHaveTextContent("Jane Candidate")

        fireEvent.click(screen.getByRole("button", { name: "Clear context" }))

        expect(screen.getByLabelText("entity type")).toHaveTextContent("none")
        expect(screen.getByLabelText("entity id")).toHaveTextContent("none")
        expect(screen.getByLabelText("entity name")).toHaveTextContent("none")
    })

    it("clears entity context when navigation leaves entity pages", async () => {
        const { rerender } = renderAIContextProbe()

        fireEvent.click(screen.getByRole("button", { name: "Set context" }))
        expect(screen.getByLabelText("entity name")).toHaveTextContent("Jane Candidate")

        mockPathname = "/dashboard"
        rerender(
            <AIContextProvider>
                <AIContextProbe />
            </AIContextProvider>
        )

        await waitFor(() => {
            expect(screen.getByLabelText("entity type")).toHaveTextContent("none")
            expect(screen.getByLabelText("entity id")).toHaveTextContent("none")
            expect(screen.getByLabelText("entity name")).toHaveTextContent("none")
        })
    })

    it("toggles the assistant panel with the keyboard shortcut when AI is available", () => {
        renderAIContextProbe()

        expect(screen.getByLabelText("ai access")).toHaveTextContent("allowed")
        expect(screen.getByLabelText("panel state")).toHaveTextContent("closed")

        fireEvent.keyDown(window, {
            key: "a",
            metaKey: true,
            shiftKey: true,
        })

        expect(screen.getByLabelText("panel state")).toHaveTextContent("open")
    })
})
