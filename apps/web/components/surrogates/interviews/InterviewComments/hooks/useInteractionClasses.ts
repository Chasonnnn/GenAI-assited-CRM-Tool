"use client"

import { useEffect, useRef } from "react"
import type { CommentInteraction } from "../context"

const COMMENT_HOVER_CLASSES = "bg-amber-200 dark:bg-amber-800/50"
const COMMENT_FOCUS_CLASSES =
    "bg-amber-300 dark:bg-amber-700/60 ring-2 ring-amber-400 ring-offset-1"

/**
 * Hook to manage DOM class toggling for comment highlight interactions.
 * Handles adding/removing hover and focus classes from comment spans.
 */
export function useInteractionClasses(
    transcriptRef: React.RefObject<HTMLDivElement | null>,
    interaction: CommentInteraction
) {
    const prevHoveredRef = useRef<string | null>(null)
    const prevFocusedRef = useRef<string | null>(null)

    const toggleSpanClasses = (
        commentId: string,
        classNames: string,
        enabled: boolean
    ) => {
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
    }

    // Handle hover classes
    useEffect(() => {
        const currentHovered = interaction.type === "hovering" ? interaction.commentId : null
        const prev = prevHoveredRef.current

        if (prev && prev !== currentHovered) {
            toggleSpanClasses(prev, COMMENT_HOVER_CLASSES, false)
        }
        if (currentHovered) {
            toggleSpanClasses(currentHovered, COMMENT_HOVER_CLASSES, true)
        }
        prevHoveredRef.current = currentHovered
    }, [interaction])

    // Handle focus classes
    useEffect(() => {
        const currentFocused = interaction.type === "focused" ? interaction.commentId : null
        const prev = prevFocusedRef.current

        if (prev && prev !== currentFocused) {
            toggleSpanClasses(prev, COMMENT_FOCUS_CLASSES, false)
        }
        if (currentFocused) {
            toggleSpanClasses(currentFocused, COMMENT_FOCUS_CLASSES, true)
        }
        prevFocusedRef.current = currentFocused
    }, [interaction])
}
