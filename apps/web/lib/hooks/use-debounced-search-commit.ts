import { useEffect, useRef } from "react"

export function useDebouncedSearchCommit(scopeKey: string) {
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

    const cancel = () => {
        if (!timerRef.current) return
        clearTimeout(timerRef.current)
        timerRef.current = null
    }

    const schedule = (commit: () => void, delayMs: number) => {
        cancel()
        timerRef.current = setTimeout(() => {
            timerRef.current = null
            commit()
        }, delayMs)
    }

    useEffect(() => {
        return cancel
    }, [scopeKey])

    return { cancel, schedule }
}
