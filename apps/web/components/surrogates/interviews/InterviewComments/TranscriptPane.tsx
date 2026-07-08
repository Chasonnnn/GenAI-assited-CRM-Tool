"use client"

import { useEffect } from "react"
import { SafeHtmlContent } from "@/components/safe-html-content"
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

    useEffect(() => {
        const container = transcriptRef.current
        if (!container) return

        const focusCommentFromTarget = (target: HTMLElement | null) => {
            const commentSpan = target?.closest("[data-comment-id]")
            if (commentSpan) {
                const commentId = commentSpan.getAttribute("data-comment-id")
                setFocusedCommentId(commentId)
            }
        }

        const handleMouseOver = (event: MouseEvent) => {
            if (isSelectingRef.current) return
            const target = event.target instanceof HTMLElement ? event.target : null
            const commentSpan = target?.closest("[data-comment-id]")
            if (commentSpan) {
                setHoveredCommentId(commentSpan.getAttribute("data-comment-id"))
            }
        }

        const handleMouseOut = (event: MouseEvent) => {
            if (isSelectingRef.current) return
            const related = event.relatedTarget instanceof HTMLElement ? event.relatedTarget : null
            if (!related?.closest("[data-comment-id]")) {
                setHoveredCommentId(null)
            }
        }

        const handleMouseLeave = () => {
            setHoveredCommentId(null)
        }

        const handleFocusIn = (event: FocusEvent) => {
            if (isSelectingRef.current) return
            const target = event.target instanceof HTMLElement ? event.target : null
            const commentSpan = target?.closest("[data-comment-id]")
            if (commentSpan) {
                const commentId = commentSpan.getAttribute("data-comment-id")
                setHoveredCommentId(commentId)
                setFocusedCommentId(commentId)
            }
        }

        const handleFocusOut = (event: FocusEvent) => {
            if (isSelectingRef.current) return
            const related = event.relatedTarget instanceof HTMLElement ? event.relatedTarget : null
            if (!related?.closest("[data-comment-id]")) {
                setHoveredCommentId(null)
                setFocusedCommentId(null)
            }
        }

        const focusCommentFromClick = (event: MouseEvent) => {
            if (isSelectingRef.current) return
            const target = event.target instanceof HTMLElement ? event.target : null
            focusCommentFromTarget(target)
        }

        const handleKeyDown = (event: KeyboardEvent) => {
            if (isSelectingRef.current) return
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault()
                const target = event.target instanceof HTMLElement ? event.target : null
                focusCommentFromTarget(target)
            }
        }

        container.addEventListener("mouseover", handleMouseOver)
        container.addEventListener("mouseout", handleMouseOut)
        container.addEventListener("mouseleave", handleMouseLeave)
        container.addEventListener("focusin", handleFocusIn)
        container.addEventListener("focusout", handleFocusOut)
        container.addEventListener("click", focusCommentFromClick)
        container.addEventListener("keydown", handleKeyDown)

        return () => {
            container.removeEventListener("mouseover", handleMouseOver)
            container.removeEventListener("mouseout", handleMouseOut)
            container.removeEventListener("mouseleave", handleMouseLeave)
            container.removeEventListener("focusin", handleFocusIn)
            container.removeEventListener("focusout", handleFocusOut)
            container.removeEventListener("click", focusCommentFromClick)
            container.removeEventListener("keydown", handleKeyDown)
        }
    }, [isSelectingRef, setFocusedCommentId, setHoveredCommentId, transcriptRef])

    return (
        <>
            <section
                ref={transcriptRef}
                className={cn(
                    "p-4 prose prose-sm prose-stone dark:prose-invert max-w-none",
                    "selection:bg-teal-200 dark:selection:bg-teal-800",
                    className
                )}
                aria-label="Interview Transcript"
            >
                <SafeHtmlContent html={transcriptHtml} />
            </section>
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
