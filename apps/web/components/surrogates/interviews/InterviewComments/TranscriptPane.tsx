"use client"

import { SafeHtmlContent } from "@/components/safe-html-content"
import { cn } from "@/lib/utils"
import { SelectionPopover } from "../SelectionPopover"
import { useInterviewComments } from "./context"
import { useInteractionClasses } from "./hooks/useInteractionClasses"
import { useTranscriptCommentInteractions } from "@/lib/hooks/use-transcript-comment-interactions"

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

    useTranscriptCommentInteractions({
        transcriptRef,
        isSelectingRef,
        setHoveredCommentId,
        setFocusedCommentId,
    })

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
