import * as React from "react"

const MOBILE_BREAKPOINT = 768
const MOBILE_MEDIA_QUERY = `(max-width: ${MOBILE_BREAKPOINT - 1}px)`

function getIsMobileSnapshot() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false
  }

  return window.matchMedia(MOBILE_MEDIA_QUERY).matches
}

function subscribeToIsMobile(onStoreChange: () => void) {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return () => undefined
  }

  const mediaQueryList = window.matchMedia(MOBILE_MEDIA_QUERY)
  const listener = () => onStoreChange()
  mediaQueryList.addEventListener("change", listener)

  return () => mediaQueryList.removeEventListener("change", listener)
}

export function useIsMobile() {
  return React.useSyncExternalStore(
    subscribeToIsMobile,
    getIsMobileSnapshot,
    () => false
  )
}
