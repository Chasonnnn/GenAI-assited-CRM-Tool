"use client"

import { useInterviewComments } from "./context"
import { getMinSidebarHeight } from "./comment-layout"
import { useObservedScrollHeight } from "@/lib/hooks/use-observed-scroll-height"

export function ConnectorLines() {
    const {
        commentPositions,
        layoutMinHeight,
        activeNoteId,
        newComment,
        transcriptRef,
    } = useInterviewComments()
    const connectorVisible = Boolean(activeNoteId || newComment.type === "pending")
    const transcriptHeight = useObservedScrollHeight(transcriptRef, connectorVisible)

    // Only render when there's an active note or pending comment
    if (!connectorVisible) {
        return null
    }

    const pendingCommentId = newComment.type === "pending" ? newComment.commentId : null
    const connectorPaths = []

    for (const pos of commentPositions) {
        if (pos.noteId !== activeNoteId && pos.noteId !== pendingCommentId) continue

        const startY = pos.anchorTop + 12
        const endY = pos.top + 16
        const startX = pos.anchorLeft
        const endX = pos.cardLeft
        const midX = startX + (endX - startX) / 2
        if (!startX || !endX) continue

        connectorPaths.push(
            <path
                key={pos.noteId}
                d={`M ${startX},${startY} C ${midX},${startY} ${midX},${endY} ${endX},${endY}`}
                stroke="currentColor"
                className="text-stone-300 dark:text-stone-600"
                strokeWidth="1.5"
                fill="none"
            />
        )
    }

    return (
        <svg
            className="absolute inset-0 pointer-events-none z-20"
            style={{
                width: "100%",
                height: layoutMinHeight || Math.max(
                    getMinSidebarHeight(commentPositions),
                    transcriptHeight
                ),
            }}
        >
            {connectorPaths}
        </svg>
    )
}
