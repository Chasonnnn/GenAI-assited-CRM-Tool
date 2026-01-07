"use client"

/**
 * CommentCard - Google Docs-style comment for interview transcripts.
 *
 * Features:
 * - Bidirectional hover highlighting with transcript
 * - Reply threads with nested display
 * - Inline editing support
 */

import { useState, useCallback, useRef, useEffect } from "react"
import { formatDistanceToNow } from "date-fns"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import {
    MessageSquareIcon,
    Trash2Icon,
    PencilIcon,
    XIcon,
    SendIcon,
    CornerDownRightIcon,
    CheckIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import type { InterviewNoteRead } from "@/lib/api/interviews"

interface CommentCardProps {
    note: InterviewNoteRead
    isHovered: boolean
    isFocused: boolean
    onHover: (hover: boolean) => void
    onClick: () => void
    onReply: (content: string) => void
    onDelete: () => void
    onDeleteReply: (replyId: string) => void
    onEdit?: (content: string) => void
    onEditReply?: (replyId: string, content: string) => void
    canEdit: boolean
}

/**
 * Single reply item within a thread
 */
function ReplyItem({
    reply,
    canEdit,
    onDelete,
    onEdit,
}: {
    reply: InterviewNoteRead
    canEdit: boolean
    onDelete: () => void
    onEdit?: (content: string) => void
}) {
    const [isEditing, setIsEditing] = useState(false)
    const [editContent, setEditContent] = useState(reply.content)
    const editInputRef = useRef<HTMLTextAreaElement>(null)
    const canDelete = canEdit
    const canEditReply = canEdit && onEdit

    useEffect(() => {
        if (isEditing && editInputRef.current) {
            editInputRef.current.focus()
        }
    }, [isEditing])

    const handleEditSubmit = useCallback(() => {
        if (!editContent.trim() || !onEdit) return
        onEdit(editContent.trim())
        setIsEditing(false)
    }, [editContent, onEdit])

    return (
        <div className="group relative pl-2 border-l-2 border-stone-200 dark:border-stone-700 ml-1 mt-2">
            <div className="flex items-start gap-2">
                <CornerDownRightIcon className="size-3.5 text-muted-foreground shrink-0 mt-1" />
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 text-xs">
                        <span className="font-medium text-foreground truncate">
                            {reply.author_name}
                        </span>
                        <span className="text-muted-foreground">
                            {formatDistanceToNow(new Date(reply.created_at), { addSuffix: true })}
                        </span>
                    </div>
                    {isEditing ? (
                        <div className="mt-2 space-y-2">
                            <Textarea
                                ref={editInputRef}
                                value={editContent}
                                onChange={(e) => setEditContent(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                                        e.preventDefault()
                                        handleEditSubmit()
                                    } else if (e.key === "Escape") {
                                        e.preventDefault()
                                        setIsEditing(false)
                                        setEditContent(reply.content)
                                    }
                                }}
                                className="min-h-[60px] text-sm resize-none"
                            />
                            <div className="flex items-center gap-1.5 justify-end">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => {
                                        setIsEditing(false)
                                        setEditContent(reply.content)
                                    }}
                                    className="h-7 px-2 text-xs"
                                >
                                    <XIcon className="size-3 mr-1" />
                                    Cancel
                                </Button>
                                <Button
                                    size="sm"
                                    onClick={handleEditSubmit}
                                    disabled={!editContent.trim()}
                                    className="h-7 px-2 text-xs"
                                >
                                    <CheckIcon className="size-3 mr-1" />
                                    Save
                                </Button>
                            </div>
                        </div>
                    ) : (
                        <div
                            className="mt-1 text-sm text-foreground prose prose-sm prose-stone dark:prose-invert max-w-none [&>p]:my-0"
                            dangerouslySetInnerHTML={{ __html: reply.content }}
                        />
                    )}
                </div>
                {canDelete && (
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={onDelete}
                        className="size-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
                    >
                        <Trash2Icon className="size-3" />
                    </Button>
                )}
            </div>
            {canEditReply && !isEditing && (
                <div className="ml-6 mt-1">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setIsEditing(true)}
                        className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
                    >
                        <PencilIcon className="size-3 mr-1" />
                        Edit
                    </Button>
                </div>
            )}
        </div>
    )
}

