import * as React from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

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

vi.mock('@/lib/hooks/use-ai', () => ({
    useConversation: () => mockUseConversation(),
    useStreamChatMessage: () => mockStreamMessage,
    useApproveAction: () => ({ mutate: mockApproveAction, isPending: false }),
    useRejectAction: () => ({ mutate: mockRejectAction, isPending: false }),
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
    })

    afterEach(() => {
        vi.unstubAllGlobals()
    })

    it('renders with accessible close button when onClose is provided', () => {
        const onClose = vi.fn()
        render(<AIChatPanel onClose={onClose} />)

        const closeButton = screen.getByRole('button', { name: /close ai assistant/i })
        expect(closeButton).toBeInTheDocument()

        fireEvent.click(closeButton)
        expect(onClose).toHaveBeenCalled()
    })

    it('does not render close button when onClose is not provided', () => {
        render(<AIChatPanel />)
        const closeButton = screen.queryByRole('button', { name: /close ai assistant/i })
        expect(closeButton).not.toBeInTheDocument()
    })

    it('renders accessible action buttons when actions are proposed', () => {
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
                                action_type: 'add_note',
                                action_data: { content: 'test note' }
                            }
                        ]
                    }
                ]
            },
            isLoading: false
        })

        render(<AIChatPanel />)

        const approveButton = screen.getByRole('button', { name: /approve action/i })
        const rejectButton = screen.getByRole('button', { name: /reject action/i })

        expect(approveButton).toBeInTheDocument()
        expect(rejectButton).toBeInTheDocument()

        fireEvent.click(approveButton)
        expect(mockApproveAction).toHaveBeenCalledWith('action1')

        fireEvent.click(rejectButton)
        expect(mockRejectAction).toHaveBeenCalledWith('action1')
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
