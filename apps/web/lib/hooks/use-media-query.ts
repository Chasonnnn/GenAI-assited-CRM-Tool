/**
 * useMediaQuery hook for responsive design.
 * Returns true if the media query matches.
 */

import { useSyncExternalStore } from "react"

export function useMediaQuery(query: string): boolean {
    return useSyncExternalStore(
        (onStoreChange) => {
            if (typeof window === "undefined") return () => {}
            const media = window.matchMedia(query)
            media.addEventListener("change", onStoreChange)
            return () => {
                media.removeEventListener("change", onStoreChange)
            }
        },
        () => (typeof window === "undefined" ? false : window.matchMedia(query).matches),
        () => false,
    )
}
