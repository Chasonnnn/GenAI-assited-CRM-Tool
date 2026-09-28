"use client"

import { useLayoutEffect, useRef, useState } from "react"

export type SaveTicket = {
    // False once the builder opened another form or a newer request finished.
    isCurrent: () => boolean
    // False while the builder is hidden or after it unmounts. Navigation and toasts wait for it.
    isActive: () => boolean
}

type SaveHandlers<Result> = {
    onSuccess: (result: Result, ticket: SaveTicket) => void
    onError: (error: unknown, ticket: SaveTicket) => void
}

// Runs a builder's autosave, Save, and Publish requests one at a time, in the order they were
// requested. Each request records the builder generation when it was requested; opening another
// form starts a new generation. A finished request applies its handlers only while its
// generation is current and no newer request has finished, so an older result never replaces
// newer builder state. Handlers are the only place a request writes builder state.
export function useFormBuilderSaveQueue(scopeKey: string) {
    const boundKeyRef = useRef(scopeKey)
    const generationRef = useRef(0)
    const activeRef = useRef(false)
    const sequenceRef = useRef(0)
    const settledSequenceRef = useRef(0)
    const pendingRef = useRef(0)
    const tailRef = useRef<Promise<void>>(Promise.resolve())
    const [pendingCount, setPendingCount] = useState(0)

    // The layout effect runs in the commit that shows another form, so a request that finishes
    // afterwards cannot write into that form's state. Hiding the builder (Activity) or unmounting
    // it runs only the cleanup and keeps the generation, so results still clear pending flags;
    // React ignores state writes after unmount.
    useLayoutEffect(() => {
        if (boundKeyRef.current !== scopeKey) {
            boundKeyRef.current = scopeKey
            generationRef.current += 1
        }
        activeRef.current = true
        return () => {
            activeRef.current = false
        }
    }, [scopeKey])

    const [enqueue] = useState(
        () =>
            <Result>(task: (ticket: SaveTicket) => Promise<Result>, handlers: SaveHandlers<Result>) => {
                const generation = generationRef.current
                const sequence = ++sequenceRef.current
                const ticket: SaveTicket = {
                    isCurrent: () =>
                        generationRef.current === generation && settledSequenceRef.current < sequence,
                    isActive: () => activeRef.current,
                }
                const settle = (apply: () => void) => {
                    if (!ticket.isCurrent()) return
                    settledSequenceRef.current = sequence
                    apply()
                }
                const run = async () => {
                    try {
                        const result = await task(ticket)
                        settle(() => handlers.onSuccess(result, ticket))
                    } catch (error) {
                        settle(() => handlers.onError(error, ticket))
                    } finally {
                        pendingRef.current -= 1
                        setPendingCount((count) => count - 1)
                    }
                }

                pendingRef.current += 1
                setPendingCount((count) => count + 1)
                const next = tailRef.current.then(run)
                tailRef.current = next
                return next
            },
    )

    // Save and Publish check this in their handlers as well as through disabled buttons: an
    // autosave queued in the same frame has not rendered isBusy yet.
    const [isIdle] = useState(() => () => pendingRef.current === 0)

    return {
        enqueue,
        isIdle,
        // Autosave, Save, and Publish wait while a request is pending; edits made meanwhile stay dirty.
        isBusy: pendingCount > 0,
    }
}
