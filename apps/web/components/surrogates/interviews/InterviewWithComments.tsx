"use client"

/**
 * InterviewWithComments - Google Docs-style transcript with comments.
 *
 * Features:
 * - Transcript pane with highlighted comment anchors
 * - Comments sidebar with positioned cards that scroll WITH transcript
 * - General notes in fixed section at bottom
 * - Bidirectional hover/click interactions
 * - Text selection for new comments
 * - Mobile tabs layout (Transcript | Comments)
 * - Reply threads
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useMediaQuery } from "@/lib/hooks/use-media-query"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import {
    FileTextIcon,
    MessageSquareIcon,
    ChevronDownIcon,
    PlusIcon,
    SendIcon,
    XIcon,
    Loader2Icon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { CommentCard } from "./CommentCard"
import { SelectionPopover } from "./SelectionPopover"
import type {
    InterviewRead,
    InterviewNoteRead,
    TipTapDoc,
    TipTapNode,
    TipTapMark,
} from "@/lib/api/interviews"

// ============================================================================
// Types
// ============================================================================

interface InterviewWithCommentsProps {
    interview: InterviewRead
    notes: InterviewNoteRead[]
    isLoading?: boolean
    onAddNote: (data: {
        content: string
        commentId: string
        anchorText: string
        parentId?: string
    }) => Promise<void>
    onUpdateNote: (noteId: string, content: string) => Promise<void>
    onDeleteNote: (noteId: string) => Promise<void>
    canEdit: boolean
    className?: string
}

interface CommentPosition {
    noteId: string
    top: number
    anchorTop: number // Original anchor position (for SVG lines)
    anchorLeft: number
    cardLeft: number
    height: number
}

const COMMENT_HOVER_CLASSES =
    "bg-amber-200 dark:bg-amber-800/50"
const COMMENT_FOCUS_CLASSES =
    "bg-amber-300 dark:bg-amber-700/60 ring-2 ring-amber-400 ring-offset-1"

// ============================================================================
// TipTap Rendering Helpers
// ============================================================================

/**
 * Build a map of commentId -> noteId for quick lookup
 */
function buildCommentNoteMap(notes: InterviewNoteRead[]): Map<string, string> {
    const map = new Map<string, string>()
    for (const note of notes) {
        if (note.comment_id) {
            map.set(note.comment_id, note.id)
        }
    }
    return map
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text: string): string {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;")
}

/**
 * Apply a TipTap mark to text
 */
function applyMark(
    text: string,
    mark: TipTapMark,
    commentNoteMap: Map<string, string>
): string {
    switch (mark.type) {
        case "bold":
            return `<strong>${text}</strong>`
        case "italic":
            return `<em>${text}</em>`
        case "underline":
            return `<u>${text}</u>`
        case "strike":
            return `<s>${text}</s>`
        case "code":
            return `<code class="px-1 py-0.5 rounded bg-muted text-sm">${text}</code>`
        case "link": {
            const href = typeof mark.attrs?.href === "string" ? mark.attrs.href : "#"
            return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer" class="text-primary underline hover:text-primary/80">${text}</a>`
        }
        case "comment": {
            const commentId = typeof mark.attrs?.commentId === "string" ? mark.attrs.commentId : ""
            if (!commentId) return text

            const noteId = commentNoteMap.get(commentId)
            const hasNote = !!noteId

            // Base classes
            const baseClasses = "transition-all duration-150 rounded-sm cursor-pointer"

            // State-dependent classes
            const stateClasses = hasNote
                ? cn(
                    "bg-amber-100/80 dark:bg-amber-900/40",
                    "border-b-2 border-amber-400 dark:border-amber-500"
                )
                : cn(
                    // Orphaned comment (no matching note)
                    "bg-stone-100 dark:bg-stone-800/40",
                    "border-b-2 border-stone-300 dark:border-stone-600 border-dashed"
                )

            return `<span class="comment-highlight ${baseClasses} ${stateClasses}" data-comment-id="${escapeHtml(commentId)}" data-note-id="${escapeHtml(noteId || "")}">${text}</span>`
        }
        case "highlight":
            return `<mark class="bg-yellow-200 dark:bg-yellow-800/40 px-0.5 rounded-sm">${text}</mark>`
        default:
            return text
    }
}