export function CommentCard({
    note,
    isHovered,
    isFocused,
    onHover,
    onClick,
    onReply,
    onDelete,
    onDeleteReply,
    onEdit,
    onEditReply,
    canEdit,
}: CommentCardProps) {
    const [isReplying, setIsReplying] = useState(false)
    const [isEditing, setIsEditing] = useState(false)
    const [replyContent, setReplyContent] = useState("")
    const [editContent, setEditContent] = useState(note.content)
    const replyInputRef = useRef<HTMLTextAreaElement>(null)
    const editInputRef = useRef<HTMLTextAreaElement>(null)

    const canDelete = canEdit
    const canEditNote = canEdit && onEdit
    const isAnchored = !!note.anchor_text

    // Focus input when replying/editing starts
    useEffect(() => {
        if (isReplying && replyInputRef.current) {
            replyInputRef.current.focus()
        }
    }, [isReplying])

    useEffect(() => {
        if (isEditing && editInputRef.current) {
            editInputRef.current.focus()
        }
    }, [isEditing])

    const handleReplySubmit = useCallback(() => {
        if (!replyContent.trim()) return
        onReply(replyContent.trim())
        setReplyContent("")
        setIsReplying(false)
    }, [replyContent, onReply])

    const handleEditSubmit = useCallback(() => {
        if (!editContent.trim() || !onEdit) return
        onEdit(editContent.trim())
        setIsEditing(false)
    }, [editContent, onEdit])

    const handleKeyDown = useCallback((
        e: React.KeyboardEvent,
        onSubmit: () => void,
        onCancel: () => void
    ) => {
        if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
            e.preventDefault()
            onSubmit()
        } else if (e.key === "Escape") {
            e.preventDefault()
            onCancel()
        }
    }, [])

    return (
        <Card
            className={cn(
                "relative overflow-hidden transition-all duration-200 cursor-pointer",
                "border border-stone-200 dark:border-stone-800",
                // Hover state - bidirectional highlighting
                isHovered && !isFocused && [
                    "ring-2 ring-teal-500/50 shadow-md shadow-teal-500/10",
                    "border-teal-400 dark:border-teal-600",
                ],
                // Focused state - click interaction
                isFocused && [
                    "ring-2 ring-teal-500 shadow-lg shadow-teal-500/15",
                    "border-teal-500 dark:border-teal-500",
                    "bg-teal-50/50 dark:bg-teal-950/20",
                ],
            )}
            onMouseEnter={() => onHover(true)}
            onMouseLeave={() => onHover(false)}
            onClick={onClick}
        >
            <div className="p-3 space-y-2">
                {/* Anchor text quote */}
                {isAnchored && (
                    <div className="relative">
                        <div
                            className={cn(
                                "text-sm italic px-2.5 py-1.5 rounded-md",
                                "bg-amber-50 dark:bg-amber-950/30",
                                "border-l-2 border-amber-400 dark:border-amber-600",
                                "text-amber-800 dark:text-amber-200",
                                "line-clamp-2"
                            )}
                        >
                            &ldquo;{note.anchor_text}&rdquo;
                        </div>
                    </div>
                )}

                {/* Comment content or edit mode */}
                {isEditing ? (
                    <div className="space-y-2" onClick={(e) => e.stopPropagation()}>
                        <Textarea
                            ref={editInputRef}
                            value={editContent}
                            onChange={(e) => setEditContent(e.target.value)}
                            onKeyDown={(e) => handleKeyDown(e, handleEditSubmit, () => {
                                setIsEditing(false)
                                setEditContent(note.content)
                            })}
                            className="min-h-[60px] text-sm resize-none"
                            placeholder="Edit your comment..."
                        />
                        <div className="flex items-center gap-2 justify-end">
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                    setIsEditing(false)
                                    setEditContent(note.content)
                                }}
                                className="h-7 px-2 text-xs"
                            >
                                <XIcon className="size-3 mr-1" />
                                Cancel
                            </Button>
                            <Button
                                size="sm"
                                onClick={handleEditSubmit}
                                disabled={!editContent.trim()}
                                className="h-7 px-2 text-xs"
                            >
                                <CheckIcon className="size-3 mr-1" />
                                Save
                            </Button>
                        </div>
                    </div>
                ) : (
                    <div
                        className="text-sm text-foreground prose prose-sm prose-stone dark:prose-invert max-w-none [&>p]:my-0 [&>p:last-child]:mb-0"
                        dangerouslySetInnerHTML={{ __html: note.content }}
                    />
                )}

                {/* Author and timestamp */}
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="font-medium text-foreground/80 truncate">
                        {note.author_name}
                    </span>
                    <span className="shrink-0">
                        {formatDistanceToNow(new Date(note.created_at), { addSuffix: true })}
                    </span>
                </div>

                {/* Reply thread */}
                {note.replies && note.replies.length > 0 && (
                    <div className="pt-1">
                        {note.replies.map((reply) => (
                            <ReplyItem
                                key={reply.id}
                                reply={reply}
                                canEdit={canEdit}
                                onDelete={() => onDeleteReply(reply.id)}
                                onEdit={onEditReply ? (content) => onEditReply(reply.id, content) : undefined}
                            />
                        ))}
                    </div>
                )}

                {/* Reply input */}
                {isReplying && (
                    <div className="pt-2 space-y-2" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-start gap-2">
                            <CornerDownRightIcon className="size-3.5 text-muted-foreground shrink-0 mt-2" />
                            <Textarea
                                ref={replyInputRef}
                                value={replyContent}
                                onChange={(e) => setReplyContent(e.target.value)}
                                onKeyDown={(e) => handleKeyDown(e, handleReplySubmit, () => {
                                    setIsReplying(false)
                                    setReplyContent("")
                                })}
                                className="flex-1 min-h-[60px] text-sm resize-none"
                                placeholder="Write a reply..."
                            />
                        </div>
                        <div className="flex items-center gap-1.5 justify-end">
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                    setIsReplying(false)
                                    setReplyContent("")
                                }}
                                className="h-7 px-2 text-xs"
                            >
                                <XIcon className="size-3 mr-1" />
                                Cancel
                            </Button>
                            <Button
                                size="sm"
                                onClick={handleReplySubmit}
                                disabled={!replyContent.trim()}
                                className="h-7 px-2 text-xs"
                            >
                                <SendIcon className="size-3 mr-1" />
                                Reply
                            </Button>
                        </div>
                    </div>
                )}

                {/* Action buttons */}
                {!isEditing && !isReplying && (
                    <div
                        className="flex items-center justify-between pt-1"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setIsReplying(true)}
                            className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
                        >
                            <MessageSquareIcon className="size-3 mr-1" />
                            Reply
                        </Button>

                        {canEditNote && (
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setIsEditing(true)}
                                className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
                            >
                                <PencilIcon className="size-3 mr-1" />
                                Edit
                            </Button>
                        )}

                        {canDelete && (
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={onDelete}
                                className="h-7 px-2 text-xs text-muted-foreground hover:text-destructive"
                            >
                                <Trash2Icon className="size-3 mr-1" />
                                Delete
                            </Button>
                        )}
                    </div>
                )}
            </div>
        </Card>
    )
}
