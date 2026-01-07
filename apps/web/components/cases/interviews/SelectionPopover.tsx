"use client"

/**
 * SelectionPopover - Floating button that appears on text selection.
 *
 * When the user selects text in the transcript, this popover appears
 * near the selection with an "Add Comment" button. Clicking it triggers
 * the comment creation flow.
 */

import { useCallback, useEffect, useState, useRef } from "react"
import { createPortal } from "react-dom"
import { Button } from "@/components/ui/button"
import { MessageSquarePlusIcon } from "lucide-react"
import { cn } from "@/lib/utils"

interface SelectionPopoverProps {
    containerRef: React.RefObject<HTMLElement | null>
    onAddComment: (selection: { text: string; range: Range }) => void
    disabled?: boolean
    onSelectionStateChange?: (active: boolean) => void
}

interface PopoverPosition {
    x: number
    y: number
    visible: boolean
}

export function SelectionPopover({
    containerRef,
    onAddComment,
    disabled = false,
    onSelectionStateChange,
}: SelectionPopoverProps) {
    const [position, setPosition] = useState<PopoverPosition>({ x: 0, y: 0, visible: false })
    const [selectedText, setSelectedText] = useState("")
    const [selectedRange, setSelectedRange] = useState<Range | null>(null)
    const popoverRef = useRef<HTMLDivElement>(null)
    const isClickingPopover = useRef(false)
    const isMouseDownRef = useRef(false)
    const selectionActiveRef = useRef(false)

    const setSelectionActive = useCallback((active: boolean) => {
        if (selectionActiveRef.current === active) return
        selectionActiveRef.current = active
        onSelectionStateChange?.(active)
    }, [onSelectionStateChange])

    // Handle text selection within the container
    const handleSelectionChange = useCallback(() => {
        // Don't update if we're clicking the popover or dragging selection
        if (isClickingPopover.current || isMouseDownRef.current) return

        if (disabled) {
            setSelectionActive(false)
            return
        }

        const selection = window.getSelection()
        if (!selection || selection.isCollapsed) {
            setPosition({ x: 0, y: 0, visible: false })
            setSelectedText("")
            setSelectedRange(null)
            setSelectionActive(false)
            return
        }

        const text = selection.toString().trim()
        if (text.length < 3) {
            setPosition({ x: 0, y: 0, visible: false })
            setSelectedText("")
            setSelectedRange(null)
            setSelectionActive(false)
            return
        }

        // Check if selection is within our container
        const container = containerRef.current
        if (!container) {
            setPosition({ x: 0, y: 0, visible: false })
            setSelectionActive(false)
            return
        }

        const range = selection.getRangeAt(0)
        const ancestor = range.commonAncestorContainer
        const ancestorElement = ancestor.nodeType === Node.TEXT_NODE
            ? ancestor.parentElement
            : ancestor as Element

        if (!ancestorElement || !container.contains(ancestorElement)) {
            setPosition({ x: 0, y: 0, visible: false })
            setSelectionActive(false)
            return
        }

        // Get position for the popover
        const rects = range.getClientRects()
        if (rects.length === 0) {
            setPosition({ x: 0, y: 0, visible: false })
            setSelectionActive(false)
            return
        }

        // Use the first rect (first line of selection)
        const firstRect = rects[0]

        setPosition({
            x: firstRect.left + firstRect.width / 2,
            y: firstRect.top,
            visible: true,
        })
        setSelectedText(text)
        setSelectedRange(range.cloneRange())
        setSelectionActive(true)
    }, [containerRef, disabled, setSelectionActive])

    // Listen for selection changes
    useEffect(() => {
        document.addEventListener("selectionchange", handleSelectionChange)
        return () => {
            document.removeEventListener("selectionchange", handleSelectionChange)
        }
    }, [handleSelectionChange])

    // Handle keyboard shortcuts
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape" && position.visible) {
                setPosition({ x: 0, y: 0, visible: false })
                window.getSelection()?.removeAllRanges()
            }
        }

        document.addEventListener("keydown", handleKeyDown)
        return () => {
            document.removeEventListener("keydown", handleKeyDown)
        }
    }, [position.visible])

    // Handle click outside
    useEffect(() => {
        const handleMouseDown = (e: MouseEvent) => {
            isMouseDownRef.current = true
            const target = e.target as HTMLElement
            const popover = popoverRef.current
            if (popover && popover.contains(target)) {
                isClickingPopover.current = true
                return
            }
            // Let selection change handler deal with it
            isClickingPopover.current = false
        }

        const handleMouseUp = () => {
            isMouseDownRef.current = false
            handleSelectionChange()
            // Reset after a short delay
            setTimeout(() => {
                isClickingPopover.current = false
            }, 100)
        }

        document.addEventListener("mousedown", handleMouseDown)
        document.addEventListener("mouseup", handleMouseUp)
        return () => {
            document.removeEventListener("mousedown", handleMouseDown)
            document.removeEventListener("mouseup", handleMouseUp)
        }
    }, [])

    const handleAddComment = useCallback(() => {
        if (!selectedText || !selectedRange) return

        onAddComment({
            text: selectedText,
            range: selectedRange,
        })

        // Clear selection
        setPosition({ x: 0, y: 0, visible: false })
        setSelectedText("")
        setSelectedRange(null)
        window.getSelection()?.removeAllRanges()
        setSelectionActive(false)
    }, [selectedText, selectedRange, onAddComment, setSelectionActive])

    // Don't render if not visible or disabled
    if (!position.visible || disabled) return null

    // Render in portal to avoid z-index issues
    return createPortal(
        <div
            ref={popoverRef}
            className={cn(
                "fixed z-50 transform -translate-x-1/2",
                "animate-in fade-in-0 zoom-in-95 slide-in-from-bottom-2",
                "duration-150"
            )}
            style={{
                left: position.x,
                top: position.y - 8,
                transform: "translate(-50%, -100%)",
            }}
        >
            <Button
                size="sm"
                onClick={handleAddComment}
                className={cn(
                    "shadow-lg gap-1.5 rounded-full px-3.5 h-8",
                    "bg-teal-600 hover:bg-teal-700 text-white",
                    "dark:bg-teal-600 dark:hover:bg-teal-500",
                    "transition-all duration-150",
                    "hover:scale-105 hover:shadow-xl"
                )}
            >
                <MessageSquarePlusIcon className="size-3.5" />
                <span className="text-xs font-medium">Add Comment</span>
            </Button>
            {/* Pointer arrow */}
            <div
                className={cn(
                    "absolute left-1/2 -translate-x-1/2 -bottom-1.5",
                    "w-3 h-3 rotate-45",
                    "bg-teal-600 dark:bg-teal-600"
                )}
            />
        </div>,
        document.body
    )
}