/**
 * Render a TipTap node to HTML
 */
function renderNode(
    node: TipTapNode,
    commentNoteMap: Map<string, string>
): string {
    if (node.type === "text") {
        let text = escapeHtml(node.text || "")

        // Apply marks
        if (node.marks) {
            for (const mark of node.marks) {
                text = applyMark(text, mark, commentNoteMap)
            }
        }

        return text
    }

    // Handle different node types
    const children = node.content
        ?.map((child) => renderNode(child, commentNoteMap))
        .join("") || ""

    switch (node.type) {
        case "doc":
            return children
        case "paragraph":
            return `<p class="my-2 first:mt-0 last:mb-0">${children || "<br/>"}</p>`
        case "heading": {
            const rawLevel = node.attrs?.level
            const level = typeof rawLevel === "number" ? rawLevel : Number(rawLevel) || 1
            const sizes: Record<number, string> = {
                1: "text-xl font-bold",
                2: "text-lg font-semibold",
                3: "text-base font-medium",
            }
            return `<h${level} class="${sizes[level] || sizes[3]} my-3">${children}</h${level}>`
        }
        case "bulletList":
            return `<ul class="list-disc list-inside my-2 space-y-1">${children}</ul>`
        case "orderedList":
            return `<ol class="list-decimal list-inside my-2 space-y-1">${children}</ol>`
        case "listItem":
            return `<li>${children}</li>`
        case "blockquote":
            return `<blockquote class="border-l-4 border-stone-300 dark:border-stone-600 pl-4 my-3 italic text-muted-foreground">${children}</blockquote>`
        case "codeBlock":
            return `<pre class="bg-muted rounded-md p-3 my-3 overflow-x-auto"><code class="text-sm">${children}</code></pre>`
        case "hardBreak":
            return "<br/>"
        case "horizontalRule":
            return `<hr class="my-4 border-stone-200 dark:border-stone-700" />`
        default:
            return children
    }
}

/**
 * Escape special regex characters
 */
function escapeRegex(str: string): string {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
}

/**
 * Highlight anchor texts that don't have comment marks in the transcript.
 * This handles notes created via the selection popover that store anchor_text
 * but the transcript may not have the comment mark.
 */
function highlightAnchorTexts(
    html: string,
    notes: InterviewNoteRead[]
): string {
    let result = html

    for (const note of notes) {
        // Only process notes that have anchor_text but aren't already highlighted via comment marks
        if (!note.anchor_text || !note.comment_id) continue

        // Check if this comment is already in the transcript
        if (result.includes(`data-comment-id="${note.comment_id}"`)) continue

        // Try to find and highlight the anchor text
        const baseClasses = "transition-all duration-150 rounded-sm cursor-pointer"
        const stateClasses = cn(
            "bg-amber-100/80 dark:bg-amber-900/40",
            "border-b-2 border-amber-400 dark:border-amber-500"
        )

        const safeAnchorText = escapeHtml(note.anchor_text)
        const escapedAnchor = escapeRegex(safeAnchorText)
        // Only replace first occurrence to avoid highlighting duplicates
        const regex = new RegExp(`(?<!data-comment-id[^>]*>)${escapedAnchor}(?![^<]*</span>)`, "")
        const replacement = `<span class="comment-highlight ${baseClasses} ${stateClasses}" data-comment-id="${escapeHtml(note.comment_id)}" data-note-id="${escapeHtml(note.id)}">${safeAnchorText}</span>`

        result = result.replace(regex, replacement)
    }

    return result
}

/**
 * Render TipTap JSON to HTML with comment highlighting
 */
function renderTranscript(
    doc: TipTapDoc | null,
    notes: InterviewNoteRead[],
    commentNoteMap: Map<string, string>
): string {
    if (!doc?.content) return ""

    let html = doc.content
        .map((node) => renderNode(node, commentNoteMap))
        .join("")

    // Apply fallback highlighting for notes with anchor_text
    html = highlightAnchorTexts(html, notes)

    return html
}

// ============================================================================
// Component
// ============================================================================

