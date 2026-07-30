import * as React from "react"
import { readFileSync } from "node:fs"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"

type DynamicComponent = React.ComponentType<Record<string, unknown>>
type DynamicModule = DynamicComponent | { default: DynamicComponent }

const resolveDynamicModule = (mod: DynamicModule): DynamicComponent => {
    if (typeof mod === "function") {
        return mod
    }
    return mod.default
}

vi.mock("next/dynamic", () => ({
    __esModule: true,
    default: (loader: () => Promise<DynamicModule>) => {
        return function DynamicComponentWrapper(props: Record<string, unknown>) {
            const [Component, setComponent] = React.useState<DynamicComponent | null>(null)

            React.useEffect(() => {
                let mounted = true
                loader().then((mod) => {
                    const Resolved = resolveDynamicModule(mod)
                    if (mounted) {
                        setComponent(() => Resolved)
                    }
                })
                return () => {
                    mounted = false
                }
            }, [])

            if (!Component) return null
            return <Component {...props} />
        }
    },
}))

// Mocks
const mockStreamMessage = vi.fn()
const mockApproveAction = vi.fn()
const mockRejectAction = vi.fn()
const mockUseConversation = vi.fn()
const mockUseApproveAction = vi.fn()
const mockUseRejectAction = vi.fn()
const mockUsePipelines = vi.fn()

vi.mock('@/lib/hooks/use-ai', () => ({
    useConversation: () => mockUseConversation(),
    useStreamChatMessage: () => mockStreamMessage,
    useApproveAction: () => mockUseApproveAction(),
    useRejectAction: () => mockUseRejectAction(),
}))

vi.mock('@/lib/hooks/use-pipelines', () => ({
    usePipelines: (...args: unknown[]) => mockUsePipelines(...args),
}))

// Mock ScheduleParserDialog to avoid deep rendering issues
vi.mock('@/components/ai/ScheduleParserDialog', () => ({
    ScheduleParserDialog: () => <div data-testid="schedule-parser-dialog">Dialog</div>
}))

import { AIChatPanel } from "../components/ai/AIChatPanel"

const createConversationMessage = (id: string, content: string) => ({
    id,
    role: "assistant" as const,
    content,
    status: "done" as const,
})

function mockScrollContainer(
    element: Element,
    { clientHeight, scrollHeight, scrollTop }: { clientHeight: number; scrollHeight: number; scrollTop: number }
) {
    let currentScrollTop = scrollTop

    Object.defineProperty(element, "clientHeight", {
        configurable: true,
        value: clientHeight,
    })
    Object.defineProperty(element, "scrollHeight", {
        configurable: true,
        value: scrollHeight,
    })
    Object.defineProperty(element, "scrollTop", {
        configurable: true,
        get: () => currentScrollTop,
        set: (value: number) => {
            currentScrollTop = value
        },
    })

    return {
        getScrollTop: () => currentScrollTop,
    }
}

