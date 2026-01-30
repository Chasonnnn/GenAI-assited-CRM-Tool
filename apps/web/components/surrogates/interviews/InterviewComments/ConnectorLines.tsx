"use client"

import { useInterviewComments, getMinSidebarHeight } from "./context"

export function ConnectorLines() {
    const {
        commentPositions,
        layoutMinHeight,
        activeNoteId,
        newComment,
        transcriptRef,
    } = useInterviewComments()

    // Only render when there's an active note or pending comment
    if (!activeNoteId && newComment.type !== "pending") {
        return null
    }

    const pendingCommentId = newComment.type === "pending" ? newComment.commentId : null

    return (
        <svg
            className="absolute inset-0 pointer-events-none z-20"
            style={{
                width: "100%",
                height: layoutMinHeight || Math.max(
                    getMinSidebarHeight(commentPositions),
                    transcriptRef.current?.scrollHeight ?? 0
                ),
            }}
        >
            {commentPositions
                .filter((pos) => pos.noteId === activeNoteId || pos.noteId === pendingCommentId)
                .map((pos) => {
                    const startY = pos.anchorTop + 12
                    const endY = pos.top + 16
                    const startX = pos.anchorLeft
                    const endX = pos.cardLeft
                    const midX = startX + (endX - startX) / 2
                    if (!startX || !endX) return null

                    return (
                        <path
                            key={pos.noteId}
                            d={`M ${startX},${startY} C ${midX},${startY} ${midX},${endY} ${endX},${endY}`}
                            stroke="currentColor"
                            className="text-stone-300 dark:text-stone-600"
                            strokeWidth="1.5"
                            fill="none"
                        />
                    )
                })}
        </svg>
    )
}