export function InterviewWithComments({
    interview,
    notes,
    isLoading = false,
    onAddNote,
    onUpdateNote,
    onDeleteNote,
    canEdit,
    className,
}: InterviewWithCommentsProps) {
    const isMobile = useMediaQuery("(max-width: 768px)")
    const scrollContainerRef = useRef<HTMLDivElement>(null)
    const transcriptRef = useRef<HTMLDivElement>(null)
    const commentSidebarRef = useRef<HTMLDivElement>(null)
    const layoutRef = useRef<HTMLDivElement>(null)
    const isSelectingRef = useRef(false)

    // Comment state
    const [hoveredCommentId, setHoveredCommentId] = useState<string | null>(null)
    const [focusedCommentId, setFocusedCommentId] = useState<string | null>(null)
    const [commentPositions, setCommentPositions] = useState<CommentPosition[]>([])
    const [layoutMinHeight, setLayoutMinHeight] = useState(0)
    const hoveredIdRef = useRef<string | null>(null)
    const focusedIdRef = useRef<string | null>(null)

    // New comment state
    const [isAddingGeneralNote, setIsAddingGeneralNote] = useState(false)
    const [newNoteContent, setNewNoteContent] = useState("")
    const [pendingComment, setPendingComment] = useState<{
        text: string
        commentId: string
        anchorTop: number
        anchorLeft: number
    } | null>(null)
    const [isSubmitting, setIsSubmitting] = useState(false)

    // Build comment-to-note mapping
    const commentNoteMap = useMemo(() => buildCommentNoteMap(notes), [notes])

    // Separate anchored and general notes
    const anchoredNotes = useMemo(
        () => notes.filter((n) => n.comment_id || n.anchor_text),
        [notes]
    )
    const generalNotes = useMemo(
        () => notes.filter((n) => !n.comment_id && !n.anchor_text),
        [notes]
    )

    // Render transcript HTML
    const transcriptHtml = useMemo(
        () =>
            renderTranscript(
                interview.transcript_json,
                notes,
                commentNoteMap
            ),
        [interview.transcript_json, notes, commentNoteMap]
    )

    const activeNoteId = useMemo(() => {
        if (!focusedCommentId) return null
        return commentNoteMap.get(focusedCommentId) ?? null
    }, [focusedCommentId, commentNoteMap])

    // Calculate comment positions based on anchor elements
    const calculatePositions = useCallback(() => {
        if (!transcriptRef.current) return

        const container = transcriptRef.current
        const layout = layoutRef.current
        if (!layout || !container) return
        const layoutRect = layout.getBoundingClientRect()
        const containerRect = container.getBoundingClientRect()
        const sidebarRect = commentSidebarRef.current?.getBoundingClientRect()
        const positions: CommentPosition[] = []
        const sidebarLeft = sidebarRect
            ? sidebarRect.left - layoutRect.left + 8
            : 0
        const fallbackAnchorLeft = Math.max(
            (containerRect.right - layoutRect.left) - 12,
            0
        )

        for (const note of anchoredNotes) {
            const commentId = note.comment_id
            if (!commentId) continue

            const anchorEl = container.querySelector(
                `[data-comment-id="${commentId}"]`
            )
            let topOffset = 0
            let anchorLeft = fallbackAnchorLeft

            if (anchorEl) {
                const anchorRect = anchorEl.getBoundingClientRect()
                // Calculate offset from top of transcript content
                topOffset = anchorRect.top - containerRect.top
                anchorLeft = anchorRect.left - layoutRect.left + Math.min(anchorRect.width, 12)
            } else if (positions.length > 0) {
                const lastPosition = positions[positions.length - 1]
                if (lastPosition) {
                    topOffset = lastPosition.anchorTop + 24
                }
            }

            positions.push({
                noteId: note.id,
                top: topOffset,
                anchorTop: topOffset, // Store original anchor position for SVG lines
                anchorLeft,
                cardLeft: sidebarLeft,
                height: 0,
            })
        }

        if (pendingComment) {
            positions.push({
                noteId: pendingComment.commentId,
                top: pendingComment.anchorTop,
                anchorTop: pendingComment.anchorTop,
                anchorLeft: pendingComment.anchorLeft || fallbackAnchorLeft,
                cardLeft: sidebarLeft,
                height: 0,
            })
        }

        for (const position of positions) {
            const cardEl = commentSidebarRef.current?.querySelector<HTMLElement>(
                `[data-note-id="${position.noteId}"]`
            )
            position.height = cardEl?.offsetHeight || 140
        }

        // Sort by position and apply collision avoidance
        positions.sort((a, b) => {
            const delta = a.anchorTop - b.anchorTop
            return delta !== 0 ? delta : a.noteId.localeCompare(b.noteId)
        })
        avoidCollisions(positions)

        setCommentPositions(positions)

        const commentsHeight = getMinSidebarHeight(positions)
        const transcriptHeight = transcriptRef.current?.scrollHeight ?? 0
        setLayoutMinHeight(Math.max(commentsHeight, transcriptHeight, 200))
    }, [anchoredNotes, pendingComment])

    const toggleSpanClasses = useCallback((commentId: string, classNames: string, enabled: boolean) => {
        const container = transcriptRef.current
        if (!container) return
        const span = container.querySelector(`[data-comment-id="${commentId}"]`)
        if (!span) return
        for (const className of classNames.split(" ")) {
            if (!className) continue
            if (enabled) {
                span.classList.add(className)
            } else {
                span.classList.remove(className)
            }
        }
    }, [])

    useEffect(() => {
        const prev = hoveredIdRef.current
        if (prev && prev !== hoveredCommentId) {
            toggleSpanClasses(prev, COMMENT_HOVER_CLASSES, false)
        }
        if (hoveredCommentId) {
            toggleSpanClasses(hoveredCommentId, COMMENT_HOVER_CLASSES, true)
        }
        hoveredIdRef.current = hoveredCommentId
    }, [hoveredCommentId, toggleSpanClasses])

    useEffect(() => {
        const prev = focusedIdRef.current
        if (prev && prev !== focusedCommentId) {
            toggleSpanClasses(prev, COMMENT_FOCUS_CLASSES, false)
        }
        if (focusedCommentId) {
            toggleSpanClasses(focusedCommentId, COMMENT_FOCUS_CLASSES, true)
        }
        focusedIdRef.current = focusedCommentId
    }, [focusedCommentId, toggleSpanClasses])

    // Collision avoidance for overlapping comments
    function avoidCollisions(positions: CommentPosition[]) {
        const MIN_GAP = 12  // Ensure buttons are never covered

        for (let i = 1; i < positions.length; i++) {
            const prev = positions[i - 1]
            const curr = positions[i]
            if (!prev || !curr) continue
            const minTop = prev.top + prev.height + MIN_GAP
            if (curr.top < minTop) {
                curr.top = minTop
            }
        }
    }

    // Recalculate positions on mount and resize
    useEffect(() => {
        // Delay initial calculation to allow DOM to settle
        const timer = setTimeout(calculatePositions, 100)

        const container = transcriptRef.current
        if (!container) return

        const resizeObserver = new ResizeObserver(() => {
            requestAnimationFrame(calculatePositions)
        })
        resizeObserver.observe(container)

        return () => {
            clearTimeout(timer)
            resizeObserver.disconnect()
        }
    }, [calculatePositions])

    useEffect(() => {
        const raf = window.requestAnimationFrame(() => {
            calculatePositions()
        })
        return () => {
            window.cancelAnimationFrame(raf)
        }
    }, [calculatePositions, transcriptHtml])

    useEffect(() => {
        const scroller = scrollContainerRef.current
        if (!scroller) return
        let raf = 0
        const handleScroll = () => {
            if (raf) return
            raf = window.requestAnimationFrame(() => {
                calculatePositions()
                raf = 0
            })
        }
        scroller.addEventListener("scroll", handleScroll, { passive: true })
        return () => {
            scroller.removeEventListener("scroll", handleScroll)
            if (raf) window.cancelAnimationFrame(raf)
        }
    }, [calculatePositions])

    useEffect(() => {
        const container = commentSidebarRef.current
        if (!container) return
        const observer = new ResizeObserver(() => {
            requestAnimationFrame(calculatePositions)
        })
        const nodes = container.querySelectorAll("[data-note-id]")
        nodes.forEach((node) => observer.observe(node))
        return () => {
            observer.disconnect()
        }
    }, [calculatePositions, anchoredNotes, pendingComment])

    // Handle hover on transcript highlights (event delegation)
    const handleTranscriptMouseOver = useCallback((e: React.MouseEvent) => {
        if (isSelectingRef.current) return
        const target = e.target instanceof HTMLElement ? e.target : null
        const commentSpan = target?.closest("[data-comment-id]")
        if (commentSpan) {
            setHoveredCommentId(commentSpan.getAttribute("data-comment-id"))
        }
    }, [])

    const handleTranscriptMouseOut = useCallback((e: React.MouseEvent) => {
        if (isSelectingRef.current) return
        const related = e.relatedTarget instanceof HTMLElement ? e.relatedTarget : null
        if (!related?.closest("[data-comment-id]")) {
            setHoveredCommentId(null)
        }
    }, [])

    // Handle click on transcript highlights
    const handleTranscriptClick = useCallback((e: React.MouseEvent) => {
        if (isSelectingRef.current) return
        const target = e.target instanceof HTMLElement ? e.target : null
        const commentSpan = target?.closest("[data-comment-id]")
        if (commentSpan) {
            const commentId = commentSpan.getAttribute("data-comment-id")
            setFocusedCommentId(commentId)
        }
    }, [])

    // Handle selection for new comment
    const handleAddComment = useCallback(
        (selection: { text: string; range: Range }) => {
            const commentId = crypto.randomUUID()
            const rect = selection.range.getClientRects()[0]
            const transcriptRect = transcriptRef.current?.getBoundingClientRect()
            const layoutRect = layoutRef.current?.getBoundingClientRect()
            const anchorTop = rect && transcriptRect
                ? rect.top - transcriptRect.top
                : 0
            const anchorLeft = rect && layoutRect
                ? rect.left - layoutRect.left + Math.min(rect.width, 12)
                : 0
            const firstLine = selection.text.split(/\r?\n/)[0] ?? ""
            const anchorText = firstLine
                .replace(/\s+/g, " ")
                .trim()
            setPendingComment({
                text: anchorText,
                commentId,
                anchorTop,
                anchorLeft,
            })
        },
        []
    )

    // Submit new anchored comment
    const handleSubmitComment = useCallback(
        async (content: string) => {
            if (!pendingComment || !content.trim()) return

            setIsSubmitting(true)
            try {
                await onAddNote({
                    content: content.trim(),
                    commentId: pendingComment.commentId,
                    anchorText: pendingComment.text,
                })
                setPendingComment(null)
            } finally {
                setIsSubmitting(false)
            }
        },
        [pendingComment, onAddNote]
    )

    // Submit reply
    const handleReply = useCallback(
        async (noteId: string, content: string) => {
            const parentNote = notes.find((n) => n.id === noteId)
            if (!parentNote) return

            setIsSubmitting(true)
            try {
                await onAddNote({
                    content,
                    commentId: "",
                    anchorText: "",
                    parentId: noteId,
                })
            } finally {
                setIsSubmitting(false)
            }
        },
        [notes, onAddNote]
    )

    // Submit general note
    const handleSubmitGeneralNote = useCallback(async () => {
        if (!newNoteContent.trim()) return

        setIsSubmitting(true)
        try {
            await onAddNote({
                content: newNoteContent.trim(),
                commentId: "",
                anchorText: "",
            })
            setNewNoteContent("")
            setIsAddingGeneralNote(false)
        } finally {
            setIsSubmitting(false)
        }
    }, [newNoteContent, onAddNote])

    // Handle comment card hover
    const handleCardHover = useCallback((commentId: string | null, hover: boolean) => {
        if (isSelectingRef.current) return
        setHoveredCommentId(hover ? commentId : null)
    }, [])

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
    }, [])

    // Loading state
    if (isLoading) {
        return (
            <div className={cn("flex items-center justify-center h-64", className)}>
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    // No transcript
    if (!interview.transcript_json) {
        return (
            <div className={cn("flex items-center justify-center h-64 text-center", className)}>
                <div>
                    <FileTextIcon className="size-12 mx-auto mb-4 text-muted-foreground/50" />
                    <p className="text-muted-foreground">No transcript available</p>
                </div>
            </div>
        )
    }

    // Mobile: tabs layout
    if (isMobile) {
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
                    <div
                        ref={transcriptRef}
                        className={cn(
                            "p-4 prose prose-sm prose-stone dark:prose-invert max-w-none",
                            "selection:bg-teal-200 dark:selection:bg-teal-800",
                        )}
                        onMouseOver={handleTranscriptMouseOver}
                        onMouseOut={handleTranscriptMouseOut}
                        onMouseLeave={() => setHoveredCommentId(null)}
                        onClick={handleTranscriptClick}
                        dangerouslySetInnerHTML={{ __html: transcriptHtml }}
                    />
                    <SelectionPopover
                        containerRef={transcriptRef}
                        onAddComment={handleAddComment}
                        disabled={!canEdit || !!pendingComment}
                        onSelectionStateChange={(active) => {
                            isSelectingRef.current = active
                            if (active) {
                                setHoveredCommentId(null)
                            }
                        }}
                    />
                </TabsContent>
                <TabsContent value="comments" className="flex-1 m-0 overflow-hidden flex flex-col">
                    <ScrollArea className="flex-1">
                        <div className="p-3 space-y-3">
                            {/* Pending comment input */}
                            {pendingComment && (
                                <PendingCommentInput
                                    anchorText={pendingComment.text}
                                    onSubmit={handleSubmitComment}
                                    onCancel={() => setPendingComment(null)}
                                    isSubmitting={isSubmitting}
                                />
                            )}

                            {/* Anchored comments */}
                            {anchoredNotes.map((note) => (
                                <CommentCard
                                    key={note.id}
                                    note={note}
                                    isHovered={hoveredCommentId === note.comment_id}
                                    isFocused={focusedCommentId === note.comment_id}
                                    onHover={(hover) => handleCardHover(note.comment_id, hover)}
                                    onClick={() => handleCardClick(note.comment_id)}
                                    onReply={(content) => handleReply(note.id, content)}
                                    onDelete={() => onDeleteNote(note.id)}
                                    onDeleteReply={(replyId) => onDeleteNote(replyId)}
                                    onEdit={(content) => onUpdateNote(note.id, content)}
                                    onEditReply={(replyId, content) => onUpdateNote(replyId, content)}
                                    canEdit={canEdit}
                                />
                            ))}
                        </div>
                    </ScrollArea>

                    {/* General notes - fixed at bottom */}
                    <GeneralNotesSection
                        notes={generalNotes}
                        isAddingNote={isAddingGeneralNote}
                        newNoteContent={newNoteContent}
                        isSubmitting={isSubmitting}
                        canEdit={canEdit}
                        onStartAdding={() => setIsAddingGeneralNote(true)}
                        onCancelAdding={() => {
                            setIsAddingGeneralNote(false)
                            setNewNoteContent("")
                        }}
                        onContentChange={setNewNoteContent}
                        onSubmit={handleSubmitGeneralNote}
                        onReply={handleReply}
                        onDelete={onDeleteNote}
                        onDeleteReply={onDeleteNote}
                        onEdit={onUpdateNote}
                        onEditReply={onUpdateNote}
                    />
                </TabsContent>
            </Tabs>
        )
    }

    // Desktop: 2-column layout with bottom general notes
    return (
        <div className={cn("flex flex-col h-full", className)}>
            {/* Main content area: Transcript + Comments */}
            <div className="flex-1 flex overflow-hidden">
                {/* Main scrollable area containing transcript and positioned comments */}
                <div
                    ref={scrollContainerRef}
                    className="flex-1 overflow-auto"
                >
                    <div
                        ref={layoutRef}
                        className="flex min-h-full relative"
                        style={{ minHeight: layoutMinHeight || undefined }}
                    >
                        {(activeNoteId || pendingComment) && (
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
                                    .filter((pos) => pos.noteId === activeNoteId || pos.noteId === pendingComment?.commentId)
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
                        )}
                        {/* Transcript pane */}
                        <div className="flex-1 min-w-0 relative z-10">
                            <div
                                ref={transcriptRef}
                                className={cn(
                                    "p-4 prose prose-sm prose-stone dark:prose-invert max-w-none",
                                    "selection:bg-teal-200 dark:selection:bg-teal-800",
                                )}
                                onMouseOver={handleTranscriptMouseOver}
                                onMouseOut={handleTranscriptMouseOut}
                                onMouseLeave={() => setHoveredCommentId(null)}
                                onClick={handleTranscriptClick}
                                dangerouslySetInnerHTML={{ __html: transcriptHtml }}
                            />
                            <SelectionPopover
                                containerRef={transcriptRef}
                                onAddComment={handleAddComment}
                                disabled={!canEdit || !!pendingComment}
                                onSelectionStateChange={(active) => {
                                    isSelectingRef.current = active
                                    if (active) {
                                        setHoveredCommentId(null)
                                    }
                                }}
                            />
                        </div>

                        {/* Anchored comments sidebar - scrolls with transcript */}
                        <div className="w-72 shrink-0 border-l border-stone-200 dark:border-stone-800 relative z-30">
                            <div
                                ref={commentSidebarRef}
                                className="p-2 relative"
                                style={{ minHeight: layoutMinHeight || getMinSidebarHeight(commentPositions) }}
                            >
                                {/* Pending comment input */}
                                {pendingComment && (
                                    <div
                                        data-note-id={pendingComment.commentId}
                                        style={{
                                            position: "absolute",
                                            top: commentPositions.find((p) => p.noteId === pendingComment.commentId)?.top ?? 0,
                                            left: 8,
                                            right: 8,
                                        }}
                                    >
                                        <PendingCommentInput
                                            anchorText={pendingComment.text}
                                            onSubmit={handleSubmitComment}
                                            onCancel={() => setPendingComment(null)}
                                            isSubmitting={isSubmitting}
                                        />
                                    </div>
                                )}

                                {/* Positioned comment cards */}
                                {anchoredNotes.map((note) => {
                                    const position = commentPositions.find((p) => p.noteId === note.id)
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
                                                isHovered={hoveredCommentId === note.comment_id}
                                                isFocused={focusedCommentId === note.comment_id}
                                                onHover={(hover) => handleCardHover(note.comment_id, hover)}
                                                onClick={() => handleCardClick(note.comment_id)}
                                                onReply={(content) => handleReply(note.id, content)}
                                                onDelete={() => onDeleteNote(note.id)}
                                                onDeleteReply={(replyId) => onDeleteNote(replyId)}
                                                onEdit={(content) => onUpdateNote(note.id, content)}
                                                onEditReply={(replyId, content) => onUpdateNote(replyId, content)}
                                                canEdit={canEdit}
                                            />
                                        </div>
                                    )
                                })}

                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* General notes - full width at bottom (collapsible) */}
            <Collapsible defaultOpen={generalNotes.length > 0} className="shrink-0 border-t border-stone-200 dark:border-stone-800">
                <CollapsibleTrigger className="w-full px-4 py-2 flex items-center justify-between text-sm hover:bg-muted/50 transition-colors">
                    <div className="flex items-center gap-2">
                        <MessageSquareIcon className="size-4 text-muted-foreground" />
                        <span className="font-medium text-sm">General Notes</span>
                        {generalNotes.length > 0 && (
                            <Badge variant="secondary" className="text-xs px-1.5 py-0">{generalNotes.length}</Badge>
                        )}
                    </div>
                    <ChevronDownIcon className="size-4 text-muted-foreground transition-transform [[data-state=open]>&]:rotate-180" />
                </CollapsibleTrigger>
                <CollapsibleContent>
                    <div className="max-h-48 overflow-auto bg-muted/20">
                        <GeneralNotesSection
                            notes={generalNotes}
                            isAddingNote={isAddingGeneralNote}
                            newNoteContent={newNoteContent}
                            isSubmitting={isSubmitting}
                            canEdit={canEdit}
                            onStartAdding={() => setIsAddingGeneralNote(true)}
                            onCancelAdding={() => {
                                setIsAddingGeneralNote(false)
                                setNewNoteContent("")
                            }}
                            onContentChange={setNewNoteContent}
                            onSubmit={handleSubmitGeneralNote}
                            onReply={handleReply}
                            onDelete={onDeleteNote}
                            onDeleteReply={onDeleteNote}
                            onEdit={onUpdateNote}
                            onEditReply={onUpdateNote}
                        />
                    </div>
                </CollapsibleContent>
            </Collapsible>
        </div>
    )
}

