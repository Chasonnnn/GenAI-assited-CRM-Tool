"use client"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { ScrollArea } from "@/components/ui/scroll-area"
import { PlusIcon, Loader2Icon } from "lucide-react"
import { CommentCard } from "../CommentCard"
import { useInterviewComments } from "./context"

interface GeneralNotesSectionProps {
    className?: string
}

export function GeneralNotesSection({ className }: GeneralNotesSectionProps) {
    const {
        generalNotes,
        newComment,
        newNoteContent,
        isSubmitting,
        canEdit,
        startAddingGeneralNote,
        cancelAddingGeneralNote,
        setNewNoteContent,
        submitGeneralNote,
        submitReply,
        deleteNote,
        updateNote,
    } = useInterviewComments()

    const isAddingNote = newComment.type === "adding_general"

    return (
        <div className={className}>
            <div className="p-2 border-b border-stone-200 dark:border-stone-700 flex items-center justify-between shrink-0 bg-background/80 backdrop-blur-sm">
                <h4 className="text-xs font-medium text-muted-foreground">General Notes</h4>
                {canEdit && (
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={startAddingGeneralNote}
                        className="h-6 px-1.5 text-xs"
                        disabled={isAddingNote}
                    >
                        <PlusIcon className="size-3" />
                    </Button>
                )}
            </div>

            <ScrollArea className="flex-1">
                <div className="p-2 space-y-2">
                    {/* New note input */}
                    {isAddingNote && (
                        <div className="bg-card border border-stone-200 dark:border-stone-700 rounded-lg p-2 space-y-2">
                            <Textarea
                                value={newNoteContent}
                                onChange={(e) => setNewNoteContent(e.target.value)}
                                placeholder="Add a note..."
                                className="min-h-[60px] text-sm resize-none"
                                autoFocus
                                onKeyDown={(e) => {
                                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                                        e.preventDefault()
                                        submitGeneralNote()
                                    } else if (e.key === "Escape") {
                                        cancelAddingGeneralNote()
                                    }
                                }}
                            />
                            <div className="flex items-center gap-1.5 justify-end">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={cancelAddingGeneralNote}
                                    className="h-6 px-2 text-xs"
                                >
                                    Cancel
                                </Button>
                                <Button
                                    size="sm"
                                    onClick={submitGeneralNote}
                                    disabled={!newNoteContent.trim() || isSubmitting}
                                    className="h-6 px-2 text-xs"
                                >
                                    {isSubmitting ? (
                                        <Loader2Icon className="size-3 animate-spin" />
                                    ) : (
                                        "Add"
                                    )}
                                </Button>
                            </div>
                        </div>
                    )}

                    {/* Notes list */}
                    {generalNotes.map((note) => (
                        <CommentCard
                            key={note.id}
                            note={note}
                            isHovered={false}
                            isFocused={false}
                            onHover={() => { }}
                            onClick={() => { }}
                            onReply={(content) => submitReply(note.id, content)}
                            onDelete={() => deleteNote(note.id)}
                            onDeleteReply={(replyId) => deleteNote(replyId)}
                            onEdit={(content) => updateNote(note.id, content)}
                            onEditReply={(replyId, content) => updateNote(replyId, content)}
                            canEdit={canEdit}
                        />
                    ))}

                    {generalNotes.length === 0 && !isAddingNote && (
                        <p className="text-xs text-muted-foreground text-center py-2">
                            No general notes
                        </p>
                    )}
                </div>
            </ScrollArea>
        </div>
    )
}
