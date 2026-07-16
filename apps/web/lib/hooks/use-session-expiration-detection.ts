import { useEffect, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"

function isUnauthorizedError(error: unknown): boolean {
    if (!error || typeof error !== "object") return false
    if ("status" in error && error.status === 401) return true
    if (
        "response" in error &&
        error.response &&
        typeof error.response === "object" &&
        "status" in error.response &&
        error.response.status === 401
    ) {
        return true
    }
    return false
}

export function useSessionExpirationDetection() {
    const [isExpired, setIsExpired] = useState(false)
    const queryClient = useQueryClient()

    useEffect(() => {
        const unsubscribeQueries = queryClient.getQueryCache().subscribe((event) => {
            if (
                event.type === "updated" &&
                event.action.type === "error" &&
                isUnauthorizedError(event.action.error)
            ) {
                setIsExpired(true)
            }
        })
        const unsubscribeMutations = queryClient.getMutationCache().subscribe((event) => {
            if (
                event.type === "updated" &&
                event.action.type === "error" &&
                isUnauthorizedError(event.action.error)
            ) {
                setIsExpired(true)
            }
        })

        return () => {
            unsubscribeQueries()
            unsubscribeMutations()
        }
    }, [queryClient])

    return isExpired
}
