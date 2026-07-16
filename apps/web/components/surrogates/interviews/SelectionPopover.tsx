"use client"

/**
 * SelectionPopover - Floating button that appears on text selection.
 *
 * When the user selects text in the transcript, this popover appears
 * near the selection with an "Add Comment" button. Clicking it triggers
 * the comment creation flow.
 */

import { useEffect, useEffectEvent, useState, useRef } from "react"
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

function useSelectionPopoverDocumentListeners({
    containerRef,
    disabled,
    onSelectionStateChange,
    positionVisible,
    setPosition,
    selectedTextRef,
    selectedRangeRef,
    selectionActiveRef,
    popoverRef,
    isClickingPopover,
    isMouseDownRef,
}: {
    containerRef: React.RefObject<HTMLElement | null>
    disabled: boolean
    onSelectionStateChange: ((active: boolean) => void) | undefined
    positionVisible: boolean
    setPosition: React.Dispatch<React.SetStateAction<PopoverPosition>>
    selectedTextRef: React.RefObject<string>
    selectedRangeRef: React.RefObject<Range | null>
    selectionActiveRef: React.RefObject<boolean>
    popoverRef: React.RefObject<HTMLDivElement | null>
    isClickingPopover: React.RefObject<boolean>
    isMouseDownRef: React.RefObject<boolean>
}) {
    const setSelectionActive = (active: boolean) => {
        if (selectionActiveRef.current === active) return
        selectionActiveRef.current = active
        onSelectionStateChange?.(active)
    }

    const handleSelectionChange = useEffectEvent(() => {
        if (isClickingPopover.current || isMouseDownRef.current) return
        if (disabled) {
            setSelectionActive(false)
            return
        }

        const selection = window.getSelection()
        if (!selection || selection.isCollapsed) {
            setPosition({ x: 0, y: 0, visible: false })
            selectedTextRef.current = ""
            selectedRangeRef.current = null
            setSelectionActive(false)
            return
        }

        const text = selection.toString().trim()
        if (text.length < 3) {
            setPosition({ x: 0, y: 0, visible: false })
            selectedTextRef.current = ""
            selectedRangeRef.current = null
            setSelectionActive(false)
            return
        }

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

        const firstRect = range.getClientRects()[0]
        if (!firstRect) {
            setPosition({ x: 0, y: 0, visible: false })
            setSelectionActive(false)
            return
        }

        setPosition({
            x: firstRect.left + firstRect.width / 2,
            y: firstRect.top,
            visible: true,
        })
        selectedTextRef.current = text
        selectedRangeRef.current = range.cloneRange()
        setSelectionActive(true)
    })

    const handleDocumentKeyDown = useEffectEvent((event: KeyboardEvent) => {
        if (event.key === "Escape" && positionVisible) {
            setPosition({ x: 0, y: 0, visible: false })
            window.getSelection()?.removeAllRanges()
        }
    })

    useEffect(() => {
        let clickResetTimeout: ReturnType<typeof setTimeout> | null = null
        const handleDocumentSelectionChange = () => handleSelectionChange()
        const handleMouseDown = (event: MouseEvent) => {
            isMouseDownRef.current = true
            const target = event.target as HTMLElement
            const popover = popoverRef.current
            if (popover && popover.contains(target)) {
                isClickingPopover.current = true
                return
            }
            isClickingPopover.current = false
        }

        const handleMouseUp = () => {
            isMouseDownRef.current = false
            handleSelectionChange()
            if (clickResetTimeout) clearTimeout(clickResetTimeout)
            clickResetTimeout = setTimeout(() => {
                isClickingPopover.current = false
            }, 100)
        }

        document.addEventListener("selectionchange", handleDocumentSelectionChange)
        document.addEventListener("keydown", handleDocumentKeyDown)
        document.addEventListener("mousedown", handleMouseDown)
        document.addEventListener("mouseup", handleMouseUp)
        return () => {
            document.removeEventListener("selectionchange", handleDocumentSelectionChange)
            document.removeEventListener("keydown", handleDocumentKeyDown)
            document.removeEventListener("mousedown", handleMouseDown)
            document.removeEventListener("mouseup", handleMouseUp)
            if (clickResetTimeout) clearTimeout(clickResetTimeout)
        }
    }, [isClickingPopover, isMouseDownRef, popoverRef])
}

export function SelectionPopover({
    containerRef,
    onAddComment,
    disabled = false,
    onSelectionStateChange,
}: SelectionPopoverProps) {
    const [position, setPosition] = useState<PopoverPosition>({ x: 0, y: 0, visible: false })
    const selectedTextRef = useRef("")
    const selectedRangeRef = useRef<Range | null>(null)
    const popoverRef = useRef<HTMLDivElement>(null)
    const isClickingPopover = useRef(false)
    const isMouseDownRef = useRef(false)
    const selectionActiveRef = useRef(false)

    useSelectionPopoverDocumentListeners({
        containerRef,
        disabled,
        onSelectionStateChange,
        positionVisible: position.visible,
        setPosition,
        selectedTextRef,
        selectedRangeRef,
        selectionActiveRef,
        popoverRef,
        isClickingPopover,
        isMouseDownRef,
    })

    const handleAddComment = () => {
        const selectedText = selectedTextRef.current
        const selectedRange = selectedRangeRef.current
        if (!selectedText || !selectedRange) return

        onAddComment({
            text: selectedText,
            range: selectedRange,
        })

        // Clear selection
        setPosition({ x: 0, y: 0, visible: false })
        selectedTextRef.current = ""
        selectedRangeRef.current = null
        window.getSelection()?.removeAllRanges()
        if (selectionActiveRef.current) {
            selectionActiveRef.current = false
            onSelectionStateChange?.(false)
        }
    }

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
                <MessageSquarePlusIcon className="size-3.5" aria-hidden="true" />
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