// ============================================================================
// Helper Components
// ============================================================================

function getMinSidebarHeight(positions: CommentPosition[]): number {
    if (positions.length === 0) return 100
    let maxBottom = 0
    for (const position of positions) {
        maxBottom = Math.max(maxBottom, position.top + position.height)
    }
    return maxBottom + 40
}


interface PendingCommentInputProps {
    anchorText: string
    onSubmit: (content: string) => void
    onCancel: () => void
    isSubmitting: boolean
}

function PendingCommentInput({ anchorText, onSubmit, onCancel, isSubmitting }: PendingCommentInputProps) {
    const [content, setContent] = useState("")

    return (
        <div className="bg-card border border-teal-500 rounded-lg p-3 space-y-2 shadow-md mb-3">
            <div className="text-xs italic px-2 py-1 rounded bg-amber-50 dark:bg-amber-950/30 border-l-2 border-amber-400 text-amber-800 dark:text-amber-200 line-clamp-2">
                &ldquo;{anchorText}&rdquo;
            </div>
            <Textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="Add your comment..."
                className="min-h-[80px] text-sm resize-none"
                autoFocus
                onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                        e.preventDefault()
                        onSubmit(content)
                    } else if (e.key === "Escape") {
                        onCancel()
                    }
                }}
            />
            <div className="flex items-center gap-2 justify-end">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={onCancel}
                    className="h-7 px-2 text-xs"
                >
                    <XIcon className="size-3 mr-1" />
                    Cancel
                </Button>
                <Button
                    size="sm"
                    onClick={() => onSubmit(content)}
                    disabled={!content.trim() || isSubmitting}
                    className="h-7 px-2 text-xs"
                >
                    {isSubmitting ? (
                        <Loader2Icon className="size-3 mr-1 animate-spin" />
                    ) : (
                        <SendIcon className="size-3 mr-1" />
                    )}
                    Comment
                </Button>
            </div>
        </div>
    )
}

