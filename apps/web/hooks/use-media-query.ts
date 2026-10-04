import * as React from "react"

function getSnapshot(query: string) {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false
  }
  return window.matchMedia(query).matches
}

function subscribe(query: string, onStoreChange: () => void) {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return () => undefined
  }
  const mediaQueryList = window.matchMedia(query)
  mediaQueryList.addEventListener("change", onStoreChange)
  return () => mediaQueryList.removeEventListener("change", onStoreChange)
}

/** True while the media query matches; false on the server and before hydration. */
export function useMediaQuery(query: string) {
  const subscribeToQuery = React.useCallback(
    (onStoreChange: () => void) => subscribe(query, onStoreChange),
    [query],
  )
  const getQuerySnapshot = React.useCallback(() => getSnapshot(query), [query])
  return React.useSyncExternalStore(subscribeToQuery, getQuerySnapshot, () => false)
}
