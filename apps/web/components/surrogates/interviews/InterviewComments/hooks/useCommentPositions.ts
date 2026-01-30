"use client"

import { useEffect } from "react"
import { useInterviewComments } from "../context"

/**
 * Hook to manage comment position calculations and recalculations.
 * Sets up resize observers and scroll handlers to keep positions in sync.
 */
export function useCommentPositions() {
    const {
        calculatePositions,
        transcriptRef,
        scrollContainerRef,
        commentSidebarRef,
        anchoredNotes,
        newComment,
        transcriptHtml,
    } = useInterviewComments()

    // Recalculate positions on mount and resize
    useEffect(() => {
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
    }, [calculatePositions, transcriptRef])

    // Recalculate when transcript HTML changes
    useEffect(() => {
        const raf = window.requestAnimationFrame(() => {
            calculatePositions()
        })
        return () => {
            window.cancelAnimationFrame(raf)
        }
    }, [calculatePositions, transcriptHtml])

    // Recalculate on scroll
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
    }, [calculatePositions, scrollContainerRef])

    // Recalculate when comment cards resize
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
    }, [calculatePositions, commentSidebarRef, anchoredNotes, newComment])
}
