"use client"

import { useLayoutEffect, useRef, useState } from "react"

export type SaveTicket = {
    // False once the builder moved to another form or unmounted, or a newer request finished.
    isCurrent: () => boolean
}

type SaveHandlers<Result> = {
    onSuccess: (result: Result) => void
    onError: (error: unknown) => void
}

// Runs a builder's autosave, Save, and Publish requests one at a time, in the order they were
// requested. Each request records the builder generation when it was requested; navigation to
// another form and unmount start a new generation. A finished request applies its handlers only
// while its generation is current and no newer request has finished, so an older result never
// replaces newer builder state. Handlers are the only place a request writes builder state.
export function useFormBuilderSaveQueue(scopeKey: string) {
    const generationRef = useRef(0)
    const sequenceRef = useRef(0)
    const settledSequenceRef = useRef(0)
    const tailRef = useRef<Promise<void>>(Promise.resolve())
    const [pendingCount, setPendingCount] = useState(0)

    // A layout effect cleanup runs in the same commit that shows the other form or removes the
    // builder. A passive effect cleanup can run later, and a request finishing in between would
    // write its result into the other form's state.
    useLayoutEffect(() => {
        return () => {
            generationRef.current += 1
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
                }
                const settle = (apply: () => void) => {
                    if (!ticket.isCurrent()) return
                    settledSequenceRef.current = sequence
                    apply()
                }
                const run = async () => {
                    try {
                        const result = await task(ticket)
                        settle(() => handlers.onSuccess(result))
                    } catch (error) {
                        settle(() => handlers.onError(error))
                    } finally {
                        setPendingCount((count) => count - 1)
                    }
                }

                setPendingCount((count) => count + 1)
                const next = tailRef.current.then(run)
                tailRef.current = next
                return next
            },
    )

    return {
        enqueue,
        // Autosave waits while a request is pending or queued; edits made meanwhile stay dirty.
        isBusy: pendingCount > 0,
    }
}
