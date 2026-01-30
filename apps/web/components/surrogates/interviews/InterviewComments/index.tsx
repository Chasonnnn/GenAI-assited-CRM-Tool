"use client"

/**
 * InterviewComments - Google Docs-style transcript with comments.
 *
 * Refactored as compound components with context for state management.
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

import { useMemo } from "react"
import { useMediaQuery } from "@/lib/hooks/use-media-query"
import { Loader2Icon, FileTextIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import type {
    InterviewRead,
    InterviewNoteRead,
    TipTapDoc,
    TipTapNode,
    TipTapMark,
} from "@/lib/api/interviews"

import { InterviewCommentsProvider } from "./context"
import { MobileLayout } from "./MobileLayout"
import { DesktopLayout } from "./DesktopLayout"

// Re-export context hook for external use
export { useInterviewComments } from "./context"
export type { CommentInteraction, NewCommentState, CommentPosition } from "./context"

// ============================================================================
// TipTap Rendering Helpers
// ============================================================================

function buildCommentNoteMap(notes: InterviewNoteRead[]): Map<string, string> {
    const map = new Map<string, string>()
    for (const note of notes) {
        if (note.comment_id) {
            map.set(note.comment_id, note.id)
        }
    }
    return map
}

function escapeHtml(text: string): string {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;")
}

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

            const baseClasses = "transition-all duration-150 rounded-sm cursor-pointer"
            const stateClasses = hasNote
                ? cn(
                    "bg-amber-100/80 dark:bg-amber-900/40",
                    "border-b-2 border-amber-400 dark:border-amber-500"
                )
                : cn(
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

function renderNode(
    node: TipTapNode,
    commentNoteMap: Map<string, string>
): string {
    if (node.type === "text") {
        let text = escapeHtml(node.text || "")
        if (node.marks) {
            for (const mark of node.marks) {
                text = applyMark(text, mark, commentNoteMap)
            }
        }
        return text
    }

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

function escapeRegex(str: string): string {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
}

function highlightAnchorTexts(
    html: string,
    notes: InterviewNoteRead[]
): string {
    let result = html

    for (const note of notes) {
        if (!note.anchor_text || !note.comment_id) continue
        if (result.includes(`data-comment-id="${note.comment_id}"`)) continue

        const baseClasses = "transition-all duration-150 rounded-sm cursor-pointer"
        const stateClasses = cn(
            "bg-amber-100/80 dark:bg-amber-900/40",
            "border-b-2 border-amber-400 dark:border-amber-500"
        )

        const safeAnchorText = escapeHtml(note.anchor_text)
        const escapedAnchor = escapeRegex(safeAnchorText)
        const regex = new RegExp(`(?<!data-comment-id[^>]*>)${escapedAnchor}(?![^<]*</span>)`, "")
        const replacement = `<span class="comment-highlight ${baseClasses} ${stateClasses}" data-comment-id="${escapeHtml(note.comment_id)}" data-note-id="${escapeHtml(note.id)}">${safeAnchorText}</span>`

        result = result.replace(regex, replacement)
    }

    return result
}

function renderTranscript(
    doc: TipTapDoc | null,
    notes: InterviewNoteRead[],
    commentNoteMap: Map<string, string>
): string {
    if (!doc?.content) return ""

    let html = doc.content
        .map((node) => renderNode(node, commentNoteMap))
        .join("")

    html = highlightAnchorTexts(html, notes)

    return html
}

// ============================================================================
// Main Component Props
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

// ============================================================================
// Main Component
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

    // Build comment-to-note mapping and render transcript
    const commentNoteMap = useMemo(() => buildCommentNoteMap(notes), [notes])
    const transcriptHtml = useMemo(
        () => renderTranscript(interview.transcript_json, notes, commentNoteMap),
        [interview.transcript_json, notes, commentNoteMap]
    )

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

    return (
        <InterviewCommentsProvider
            interview={interview}
            notes={notes}
            onAddNote={onAddNote}
            onUpdateNote={onUpdateNote}
            onDeleteNote={onDeleteNote}
            canEdit={canEdit}
            isMobile={isMobile}
            transcriptHtml={transcriptHtml}
        >
            {isMobile ? (
                <MobileLayout className={className} />
            ) : (
                <DesktopLayout className={className} />
            )}
        </InterviewCommentsProvider>
    )
}
