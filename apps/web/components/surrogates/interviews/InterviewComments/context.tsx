"use client"

import * as React from "react"
import { createContext, use, useState, useRef } from "react"
import type {
    InterviewRead,
    InterviewNoteRead,
} from "@/lib/api/interviews"
import { getMinSidebarHeight } from "./comment-layout"

// ============================================================================
// Types
// ============================================================================

export type CommentInteraction =
    | { type: "idle" }
    | { type: "hovering"; commentId: string }
    | { type: "focused"; commentId: string }

export type NewCommentState =
    | { type: "none" }
    | { type: "pending"; text: string; commentId: string; anchorTop: number; anchorLeft: number }
    | { type: "adding_general" }

export interface CommentPosition {
    noteId: string
    top: number
    anchorTop: number
    anchorLeft: number
    cardLeft: number
    height: number
}

export interface InterviewCommentsContextValue {
    // Data
    interview: InterviewRead
    notes: InterviewNoteRead[]
    anchoredNotes: InterviewNoteRead[]
    generalNotes: InterviewNoteRead[]
    commentNoteMap: Map<string, string>

    // State
    interaction: CommentInteraction
    newComment: NewCommentState
    isSubmitting: boolean
    commentPositions: CommentPosition[]
    layoutMinHeight: number

    // Refs
    transcriptRef: React.RefObject<HTMLElement | null>
    commentSidebarRef: React.RefObject<HTMLDivElement | null>
    layoutRef: React.RefObject<HTMLDivElement | null>
    scrollContainerRef: React.RefObject<HTMLDivElement | null>
    isSelectingRef: React.RefObject<boolean>

    // Interaction actions
    setInteraction: (interaction: CommentInteraction) => void
    setHoveredCommentId: (commentId: string | null) => void
    setFocusedCommentId: (commentId: string | null) => void

    // Comment actions
    startPendingComment: (selection: { text: string; range: Range }) => void
    cancelPendingComment: () => void
    startAddingGeneralNote: () => void
    cancelAddingGeneralNote: () => void
    setNewNoteContent: (content: string) => void
    newNoteContent: string

    // Mutations
    submitComment: (content: string) => Promise<void>
    submitGeneralNote: () => Promise<void>
    submitReply: (noteId: string, content: string) => Promise<void>
    updateNote: (noteId: string, content: string) => Promise<void>
    deleteNote: (noteId: string) => Promise<void>

    // Position management
    calculatePositions: () => void
    setCommentPositions: React.Dispatch<React.SetStateAction<CommentPosition[]>>
    setLayoutMinHeight: React.Dispatch<React.SetStateAction<number>>

    // Meta
    canEdit: boolean
    isMobile: boolean
    transcriptHtml: string
    activeNoteId: string | null
}

// ============================================================================
// Context
// ============================================================================

const InterviewCommentsContext = createContext<InterviewCommentsContextValue | null>(null)

export function useInterviewComments() {
    const context = use(InterviewCommentsContext)
    if (!context) {
        throw new Error("useInterviewComments must be used within an InterviewCommentsProvider")
    }
    return context
}

// ============================================================================
// Helper functions
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

type MutationResult = { ok: true } | { ok: false; error: unknown }

function resolveMutationResult(promise: Promise<void>): Promise<MutationResult> {
    return promise.then(
        () => ({ ok: true as const }),
        (error: unknown) => ({ ok: false as const, error })
    )
}

function throwMutationError(error: unknown): never {
    throw error
}

// ============================================================================
// Provider Props
// ============================================================================

interface InterviewCommentsProviderProps {
    interview: InterviewRead
    notes: InterviewNoteRead[]
    onAddNote: (data: {
        content: string
        commentId: string
        anchorText: string
        parentId?: string
    }) => Promise<void>
    onUpdateNote: (noteId: string, content: string) => Promise<void>
    onDeleteNote: (noteId: string) => Promise<void>
    canEdit: boolean
    isMobile: boolean
    transcriptHtml: string
    children: React.ReactNode
}

// ============================================================================
// Provider
// ============================================================================