interface GeneralNotesSectionProps {
    notes: InterviewNoteRead[]
    isAddingNote: boolean
    newNoteContent: string
    isSubmitting: boolean
    canEdit: boolean
    onStartAdding: () => void
    onCancelAdding: () => void
    onContentChange: (content: string) => void
    onSubmit: () => void
    onReply: (noteId: string, content: string) => void
    onDelete: (noteId: string) => void
    onDeleteReply: (noteId: string) => void
    onEdit: (noteId: string, content: string) => void
    onEditReply: (noteId: string, content: string) => void
}

function GeneralNotesSection({
    notes,
    isAddingNote,
    newNoteContent,
    isSubmitting,
    canEdit,
    onStartAdding,
    onCancelAdding,
    onContentChange,
    onSubmit,
    onReply,
    onDelete,
    onDeleteReply,
    onEdit,
    onEditReply,
}: GeneralNotesSectionProps) {
    return (
        <div className="flex flex-col h-full">
            <div className="p-2 border-b border-stone-200 dark:border-stone-700 flex items-center justify-between shrink-0 bg-background/80 backdrop-blur-sm">
                <h4 className="text-xs font-medium text-muted-foreground">General Notes</h4>
                {canEdit && (
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={onStartAdding}
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
                                onChange={(e) => onContentChange(e.target.value)}
                                placeholder="Add a note..."
                                className="min-h-[60px] text-sm resize-none"
                                autoFocus
                                onKeyDown={(e) => {
                                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                                        e.preventDefault()
                                        onSubmit()
                                    } else if (e.key === "Escape") {
                                        onCancelAdding()
                                    }
                                }}
                            />
                            <div className="flex items-center gap-1.5 justify-end">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={onCancelAdding}
                                    className="h-6 px-2 text-xs"
                                >
                                    Cancel
                                </Button>
                                <Button
                                    size="sm"
                                    onClick={onSubmit}
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
                    {notes.map((note) => (
                        <CommentCard
                            key={note.id}
                            note={note}
                            isHovered={false}
                            isFocused={false}
                            onHover={() => { }}
                            onClick={() => { }}
                            onReply={(content) => onReply(note.id, content)}
                            onDelete={() => onDelete(note.id)}
                            onDeleteReply={(replyId) => onDeleteReply(replyId)}
                            onEdit={(content) => onEdit(note.id, content)}
                            onEditReply={(replyId, content) => onEditReply(replyId, content)}
                            canEdit={canEdit}
                        />
                    ))}

                    {notes.length === 0 && !isAddingNote && (
                        <p className="text-xs text-muted-foreground text-center py-2">
                            No general notes
                        </p>
                    )}
                </div>
            </ScrollArea>
        </div>
    )
}
