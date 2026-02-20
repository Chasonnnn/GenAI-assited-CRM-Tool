"use client"

import { useCallback } from "react"
import { cn } from "@/lib/utils"
import { SelectionPopover } from "../SelectionPopover"
import { useInterviewComments } from "./context"
import { useInteractionClasses } from "./hooks/useInteractionClasses"

interface TranscriptPaneProps {
    className?: string
}

export function TranscriptPane({ className }: TranscriptPaneProps) {
    const {
        transcriptRef,
        transcriptHtml,
        canEdit,
        newComment,
        isSelectingRef,
        interaction,
        setHoveredCommentId,
        setFocusedCommentId,
        startPendingComment,
    } = useInterviewComments()

    // Set up DOM class toggling for hover/focus states
    useInteractionClasses(transcriptRef, interaction)

    // Handle hover on transcript highlights (event delegation)
    const handleMouseOver = useCallback((e: React.MouseEvent) => {
        if (isSelectingRef.current) return
        const target = e.target instanceof HTMLElement ? e.target : null
        const commentSpan = target?.closest("[data-comment-id]")
        if (commentSpan) {
            setHoveredCommentId(commentSpan.getAttribute("data-comment-id"))
        }
    }, [isSelectingRef, setHoveredCommentId])

    const handleMouseOut = useCallback((e: React.MouseEvent) => {
        if (isSelectingRef.current) return
        const related = e.relatedTarget instanceof HTMLElement ? e.relatedTarget : null
        if (!related?.closest("[data-comment-id]")) {
            setHoveredCommentId(null)
        }
    }, [isSelectingRef, setHoveredCommentId])

    const handleMouseLeave = useCallback(() => {
        setHoveredCommentId(null)
    }, [setHoveredCommentId])

    const focusCommentFromTarget = useCallback((target: HTMLElement | null) => {
        const commentSpan = target?.closest("[data-comment-id]")
        if (commentSpan) {
            const commentId = commentSpan.getAttribute("data-comment-id")
            setFocusedCommentId(commentId)
        }
    }, [setFocusedCommentId])

    // Handle click on transcript highlights
    const handleClick = useCallback((e: React.MouseEvent) => {
        if (isSelectingRef.current) return
        const target = e.target instanceof HTMLElement ? e.target : null
        focusCommentFromTarget(target)
    }, [focusCommentFromTarget, isSelectingRef])

    return (
        <>
            <div
                ref={transcriptRef}
                className={cn(
                    "p-4 prose prose-sm prose-stone dark:prose-invert max-w-none",
                    "selection:bg-teal-200 dark:selection:bg-teal-800",
                    className
                )}
                onMouseOver={handleMouseOver}
                onMouseOut={handleMouseOut}
                onMouseLeave={handleMouseLeave}
                onClick={handleClick}
                onKeyDown={(e) => {
                    if (isSelectingRef.current) return
                    if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault()
                        const target = e.target instanceof HTMLElement ? e.target : null
                        focusCommentFromTarget(target)
                    }
                }}
                role="button"
                tabIndex={0}
                dangerouslySetInnerHTML={{ __html: transcriptHtml }}
            />
            <SelectionPopover
                containerRef={transcriptRef}
                onAddComment={startPendingComment}
                disabled={!canEdit || newComment.type === "pending"}
                onSelectionStateChange={(active) => {
                    isSelectingRef.current = active
                    if (active) {
                        setHoveredCommentId(null)
                    }
                }}
            />
        </>
    )
}