export function InterviewCommentsProvider({
    interview,
    notes,
    onAddNote,
    onUpdateNote,
    onDeleteNote,
    canEdit,
    isMobile,
    transcriptHtml,
    children,
}: InterviewCommentsProviderProps) {
    // Refs
    const transcriptRef = useRef<HTMLElement>(null)
    const commentSidebarRef = useRef<HTMLDivElement>(null)
    const layoutRef = useRef<HTMLDivElement>(null)
    const scrollContainerRef = useRef<HTMLDivElement>(null)
    const isSelectingRef = useRef(false)

    // State - consolidated from multiple booleans
    const [interaction, setInteraction] = useState<CommentInteraction>({ type: "idle" })
    const [newComment, setNewComment] = useState<NewCommentState>({ type: "none" })
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [newNoteContent, setNewNoteContent] = useState("")
    const [commentPositions, setCommentPositions] = useState<CommentPosition[]>([])
    const [layoutMinHeight, setLayoutMinHeight] = useState(0)

    // Derived data
    const commentNoteMap = buildCommentNoteMap(notes)
    const anchoredNotes = notes.filter((n) => n.comment_id || n.anchor_text)
    const generalNotes = notes.filter((n) => !n.comment_id && !n.anchor_text)
    const activeNoteId = interaction.type === "focused"
        ? commentNoteMap.get(interaction.commentId) ?? null
        : null

    // Interaction helpers
    const setHoveredCommentId = (commentId: string | null) => {
        if (commentId) {
            setInteraction({ type: "hovering", commentId })
        } else if (interaction.type === "hovering") {
            setInteraction({ type: "idle" })
        }
    }

    const setFocusedCommentId = (commentId: string | null) => {
        if (commentId) {
            setInteraction({ type: "focused", commentId })
        } else {
            setInteraction({ type: "idle" })
        }
    }

    // Position calculation
    const calculatePositions = () => {
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
                anchorTop: topOffset,
                anchorLeft,
                cardLeft: sidebarLeft,
                height: 0,
            })
        }

        // Add pending comment position
        if (newComment.type === "pending") {
            positions.push({
                noteId: newComment.commentId,
                top: newComment.anchorTop,
                anchorTop: newComment.anchorTop,
                anchorLeft: newComment.anchorLeft || fallbackAnchorLeft,
                cardLeft: sidebarLeft,
                height: 0,
            })
        }

        // Measure card heights
        for (const position of positions) {
            const cardEl = commentSidebarRef.current?.querySelector<HTMLElement>(
                `[data-note-id="${position.noteId}"]`
            )
            position.height = cardEl?.offsetHeight || 140
        }

        // Sort and avoid collisions
        positions.sort((a, b) => {
            const delta = a.anchorTop - b.anchorTop
            return delta !== 0 ? delta : a.noteId.localeCompare(b.noteId)
        })
        avoidCollisions(positions)

        setCommentPositions(positions)

        const commentsHeight = getMinSidebarHeight(positions)
        const transcriptHeight = transcriptRef.current?.scrollHeight ?? 0
        setLayoutMinHeight(Math.max(commentsHeight, transcriptHeight, 200))
    }

    // Comment actions
    const startPendingComment = (selection: { text: string; range: Range }) => {
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
        const anchorText = firstLine.replace(/\s+/g, " ").trim()

        setNewComment({
            type: "pending",
            text: anchorText,
            commentId,
            anchorTop,
            anchorLeft,
        })
    }

    const cancelPendingComment = () => {
        setNewComment({ type: "none" })
    }

    const startAddingGeneralNote = () => {
        setNewComment({ type: "adding_general" })
    }

    const cancelAddingGeneralNote = () => {
        setNewComment({ type: "none" })
        setNewNoteContent("")
    }

    // Mutations
    const submitComment = async (content: string) => {
        if (newComment.type !== "pending" || !content.trim()) return

        setIsSubmitting(true)
        const result = await resolveMutationResult(onAddNote({
            content: content.trim(),
            commentId: newComment.commentId,
            anchorText: newComment.text,
        }))
        setIsSubmitting(false)
        if (!result.ok) {
            throwMutationError(result.error)
        }
        setNewComment({ type: "none" })
    }

    const submitGeneralNote = async () => {
        if (!newNoteContent.trim()) return

        setIsSubmitting(true)
        const result = await resolveMutationResult(onAddNote({
            content: newNoteContent.trim(),
            commentId: "",
            anchorText: "",
        }))
        setIsSubmitting(false)
        if (!result.ok) {
            throwMutationError(result.error)
        }
        setNewNoteContent("")
        setNewComment({ type: "none" })
    }

    const submitReply = async (noteId: string, content: string) => {
        const parentNote = notes.find((n) => n.id === noteId)
        if (!parentNote) return

        setIsSubmitting(true)
        const result = await resolveMutationResult(onAddNote({
            content,
            commentId: "",
            anchorText: "",
            parentId: noteId,
        }))
        setIsSubmitting(false)
        if (!result.ok) {
            throwMutationError(result.error)
        }
    }

    const updateNote = async (noteId: string, content: string) => {
        await onUpdateNote(noteId, content)
    }

    const deleteNote = async (noteId: string) => {
        await onDeleteNote(noteId)
    }

    const value: InterviewCommentsContextValue = {
        // Data
        interview,
        notes,
        anchoredNotes,
        generalNotes,
        commentNoteMap,

        // State
        interaction,
        newComment,
        isSubmitting,
        commentPositions,
        layoutMinHeight,

        // Refs
        transcriptRef,
        commentSidebarRef,
        layoutRef,
        scrollContainerRef,
        isSelectingRef,

        // Interaction actions
        setInteraction,
        setHoveredCommentId,
        setFocusedCommentId,

        // Comment actions
        startPendingComment,
        cancelPendingComment,
        startAddingGeneralNote,
        cancelAddingGeneralNote,
        setNewNoteContent,
        newNoteContent,

        // Mutations
        submitComment,
        submitGeneralNote,
        submitReply,
        updateNote,
        deleteNote,

        // Position management
        calculatePositions,
        setCommentPositions,
        setLayoutMinHeight,

        // Meta
        canEdit,
        isMobile,
        transcriptHtml,
        activeNoteId,
    }

    return (
        <InterviewCommentsContext.Provider value={value}>
            {children}
        </InterviewCommentsContext.Provider>
    )
}

// ============================================================================
// Helpers
// ============================================================================

function avoidCollisions(positions: CommentPosition[]) {
    const MIN_GAP = 12

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
