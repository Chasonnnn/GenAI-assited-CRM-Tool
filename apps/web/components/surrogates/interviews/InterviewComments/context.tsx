"use client"

import * as React from "react"
import { createContext, use, useState, useCallback, useRef, useMemo } from "react"
import type {
    InterviewRead,
    InterviewNoteRead,
} from "@/lib/api/interviews"

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
    transcriptRef: React.RefObject<HTMLDivElement | null>
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
    const transcriptRef = useRef<HTMLDivElement>(null)
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
    const commentNoteMap = useMemo(() => buildCommentNoteMap(notes), [notes])
    const anchoredNotes = useMemo(
        () => notes.filter((n) => n.comment_id || n.anchor_text),
        [notes]
    )
    const generalNotes = useMemo(
        () => notes.filter((n) => !n.comment_id && !n.anchor_text),
        [notes]
    )

    const activeNoteId = useMemo(() => {
        if (interaction.type !== "focused") return null
        return commentNoteMap.get(interaction.commentId) ?? null
    }, [interaction, commentNoteMap])

    // Interaction helpers
    const setHoveredCommentId = useCallback((commentId: string | null) => {
        if (commentId) {
            setInteraction({ type: "hovering", commentId })
        } else if (interaction.type === "hovering") {
            setInteraction({ type: "idle" })
        }
    }, [interaction.type])

    const setFocusedCommentId = useCallback((commentId: string | null) => {
        if (commentId) {
            setInteraction({ type: "focused", commentId })
        } else {
            setInteraction({ type: "idle" })
        }
    }, [])

    // Position calculation
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
    }, [anchoredNotes, newComment])

    // Comment actions
    const startPendingComment = useCallback(
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
            const anchorText = firstLine.replace(/\s+/g, " ").trim()

            setNewComment({
                type: "pending",
                text: anchorText,
                commentId,
                anchorTop,
                anchorLeft,
            })
        },
        []
    )

    const cancelPendingComment = useCallback(() => {
        setNewComment({ type: "none" })
    }, [])

    const startAddingGeneralNote = useCallback(() => {
        setNewComment({ type: "adding_general" })
    }, [])

    const cancelAddingGeneralNote = useCallback(() => {
        setNewComment({ type: "none" })
        setNewNoteContent("")
    }, [])

    // Mutations
    const submitComment = useCallback(
        async (content: string) => {
            if (newComment.type !== "pending" || !content.trim()) return

            setIsSubmitting(true)
            try {
                await onAddNote({
                    content: content.trim(),
                    commentId: newComment.commentId,
                    anchorText: newComment.text,
                })
                setNewComment({ type: "none" })
            } finally {
                setIsSubmitting(false)
            }
        },
        [newComment, onAddNote]
    )

    const submitGeneralNote = useCallback(async () => {
        if (!newNoteContent.trim()) return

        setIsSubmitting(true)
        try {
            await onAddNote({
                content: newNoteContent.trim(),
                commentId: "",
                anchorText: "",
            })
            setNewNoteContent("")
            setNewComment({ type: "none" })
        } finally {
            setIsSubmitting(false)
        }
    }, [newNoteContent, onAddNote])

    const submitReply = useCallback(
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

    const updateNote = useCallback(
        async (noteId: string, content: string) => {
            await onUpdateNote(noteId, content)
        },
        [onUpdateNote]
    )

    const deleteNote = useCallback(
        async (noteId: string) => {
            await onDeleteNote(noteId)
        },
        [onDeleteNote]
    )

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

export function getMinSidebarHeight(positions: CommentPosition[]): number {
    if (positions.length === 0) return 100
    let maxBottom = 0
    for (const position of positions) {
        maxBottom = Math.max(maxBottom, position.top + position.height)
    }
    return maxBottom + 40
}
