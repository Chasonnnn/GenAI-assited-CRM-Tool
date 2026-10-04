"use client"

import { useEffect, useRef, useState } from "react"
import type { PointerEvent as ReactPointerEvent, RefObject } from "react"

/** Pixels the pointer must travel before a press becomes a drag instead of a click. */
const DRAG_THRESHOLD = 4
/** Distance from the canvas edge that scrolls it while dragging. */
const AUTO_SCROLL_EDGE = 56
const AUTO_SCROLL_STEP = 14

export type StepDragSource =
    | { kind: "palette"; actionType: string }
    | { kind: "step"; index: number }

export type StepDrag = {
    source: StepDragSource
    label: string
    pointer: { x: number; y: number }
    /** Insertion slot: 0 is before the first step, actions.length is after the last. Null is off canvas. */
    slot: number | null
}

/**
 * Pointer drag for adding steps from the palette and reordering steps on the canvas. A press
 * that never passes the threshold stays a normal click. Escape cancels.
 */
export function useStepDrag({
    canvasRef,
    onInsert,
    onReorder,
}: {
    canvasRef: RefObject<HTMLElement | null>
    onInsert: (actionType: string, slot: number) => void
    onReorder: (from: number, to: number) => void
}) {
    const [drag, setDrag] = useState<StepDrag | null>(null)
    const stopRef = useRef<(() => void) | null>(null)

    useEffect(() => () => stopRef.current?.(), [])

    const slotAt = (x: number, y: number): number | null => {
        const canvas = canvasRef.current
        if (!canvas) return null
        const bounds = canvas.getBoundingClientRect()
        if (x < bounds.left || x > bounds.right || y < bounds.top || y > bounds.bottom) return null
        const steps = Array.from(canvas.querySelectorAll<HTMLElement>("[data-step-index]"))
        let slot = 0
        for (const step of steps) {
            const rect = step.getBoundingClientRect()
            if (y > rect.top + rect.height / 2) slot = Number(step.dataset.stepIndex) + 1
        }
        return slot
    }

    const autoScroll = (y: number) => {
        const canvas = canvasRef.current
        if (!canvas) return
        const bounds = canvas.getBoundingClientRect()
        if (y < bounds.top + AUTO_SCROLL_EDGE) canvas.scrollBy({ top: -AUTO_SCROLL_STEP })
        else if (y > bounds.bottom - AUTO_SCROLL_EDGE) canvas.scrollBy({ top: AUTO_SCROLL_STEP })
    }

    const begin = (event: ReactPointerEvent, source: StepDragSource, label: string) => {
        if (event.button !== 0 || event.pointerType === "touch") return
        stopRef.current?.()
        const startX = event.clientX
        const startY = event.clientY
        let active = false
        let latest: StepDrag | null = null

        const handleMove = (move: PointerEvent) => {
            if (!active) {
                if (Math.hypot(move.clientX - startX, move.clientY - startY) < DRAG_THRESHOLD) return
                active = true
            }
            autoScroll(move.clientY)
            latest = {
                source,
                label,
                pointer: { x: move.clientX, y: move.clientY },
                slot: slotAt(move.clientX, move.clientY),
            }
            setDrag(latest)
        }
        const finish = (commit: boolean) => {
            stop()
            setDrag(null)
            if (!active) return
            // The release can land on the pressed element and fire a click; a drag is not a click.
            const swallow = (click: MouseEvent) => {
                click.preventDefault()
                click.stopPropagation()
            }
            window.addEventListener("click", swallow, { capture: true, once: true })
            window.setTimeout(() => window.removeEventListener("click", swallow, { capture: true }), 0)
            if (!commit || !latest || latest.slot === null) return
            if (source.kind === "palette") {
                onInsert(source.actionType, latest.slot)
                return
            }
            const to = latest.slot > source.index ? latest.slot - 1 : latest.slot
            if (to !== source.index) onReorder(source.index, to)
        }
        const handleUp = () => finish(true)
        const handleCancel = () => finish(false)
        const handleKey = (key: KeyboardEvent) => {
            if (key.key === "Escape" && active) {
                key.preventDefault()
                finish(false)
            }
        }
        function stop() {
            window.removeEventListener("pointermove", handleMove)
            window.removeEventListener("pointerup", handleUp)
            window.removeEventListener("pointercancel", handleCancel)
            window.removeEventListener("keydown", handleKey, { capture: true })
            stopRef.current = null
        }
        window.addEventListener("pointermove", handleMove)
        window.addEventListener("pointerup", handleUp)
        window.addEventListener("pointercancel", handleCancel)
        window.addEventListener("keydown", handleKey, { capture: true })
        stopRef.current = stop
    }

    return { drag, begin }
}
