"use client"

import { useSyncExternalStore } from "react"
import { useOffline } from "next/offline"
import { WifiOff } from "lucide-react"

function subscribeBrowserConnectivity(listener: () => void) {
    window.addEventListener("online", listener)
    window.addEventListener("offline", listener)
    return () => {
        window.removeEventListener("online", listener)
        window.removeEventListener("offline", listener)
    }
}

function getBrowserOfflineSnapshot() {
    return !navigator.onLine
}

function getServerOfflineSnapshot() {
    return false
}

/**
 * Offline detection banner.
 *
 * Shows a non-blocking banner when the user appears to be offline.
 * Next's experimental signal detects failed framework navigations and Server
 * Actions when enabled. Browser events retain the existing baseline behavior.
 */
export function OfflineBanner() {
    const isNextOffline = useOffline()
    const isBrowserOffline = useSyncExternalStore(
        subscribeBrowserConnectivity,
        getBrowserOfflineSnapshot,
        getServerOfflineSnapshot
    )
    const isOffline = isNextOffline || isBrowserOffline

    if (!isOffline) {
        return null
    }

    return (
        <div
            className="fixed left-0 right-0 top-0 z-50 bg-amber-500 px-4 py-2 text-center text-sm font-medium text-amber-950"
            role="alert"
        >
            <div className="flex items-center justify-center gap-2">
                <WifiOff className="size-4" />
                <span>You're offline. Some features may be unavailable.</span>
            </div>
        </div>
    )
}
