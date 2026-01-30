"use client"

import { useCallback } from "react"
import { cn } from "@/lib/utils"
import { CommentCard } from "../CommentCard"
import { useInterviewComments, getMinSidebarHeight } from "./context"
import { PendingCommentInput } from "./PendingCommentInput"

interface CommentsSidebarProps {
    className?: string
}

export function CommentsSidebar({ className }: CommentsSidebarProps) {
    const {
        commentSidebarRef,
        anchoredNotes,
        commentPositions,
        layoutMinHeight,
        interaction,
        newComment,
        isSelectingRef,
        canEdit,
        transcriptRef,
        setHoveredCommentId,
        setFocusedCommentId,
        submitComment,
        cancelPendingComment,
        submitReply,
        updateNote,
        deleteNote,
        isSubmitting,
    } = useInterviewComments()

    // Handle comment card hover
    const handleCardHover = useCallback((commentId: string | null, hover: boolean) => {
        if (isSelectingRef.current) return
        setHoveredCommentId(hover ? commentId : null)
    }, [isSelectingRef, setHoveredCommentId])

    // Handle comment card click
    const handleCardClick = useCallback((commentId: string | null) => {
        setFocusedCommentId(commentId)
        // Scroll highlight into view
        if (commentId && transcriptRef.current) {
            const highlight = transcriptRef.current.querySelector(
                `[data-comment-id="${commentId}"]`
            )
            highlight?.scrollIntoView({ behavior: "smooth", block: "center" })
        }
    }, [setFocusedCommentId, transcriptRef])

    return (
        <div className={cn("w-72 shrink-0 border-l border-stone-200 dark:border-stone-800 relative z-30", className)}>
            <div
                ref={commentSidebarRef}
                className="p-2 relative"
                style={{ minHeight: layoutMinHeight || getMinSidebarHeight(commentPositions) }}
            >
                {/* Pending comment input */}
                {newComment.type === "pending" && (
                    <div
                        data-note-id={newComment.commentId}
                        style={{
                            position: "absolute",
                            top: commentPositions.find((p) => p.noteId === newComment.commentId)?.top ?? 0,
                            left: 8,
                            right: 8,
                        }}
                    >
                        <PendingCommentInput
                            anchorText={newComment.text}
                            onSubmit={submitComment}
                            onCancel={cancelPendingComment}
                            isSubmitting={isSubmitting}
                        />
                    </div>
                )}

                {/* Positioned comment cards */}
                {anchoredNotes.map((note) => {
                    const position = commentPositions.find((p) => p.noteId === note.id)
                    const isHovered = interaction.type === "hovering" && interaction.commentId === note.comment_id
                    const isFocused = interaction.type === "focused" && interaction.commentId === note.comment_id

                    return (
                        <div
                            key={note.id}
                            data-note-id={note.id}
                            style={
                                position
                                    ? { position: "absolute", top: position.top, left: 8, right: 8 }
                                    : undefined
                            }
                        >
                            <CommentCard
                                note={note}
                                isHovered={isHovered}
                                isFocused={isFocused}
                                onHover={(hover) => handleCardHover(note.comment_id, hover)}
                                onClick={() => handleCardClick(note.comment_id)}
                                onReply={(content) => submitReply(note.id, content)}
                                onDelete={() => deleteNote(note.id)}
                                onDeleteReply={(replyId) => deleteNote(replyId)}
                                onEdit={(content) => updateNote(note.id, content)}
                                onEditReply={(replyId, content) => updateNote(replyId, content)}
                                canEdit={canEdit}
                            />
                        </div>
                    )
                })}
            </div>
        </div>
    )
}
