"use client"

import { useEffect, useEffectEvent, type RefObject } from "react"

export function useTranscriptCommentInteractions({
    transcriptRef,
    isSelectingRef,
    setHoveredCommentId,
    setFocusedCommentId,
}: {
    transcriptRef: RefObject<HTMLElement | null>
    isSelectingRef: RefObject<boolean>
    setHoveredCommentId: (commentId: string | null) => void
    setFocusedCommentId: (commentId: string | null) => void
}) {
    const setHoveredCommentIdEvent = useEffectEvent(setHoveredCommentId)
    const setFocusedCommentIdEvent = useEffectEvent(setFocusedCommentId)

    useEffect(() => {
        const container = transcriptRef.current
        if (!container) return

        const findCommentId = (target: EventTarget | null) => {
            if (!(target instanceof HTMLElement)) return null
            return target.closest("[data-comment-id]")?.getAttribute("data-comment-id") ?? null
        }

        const focusCommentFromTarget = (target: EventTarget | null) => {
            const commentId = findCommentId(target)
            if (commentId) {
                setFocusedCommentIdEvent(commentId)
            }
        }

        const handleMouseOver = (event: MouseEvent) => {
            if (isSelectingRef.current) return
            const commentId = findCommentId(event.target)
            if (commentId) {
                setHoveredCommentIdEvent(commentId)
            }
        }

        const handleMouseOut = (event: MouseEvent) => {
            if (isSelectingRef.current) return
            if (!findCommentId(event.relatedTarget)) {
                setHoveredCommentIdEvent(null)
            }
        }

        const handleMouseLeave = () => {
            setHoveredCommentIdEvent(null)
        }

        const handleFocusIn = (event: FocusEvent) => {
            if (isSelectingRef.current) return
            const commentId = findCommentId(event.target)
            if (commentId) {
                setHoveredCommentIdEvent(commentId)
                setFocusedCommentIdEvent(commentId)
            }
        }

        const handleFocusOut = (event: FocusEvent) => {
            if (isSelectingRef.current) return
            if (!findCommentId(event.relatedTarget)) {
                setHoveredCommentIdEvent(null)
                setFocusedCommentIdEvent(null)
            }
        }

        const handleClick = (event: MouseEvent) => {
            if (isSelectingRef.current) return
            focusCommentFromTarget(event.target)
        }

        const handleKeyDown = (event: KeyboardEvent) => {
            if (isSelectingRef.current) return
            if (event.key !== "Enter" && event.key !== " ") return
            event.preventDefault()
            focusCommentFromTarget(event.target)
        }

        container.addEventListener("mouseover", handleMouseOver)
        container.addEventListener("mouseout", handleMouseOut)
        container.addEventListener("mouseleave", handleMouseLeave)
        container.addEventListener("focusin", handleFocusIn)
        container.addEventListener("focusout", handleFocusOut)
        container.addEventListener("click", handleClick)
        container.addEventListener("keydown", handleKeyDown)

        return () => {
            container.removeEventListener("mouseover", handleMouseOver)
            container.removeEventListener("mouseout", handleMouseOut)
            container.removeEventListener("mouseleave", handleMouseLeave)
            container.removeEventListener("focusin", handleFocusIn)
            container.removeEventListener("focusout", handleFocusOut)
            container.removeEventListener("click", handleClick)
            container.removeEventListener("keydown", handleKeyDown)
        }
    }, [isSelectingRef, transcriptRef])
}
