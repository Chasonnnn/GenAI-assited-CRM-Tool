"use client"

import { useCallback } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
import { FileTextIcon, MessageSquareIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { CommentCard } from "../CommentCard"
import { useInterviewComments } from "./context"
import { TranscriptPane } from "./TranscriptPane"
import { PendingCommentInput } from "./PendingCommentInput"
import { GeneralNotesSection } from "./GeneralNotesSection"

interface MobileLayoutProps {
    className?: string | undefined
}

export function MobileLayout({ className }: MobileLayoutProps) {
    const {
        notes,
        anchoredNotes,
        interaction,
        newComment,
        isSubmitting,
        canEdit,
        isSelectingRef,
        setHoveredCommentId,
        setFocusedCommentId,
        submitComment,
        cancelPendingComment,
        submitReply,
        deleteNote,
        updateNote,
    } = useInterviewComments()

    // Handle comment card hover
    const handleCardHover = useCallback((commentId: string | null, hover: boolean) => {
        if (isSelectingRef.current) return
        setHoveredCommentId(hover ? commentId : null)
    }, [isSelectingRef, setHoveredCommentId])

    // Handle comment card click
    const handleCardClick = useCallback((commentId: string | null) => {
        setFocusedCommentId(commentId)
    }, [setFocusedCommentId])

    return (
        <Tabs defaultValue="transcript" className={cn("h-full flex flex-col", className)}>
            <TabsList className="mx-4 mt-2">
                <TabsTrigger value="transcript" className="flex-1">
                    <FileTextIcon className="size-4 mr-1.5" />
                    Transcript
                </TabsTrigger>
                <TabsTrigger value="comments" className="flex-1">
                    <MessageSquareIcon className="size-4 mr-1.5" />
                    Comments
                    {notes.length > 0 && (
                        <span className="ml-1.5 bg-primary/10 text-primary text-xs px-1.5 rounded-full">
                            {notes.length}
                        </span>
                    )}
                </TabsTrigger>
            </TabsList>

            <TabsContent value="transcript" className="flex-1 m-0 overflow-auto">
                <TranscriptPane />
            </TabsContent>

            <TabsContent value="comments" className="flex-1 m-0 overflow-hidden flex flex-col">
                <ScrollArea className="flex-1">
                    <div className="p-3 space-y-3">
                        {/* Pending comment input */}
                        {newComment.type === "pending" && (
                            <PendingCommentInput
                                anchorText={newComment.text}
                                onSubmit={submitComment}
                                onCancel={cancelPendingComment}
                                isSubmitting={isSubmitting}
                            />
                        )}

                        {/* Anchored comments */}
                        {anchoredNotes.map((note) => {
                            const isHovered = interaction.type === "hovering" && interaction.commentId === note.comment_id
                            const isFocused = interaction.type === "focused" && interaction.commentId === note.comment_id

                            return (
                                <CommentCard
                                    key={note.id}
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
                            )
                        })}
                    </div>
                </ScrollArea>

                {/* General notes - fixed at bottom */}
                <GeneralNotesSection className="flex flex-col h-auto max-h-48 border-t border-stone-200 dark:border-stone-800" />
            </TabsContent>
        </Tabs>
    )
}
