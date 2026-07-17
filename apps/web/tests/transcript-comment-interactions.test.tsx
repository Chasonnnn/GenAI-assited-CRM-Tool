import { renderHook } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { useTranscriptCommentInteractions } from "@/lib/hooks/use-transcript-comment-interactions"

describe("useTranscriptCommentInteractions", () => {
    it("delegates hover and focus interactions, respects selection mode, and cleans up", () => {
        const container = document.createElement("section")
        const comment = document.createElement("span")
        comment.dataset.commentId = "comment-1"
        const child = document.createElement("strong")
        comment.append(child)
        container.append(comment)

        const transcriptRef = { current: container }
        const isSelectingRef = { current: false }
        const setHoveredCommentId = vi.fn()
        const setFocusedCommentId = vi.fn()
        const view = renderHook(() =>
            useTranscriptCommentInteractions({
                transcriptRef,
                isSelectingRef,
                setHoveredCommentId,
                setFocusedCommentId,
            })
        )

        child.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }))
        expect(setHoveredCommentId).toHaveBeenLastCalledWith("comment-1")

        child.dispatchEvent(new MouseEvent("click", { bubbles: true }))
        expect(setFocusedCommentId).toHaveBeenLastCalledWith("comment-1")

        const keyboardFocus = new KeyboardEvent("keydown", {
            bubbles: true,
            cancelable: true,
            key: "Enter",
        })
        child.dispatchEvent(keyboardFocus)
        expect(keyboardFocus.defaultPrevented).toBe(true)
        expect(setFocusedCommentId).toHaveBeenLastCalledWith("comment-1")

        isSelectingRef.current = true
        setHoveredCommentId.mockClear()
        child.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }))
        expect(setHoveredCommentId).not.toHaveBeenCalled()

        view.unmount()
        isSelectingRef.current = false
        child.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }))
        expect(setHoveredCommentId).not.toHaveBeenCalled()
    })
})
