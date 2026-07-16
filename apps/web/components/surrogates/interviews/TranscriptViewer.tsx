"use client"

/**
 * TranscriptViewer - Read-only transcript display with anchored note support.
 *
 * Features:
 * - Renders transcript HTML with selectable text
 * - Floating "Add Note" button appears on text selection
 * - Highlights text ranges that have anchored notes (via comment marks)
 * - Click on highlighted text to scroll to note in sidebar
 */

import { useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { MessageSquarePlusIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { SafeHtmlContent } from "@/components/safe-html-content"
import type { TipTapDoc, TipTapNode, TipTapMark, InterviewNoteRead } from "@/lib/api/interviews"
import { useTranscriptViewerListeners } from "@/lib/hooks/use-transcript-viewer-listeners"

interface TranscriptViewerProps {
    transcriptHtml: string | null
    transcriptJson: TipTapDoc | null
    notes: InterviewNoteRead[]
    onAddNote: (selection: { text: string; commentId: string }) => void
    onNoteClick?: (noteId: string) => void
    className?: string
}

interface SelectionPosition {
    x: number
    y: number
    text: string
}

/**
 * Generate a unique comment ID for new notes
 */
function generateCommentId(): string {
    return crypto.randomUUID()
}

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
 * Convert TipTap JSON to HTML with comment highlighting
 */
function renderTranscriptWithHighlights(
    doc: TipTapDoc | null,
    commentNoteMap: Map<string, string>,
    onNoteClick?: (noteId: string) => void
): string {
    if (!doc?.content) return ""

    function renderNode(node: TipTapNode): string {
        if (node.type === "text") {
            let text = escapeHtml(node.text || "")

            // Apply marks
            if (node.marks) {
                for (const mark of node.marks) {
                    text = applyMark(text, mark, commentNoteMap, onNoteClick)
                }
            }

            return text
        }

        // Handle different node types
        const children = node.content?.map(renderNode).join("") || ""

        switch (node.type) {
            case "doc":
                return children
            case "paragraph":
                return `<p>${children}</p>`
            case "heading": {
                const level = (node.attrs?.level as number) || 1
                return `<h${level}>${children}</h${level}>`
            }
            case "bulletList":
                return `<ul>${children}</ul>`
            case "orderedList":
                return `<ol>${children}</ol>`
            case "listItem":
                return `<li>${children}</li>`
            case "blockquote":
                return `<blockquote>${children}</blockquote>`
            case "codeBlock":
                return `<pre><code>${children}</code></pre>`
            case "hardBreak":
                return "<br/>"
            case "horizontalRule":
                return "<hr/>"
            default:
                return children
        }
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
        commentNoteMap: Map<string, string>,
        _onNoteClick?: (noteId: string) => void
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
                return `<code>${text}</code>`
            case "link": {
                const href = (mark.attrs?.href as string) || "#"
                return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer" class="text-primary underline">${text}</a>`
            }
            case "comment": {
                const commentId = mark.attrs?.commentId as string
                if (commentId && commentNoteMap.has(commentId)) {
                    const noteId = commentNoteMap.get(commentId)
                    return `<span class="transcript-comment bg-teal-100 dark:bg-teal-900/40 border-b-2 border-teal-500 cursor-pointer hover:bg-teal-200 dark:hover:bg-teal-800/50 transition-colors" data-comment-id="${escapeHtml(commentId)}" data-note-id="${escapeHtml(noteId || "")}">${text}</span>`
                }
                // Orphaned comment (note was deleted)
                return `<span class="transcript-comment-orphan bg-amber-100 dark:bg-amber-900/30 border-b-2 border-amber-400 border-dashed" data-comment-id="${escapeHtml(commentId)}">${text}</span>`
            }
            case "highlight":
                return `<mark>${text}</mark>`
            default:
                return text
        }
    }

    return doc.content.map(renderNode).join("")
}

export function TranscriptViewer({
    transcriptHtml,
    transcriptJson,
    notes,
    onAddNote,
    onNoteClick,
    className,
}: TranscriptViewerProps) {
    const containerRef = useRef<HTMLDivElement>(null)
    const [selection, setSelection] = useState<SelectionPosition | null>(null)

    // Build comment-to-note mapping
    const commentNoteMap = buildCommentNoteMap(notes)

    // Render transcript HTML with comment highlights
    const renderedHtml = transcriptJson
        ? renderTranscriptWithHighlights(transcriptJson, commentNoteMap, onNoteClick)
        : transcriptHtml || ""

    // Handle text selection
    const handleMouseUp = () => {
        const sel = window.getSelection()
        if (!sel || sel.isCollapsed || !sel.toString().trim()) {
            setSelection(null)
            return
        }

        const text = sel.toString().trim()
        if (text.length < 3) {
            setSelection(null)
            return
        }

        // Get position for floating button
        const range = sel.getRangeAt(0)
        const rect = range.getBoundingClientRect()

        setSelection({
            x: rect.left + rect.width / 2,
            y: rect.top,
            text,
        })
    }

    // Handle click on highlighted comment
    const handleClick = (e: MouseEvent) => {
        const target = e.target as HTMLElement
        if (target.classList.contains("transcript-comment")) {
            const noteId = target.dataset.noteId
            if (noteId && onNoteClick) {
                onNoteClick(noteId)
            }
        }
    }

    // Handle keyboard dismiss
    const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Escape") {
            setSelection(null)
            window.getSelection()?.removeAllRanges()
        }
    }

    useTranscriptViewerListeners({
        containerRef,
        enabled: Boolean(renderedHtml),
        onMouseUp: handleMouseUp,
        onClick: handleClick,
        onKeyDown: handleKeyDown,
    })

    // Handle add note click
    const handleAddNoteClick = () => {
        if (!selection) return

        const commentId = generateCommentId()
        onAddNote({
            text: selection.text,
            commentId,
        })

        setSelection(null)
        window.getSelection()?.removeAllRanges()
    }

    if (!renderedHtml) {
        return null
    }

    return (
        <div className="relative">
            {/* Transcript content */}
            <div ref={containerRef}>
                <SafeHtmlContent
                    html={renderedHtml}
                    className={cn(
                        "prose prose-sm max-w-none dark:prose-invert",
                        "[&_.transcript-comment]:transition-all",
                        "[&_.transcript-comment]:rounded-sm",
                        "[&_.transcript-comment-orphan]:transition-all",
                        "[&_.transcript-comment-orphan]:rounded-sm",
                        className
                    )}
                />
            </div>

            {/* Floating add note button */}
            {selection && (
                <div
                    className="fixed z-50 transform -translate-x-1/2 -translate-y-full"
                    style={{
                        left: selection.x,
                        top: selection.y - 8,
                    }}
                    data-selection-button
                >
                    <Button
                        size="sm"
                        onClick={handleAddNoteClick}
                        className="shadow-lg gap-1.5 rounded-full px-3"
                    >
                        <MessageSquarePlusIcon className="size-4" />
                        Add Note
                    </Button>
                </div>
            )}
        </div>
    )
}
