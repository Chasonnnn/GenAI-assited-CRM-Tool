import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { useState } from "react"
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

import {
    AIContextProvider,
    useAIContext,
    useSetAIContext,
} from "@/lib/context/ai-context"

const DECLARATIVE_CONTEXT = {
    entityType: "surrogate" as const,
    entityId: "surrogate-declarative",
    entityName: "Declarative Candidate",
}

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
            <button
                type="button"
                onClick={() =>
                    context.setContext({
                        entityType: "task",
                        entityId: "task-1",
                        entityName: "Follow up with surrogate",
                    })
                }
            >
                Set task context
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

function DeclarativeAIContextProbe() {
    useSetAIContext(DECLARATIVE_CONTEXT)
    const context = useAIContext()

    return <output aria-label="declarative entity">{context.entityName ?? "none"}</output>
}

function DeclarativeAIContextRegistration() {
    useSetAIContext(DECLARATIVE_CONTEXT)
    return null
}

function DeclarativeAIContextLifecycleProbe() {
    const [registered, setRegistered] = useState(true)
    const context = useAIContext()

    return (
        <>
            {registered ? <DeclarativeAIContextRegistration /> : null}
            <output aria-label="registered entity">{context.entityName ?? "none"}</output>
            <button type="button" onClick={() => setRegistered(false)}>
                Remove registration
            </button>
        </>
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

    it("sets declarative entity context without a provider render loop", async () => {
        render(
            <AIContextProvider>
                <DeclarativeAIContextProbe />
            </AIContextProvider>,
        )

        expect(await screen.findByLabelText("declarative entity")).toHaveTextContent(
            "Declarative Candidate",
        )
    })

    it("clears declarative entity context when its registration unmounts", async () => {
        render(
            <AIContextProvider>
                <DeclarativeAIContextLifecycleProbe />
            </AIContextProvider>,
        )

        expect(await screen.findByLabelText("registered entity")).toHaveTextContent(
            "Declarative Candidate",
        )
        fireEvent.click(screen.getByRole("button", { name: "Remove registration" }))

        await waitFor(() => {
            expect(screen.getByLabelText("registered entity")).toHaveTextContent("none")
        })
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

    it("keeps task context available while the user is on the tasks page", () => {
        mockPathname = "/tasks"
        renderAIContextProbe()

        fireEvent.click(screen.getByRole("button", { name: "Set task context" }))

        expect(screen.getByLabelText("entity type")).toHaveTextContent("task")
        expect(screen.getByLabelText("entity id")).toHaveTextContent("task-1")
        expect(screen.getByLabelText("entity name")).toHaveTextContent("Follow up with surrogate")
    })

    it("clears a non-task entity context when navigation enters the tasks page", async () => {
        const { rerender } = renderAIContextProbe()

        fireEvent.click(screen.getByRole("button", { name: "Set context" }))
        expect(screen.getByLabelText("entity type")).toHaveTextContent("surrogate")

        mockPathname = "/tasks"
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

    it("clears task context when navigation leaves the tasks page", async () => {
        mockPathname = "/tasks"
        const { rerender } = renderAIContextProbe()

        fireEvent.click(screen.getByRole("button", { name: "Set task context" }))
        expect(screen.getByLabelText("entity type")).toHaveTextContent("task")

        mockPathname = "/surrogates/surrogate-1"
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