describe('AIChatPanel', () => {
    beforeEach(() => {
        vi.clearAllMocks()

        // Default mock implementation
        mockUseConversation.mockReturnValue({
            data: { messages: [] },
            isLoading: false
        })
        mockUseApproveAction.mockReturnValue({
            mutate: mockApproveAction,
            isPending: false,
            variables: undefined,
            error: null,
        })
        mockUseRejectAction.mockReturnValue({
            mutate: mockRejectAction,
            isPending: false,
            variables: undefined,
            error: null,
        })
        mockUsePipelines.mockReturnValue({ data: [] })
    })

    afterEach(() => {
        vi.unstubAllGlobals()
    })

    it('renders with accessible close button when onClose is provided', () => {
        const onClose = vi.fn()
        render(<AIChatPanel onClose={onClose} />)

        const closeButton = screen.getByRole('button', { name: /close ai assistant/i })
        expect(closeButton).toBeInTheDocument()
        expect(closeButton.querySelector("svg")).toHaveAttribute("aria-hidden", "true")

        fireEvent.click(closeButton)
        expect(onClose).toHaveBeenCalled()
    })

    it("marks the close icon explicitly decorative in source", () => {
        const source = readFileSync("components/ai/AIChatPanel.tsx", "utf8")

        expect(source).toContain('<XIcon className="size-4" aria-hidden="true" />')
    })

    it('does not render close button when onClose is not provided', () => {
        render(<AIChatPanel />)
        const closeButton = screen.queryByRole('button', { name: /close ai assistant/i })
        expect(closeButton).not.toBeInTheDocument()
    })

    it("keeps task context and suggested prompts task-specific", () => {
        render(
            <AIChatPanel
                entityType="task"
                entityId="task-1"
                entityName="Confirm OB appointment"
            />
        )

        expect(screen.getByText("Task • Confirm OB appointment")).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: /summarize task/i }))

        expect(screen.getByRole("textbox", { name: "Message AI Assistant" })).toHaveValue("Summarize this task")
        expect(screen.queryByRole("button", { name: /parse schedule/i })).not.toBeInTheDocument()
    })

    it("shows compact record identity and a friendly status label when provided", () => {
        render(
            <AIChatPanel
                entityType="surrogate"
                entityId="sur-1"
                entityName="Surrogate #S10546 - QA Embryo Stage"
                entityContextLabel="Surrogate S10546"
                entityStatusLabel="Heartbeat confirmed"
            />
        )

        expect(screen.getByText("Surrogate S10546")).toBeInTheDocument()
        expect(screen.getByText("Heartbeat confirmed")).toBeInTheDocument()
        expect(screen.queryByText("Surrogate • Surrogate #S10546 - QA Embryo Stage")).not.toBeInTheDocument()
    })

    it("supports multiline drafting and sends only on Enter without Shift", async () => {
        render(
            <AIChatPanel
                entityType="surrogate"
                entityId="sur-1"
                entityName="Surrogate S10001"
            />
        )

        const composer = screen.getByRole("textbox", { name: "Message AI Assistant" })
        expect(composer.tagName).toBe("TEXTAREA")

        fireEvent.change(composer, { target: { value: "First line\nSecond line" } })
        fireEvent.keyDown(composer, { key: "Enter", shiftKey: true })

        expect(mockStreamMessage).not.toHaveBeenCalled()

        fireEvent.keyDown(composer, { key: "Enter" })

        await waitFor(() => {
            expect(mockStreamMessage).toHaveBeenCalled()
        })
        expect(mockStreamMessage.mock.calls[0]?.[0]).toEqual({
            message: "First line\nSecond line",
            entity_type: "surrogate",
            entity_id: "sur-1",
        })
    })

    it("does not let a stopped response clear a newer active response", async () => {
        let rejectFirstStream: (reason?: unknown) => void = () => undefined
        let resolveSecondStream: () => void = () => undefined
        const firstStream = new Promise<void>((_resolve, reject) => {
            rejectFirstStream = reject
        })
        const secondStream = new Promise<void>((resolve) => {
            resolveSecondStream = resolve
        })

        mockStreamMessage
            .mockImplementationOnce(() => firstStream)
            .mockImplementationOnce(() => secondStream)

        render(<AIChatPanel />)

        const composer = screen.getByRole("textbox", { name: "Message AI Assistant" })
        fireEvent.change(composer, { target: { value: "First request" } })
        fireEvent.click(screen.getByRole("button", { name: "Send message" }))
        expect(await screen.findByRole("button", { name: "Stop generating" })).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Stop generating" }))
        await waitFor(() => expect(composer).not.toBeDisabled())

        fireEvent.change(composer, { target: { value: "Second request" } })
        fireEvent.click(screen.getByRole("button", { name: "Send message" }))
        await waitFor(() => expect(mockStreamMessage).toHaveBeenCalledTimes(2))
        expect(screen.getByRole("button", { name: "Stop generating" })).toBeInTheDocument()

        await act(async () => {
            rejectFirstStream(new DOMException("Aborted", "AbortError"))
        })

        expect(screen.getByRole("button", { name: "Stop generating" })).toBeInTheDocument()

        await act(async () => {
            resolveSecondStream()
        })
    })

    it("clears an unsent draft when the conversation context changes", () => {
        const { rerender } = render(
            <AIChatPanel entityType="surrogate" entityId="sur-1" entityName="Jordan Example" />
        )
        const composer = screen.getByRole("textbox", { name: "Message AI Assistant" })

        fireEvent.change(composer, { target: { value: "Draft for Jordan" } })
        expect(composer).toHaveValue("Draft for Jordan")

        rerender(
            <AIChatPanel entityType="surrogate" entityId="sur-2" entityName="Taylor Example" />
        )

        expect(screen.getByRole("textbox", { name: "Message AI Assistant" })).toHaveValue("")
    })

    it("requires an explicit review before a proposed email can be approved", () => {
        mockUseConversation.mockReturnValue({
            data: {
                messages: [
                    {
                        id: 'msg1',
                        role: 'assistant',
                        content: 'Here is a proposal',
                        status: 'done',
                        proposed_actions: [
                            {
                                approval_id: 'action1',
                                action_type: 'send_email',
                                action_data: {
                                    to: "jordan@example.com",
                                    subject: "Confirming your OB appointment",
                                    body: "Hi Jordan, please confirm the appointment details.",
                                }
                            }
                        ]
                    }
                ]
            },
            isLoading: false
        })

        render(<AIChatPanel />)

        expect(screen.getByRole("article", { name: "Draft follow-up email" })).toBeInTheDocument()
        expect(screen.getByText("Human review required")).toBeInTheDocument()
        expect(screen.getByText("Needs review")).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Approve and send" })).not.toBeInTheDocument()

        const reviewButton = screen.getByRole("button", { name: "Review draft" })
        fireEvent.click(reviewButton)

        expect(reviewButton).toHaveAttribute("aria-expanded", "true")
        expect(screen.getByText("Hi Jordan, please confirm the appointment details.")).toBeInTheDocument()
        expect(mockApproveAction).not.toHaveBeenCalled()

        fireEvent.click(screen.getByRole("button", { name: "Approve and send" }))
        expect(mockApproveAction).toHaveBeenCalledWith("action1")

        fireEvent.click(screen.getByRole("button", { name: "Dismiss" }))
        expect(mockRejectAction).toHaveBeenCalledWith("action1")
    })

    it("shows the target stage label before approving a status change", () => {
        mockUsePipelines.mockReturnValue({
            data: [
                {
                    id: "pipeline-1",
                    stages: [
                        {
                            id: "stage-qualified",
                            label: "Qualified for matching",
                        },
                    ],
                },
            ],
        })
        mockUseConversation.mockReturnValue({
            data: {
                messages: [
                    {
                        id: "msg-stage",
                        role: "assistant",
                        content: "I can update this surrogate.",
                        status: "done",
                        proposed_actions: [
                            {
                                approval_id: "action-stage",
                                action_type: "update_status",
                                action_data: { stage_id: "stage-qualified" },
                            },
                        ],
                    },
                ],
            },
            isLoading: false,
        })

        render(<AIChatPanel entityType="surrogate" entityId="sur-1" />)

        const proposal = screen.getByRole("article", { name: "Update stage" })
        expect(proposal).toHaveTextContent("Change to Qualified for matching")
        expect(proposal).not.toHaveTextContent("Selected pipeline stage")
        expect(screen.queryByRole("button", { name: "Approve and update" })).not.toBeInTheDocument()
    })

    it("shows a friendly inline error for an action that could not execute", () => {
        mockUseConversation.mockReturnValue({
            data: {
                messages: [
                    {
                        id: "msg1",
                        role: "assistant",
                        content: "Here is a proposal",
                        proposed_actions: [
                            {
                                approval_id: "action1",
                                action_type: "send_email",
                                action_data: {
                                    to: "jordan@example.com",
                                    subject: "Follow-up",
                                    body: "Hi Jordan",
                                },
                            },
                        ],
                    },
                ],
            },
            isLoading: false,
        })
        mockUseApproveAction.mockReturnValue({
            mutate: mockApproveAction,
            isPending: false,
            variables: "action1",
            error: new Error("Permission denied"),
        })

        render(<AIChatPanel />)

        expect(screen.getByRole("alert")).toHaveTextContent(
            "This action couldn’t be completed. Review it and try again."
        )
        expect(screen.queryByText("Permission denied")).not.toBeInTheDocument()
    })

    it("renders assistant Markdown as rich text instead of raw syntax", () => {
        mockUseConversation.mockReturnValue({
            data: {
                messages: [
                    createConversationMessage(
                        "m1",
                        [
                            "Based on the last 90 days, conversion is **0.5%**.",
                            "",
                            "### 1. Address the Unassigned Bottleneck",
                            "* **The Data:** Only 6 leads have been contacted.",
                            "* **Suggestion:** Start a bulk assignment session.",
                        ].join("\n"),
                    ),
                ],
            },
            isLoading: false,
        })

        const { container } = render(<AIChatPanel />)

        expect(screen.getByText("0.5%", { selector: "strong" })).toBeInTheDocument()
        expect(screen.getByRole("heading", { level: 3, name: "1. Address the Unassigned Bottleneck" })).toBeInTheDocument()
        expect(screen.getByText("The Data:", { selector: "strong" })).toBeInTheDocument()
        expect(container.querySelector("ul")).toBeInTheDocument()
        expect(container).not.toHaveTextContent(/\*\*0\.5%\*\*/)
        expect(container).not.toHaveTextContent("### 1. Address the Unassigned Bottleneck")
    })

    it("exposes conversation updates through a polite live log", () => {
        mockUseConversation.mockReturnValue({
            data: {
                messages: [createConversationMessage("m1", "Current record summary")],
            },
            isLoading: false,
        })

        render(<AIChatPanel />)

        const conversationLog = screen.getByRole("log", { name: "AI Assistant conversation" })
        expect(conversationLog).toHaveAttribute("aria-live", "polite")
        expect(conversationLog).toHaveAttribute("aria-relevant", "additions")
        expect(conversationLog).toHaveTextContent("Current record summary")
    })

    it("keeps conversation typography compact inside the narrow drawer", () => {
        mockUseConversation.mockReturnValue({
            data: {
                messages: [
                    {
                        id: "m-user",
                        role: "user",
                        content: "Compact user message",
                    },
                    createConversationMessage("m-assistant", "Compact assistant message"),
                ],
            },
            isLoading: false,
        })

        render(<AIChatPanel />)

        expect(screen.getByText("Compact user message")).toHaveClass("text-xs")
        expect(screen.getByText("Compact assistant message").closest("div")).toHaveClass(
            "text-xs"
        )
    })

    it("shows a retryable error when conversation history cannot load", () => {
        const refetch = vi.fn()
        mockUseConversation.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            error: new Error("Network unavailable"),
            refetch,
        })

        render(<AIChatPanel />)

        expect(screen.getByRole("alert")).toHaveTextContent("Couldn’t load this conversation")
        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(refetch).toHaveBeenCalledTimes(1)
    })

    it("keeps the chat pinned to the latest message when already near the bottom", async () => {
        const requestAnimationFrame = vi.fn((callback: FrameRequestCallback) => {
            callback(0)
            return 1
        })

        vi.stubGlobal("requestAnimationFrame", requestAnimationFrame)
        vi.stubGlobal("cancelAnimationFrame", vi.fn())

        const { container, rerender } = render(<AIChatPanel />)
        const scrollContainer = container.querySelector(".overflow-y-auto")
        expect(scrollContainer).not.toBeNull()

        const metrics = mockScrollContainer(scrollContainer!, {
            clientHeight: 200,
            scrollHeight: 800,
            scrollTop: 560,
        })

        requestAnimationFrame.mockClear()

        mockUseConversation.mockReturnValue({
            data: {
                messages: [
                    createConversationMessage("m1", "First update"),
                    createConversationMessage("m2", "Second update"),
                ],
            },
            isLoading: false,
        })

        rerender(<AIChatPanel />)

        await waitFor(() => {
            expect(metrics.getScrollTop()).toBe(800)
        })
        expect(requestAnimationFrame).toHaveBeenCalled()
    })

    it("does not force-scroll when the user has moved away from the latest messages", async () => {
        const requestAnimationFrame = vi.fn((callback: FrameRequestCallback) => {
            callback(0)
            return 1
        })

        vi.stubGlobal("requestAnimationFrame", requestAnimationFrame)
        vi.stubGlobal("cancelAnimationFrame", vi.fn())

        const { container, rerender } = render(<AIChatPanel />)
        const scrollContainer = container.querySelector(".overflow-y-auto")
        expect(scrollContainer).not.toBeNull()

        const metrics = mockScrollContainer(scrollContainer!, {
            clientHeight: 200,
            scrollHeight: 800,
            scrollTop: 120,
        })

        fireEvent.scroll(scrollContainer!)
        requestAnimationFrame.mockClear()

        mockUseConversation.mockReturnValue({
            data: {
                messages: [
                    createConversationMessage("m1", "Earlier update"),
                    createConversationMessage("m2", "Latest update"),
                ],
            },
            isLoading: false,
        })

        rerender(<AIChatPanel />)

        await screen.findByText("Latest update")
        expect(metrics.getScrollTop()).toBe(120)
        expect(requestAnimationFrame).not.toHaveBeenCalled()
    })

    it("loads the schedule parser on demand for surrogate conversations", async () => {
        render(
            <AIChatPanel
                entityType="surrogate"
                entityId="sur-1"
                entityName="Jordan Example"
            />
        )

        fireEvent.click(screen.getByRole("button", { name: /parse schedule/i }))

        expect(await screen.findByTestId("schedule-parser-dialog")).toBeInTheDocument()
    })
})
