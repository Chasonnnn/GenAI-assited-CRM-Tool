"use client"

import { useEffect, useState } from "react"
import { WifiOff } from "lucide-react"

/**
 * Offline detection banner.
 *
 * Shows a non-blocking banner when the user appears to be offline.
 * Detection uses both navigator.onLine and fetch failure tracking.
 *
 * IMPORTANT: Resets isOffline on next successful fetch to avoid
 * sticky banner after network recovery.
 */
export function OfflineBanner() {
    const [isOffline, setIsOffline] = useState(false)

    // Track online/offline events
    useEffect(() => {
        const handleOnline = () => setIsOffline(false)
        const handleOffline = () => setIsOffline(true)

        // Check initial state
        if (!navigator.onLine) {
            setIsOffline(true)
        }

        window.addEventListener("online", handleOnline)
        window.addEventListener("offline", handleOffline)

        return () => {
            window.removeEventListener("online", handleOnline)
            window.removeEventListener("offline", handleOffline)
        }
    }, [])

    // Intercept fetch to detect network failures
    useEffect(() => {
        const originalFetch = window.fetch

        window.fetch = async (...args) => {
            try {
                const response = await originalFetch(...args)
                // Successful fetch - clear offline state
                if (isOffline) {
                    setIsOffline(false)
                }
                return response
            } catch (error) {
                // Network error - likely offline
                if (
                    error instanceof TypeError &&
                    (error.message.includes("Failed to fetch") ||
                        error.message.includes("NetworkError") ||
                        error.message.includes("Network request failed"))
                ) {
                    setIsOffline(true)
                }
                throw error
            }
        }

        return () => {
            window.fetch = originalFetch
        }
    }, [isOffline])

    if (!isOffline) {
        return null
    }

    return (
        <div className="fixed left-0 right-0 top-0 z-50 bg-amber-500 px-4 py-2 text-center text-sm font-medium text-amber-950">
            <div className="flex items-center justify-center gap-2">
                <WifiOff className="size-4" />
                <span>You're offline. Some features may be unavailable.</span>
            </div>
        </div>
    )
}
