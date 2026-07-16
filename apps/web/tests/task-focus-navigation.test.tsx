import { renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useTaskFocusNavigation } from "@/lib/hooks/use-task-focus-navigation"

const mockSetItem = vi.fn()

describe("useTaskFocusNavigation", () => {
    beforeEach(() => {
        document.body.innerHTML = '<section id="tasks-list"></section>'
        Object.defineProperty(Element.prototype, "scrollIntoView", {
            configurable: true,
            value: vi.fn(),
        })
        mockSetItem.mockReset()
        Object.defineProperty(window, "localStorage", {
            configurable: true,
            value: {
                clear: vi.fn(),
                getItem: vi.fn(),
                key: vi.fn(),
                length: 0,
                removeItem: vi.fn(),
                setItem: mockSetItem,
            },
        })
    })

    it("focuses a repeated task deep link again after the focus parameter clears", () => {
        const { rerender } = renderHook(
            ({ focusTarget }: { focusTarget: "tasks" | null }) =>
                useTaskFocusNavigation({
                    focusTarget,
                    activeView: "list",
                    isLoading: false,
                    loadingApprovals: false,
                    loadingStatusRequests: false,
                    loadingImportApprovals: false,
                }),
            {
                initialProps: { focusTarget: "tasks" as const | null },
            },
        )

        expect(Element.prototype.scrollIntoView).toHaveBeenCalledTimes(1)

        rerender({ focusTarget: "tasks" })
        expect(Element.prototype.scrollIntoView).toHaveBeenCalledTimes(1)

        rerender({ focusTarget: null })
        rerender({ focusTarget: "tasks" })

        expect(Element.prototype.scrollIntoView).toHaveBeenCalledTimes(2)
        expect(mockSetItem).toHaveBeenLastCalledWith("tasks-view", "list")
    })
})
