"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useEffect, useState } from "react"

function getHistoryKeys() {
  if (typeof window === "undefined") return []
  const state = window.history.state || {}
  return Object.keys(state)
}

function logState(label: string) {
  if (typeof window === "undefined") return
  const state = window.history.state || {}
  const keys = Object.keys(state)
  console.log(`[debug/nav-shell] ${label}`, {
    href: window.location.href,
    pathname: window.location.pathname,
    keys,
    __NA: state.__NA,
  })
}

export default function DebugNavShellPage() {
  const router = useRouter()
  const pathname = usePathname()
  const [historyKeys, setHistoryKeys] = useState<string[]>([])

  useEffect(() => {
    logState("mount")
    setHistoryKeys(getHistoryKeys())

    const onPopState = () => {
      logState("popstate")
      setHistoryKeys(getHistoryKeys())
    }

    const originalPush = window.history.pushState.bind(window.history)
    const originalReplace = window.history.replaceState.bind(window.history)

    window.history.pushState = function pushState(data, unused, url) {
      const result = originalPush(data, unused, url)
      logState("pushState")
      setHistoryKeys(getHistoryKeys())
      return result
    }

    window.history.replaceState = function replaceState(data, unused, url) {
      const result = originalReplace(data, unused, url)
      logState("replaceState")
      setHistoryKeys(getHistoryKeys())
      return result
    }

    window.addEventListener("popstate", onPopState)

    return () => {
      window.removeEventListener("popstate", onPopState)
      window.history.pushState = originalPush
      window.history.replaceState = originalReplace
      logState("unmount")
    }
  }, [])

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ fontSize: 20, fontWeight: 600 }}>Debug Navigation (App Shell)</h1>
      <p style={{ color: "#666" }}>Current pathname: {pathname}</p>
      <p style={{ color: "#666" }}>History state keys: {historyKeys.join(", ") || "(none)"}</p>

      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 16, maxWidth: 360 }}>
        <Link
          href="/surrogates"
          prefetch={false}
          onClick={() => logState("Link prefetch=false click") }
          style={{ color: "#2563eb", textDecoration: "underline" }}
        >
          Link prefetch=false → /surrogates
        </Link>

        <Link
          href="/surrogates"
          onClick={() => logState("Link prefetch=default click") }
          style={{ color: "#2563eb", textDecoration: "underline" }}
        >
          Link prefetch=default → /surrogates
        </Link>

        <button
          type="button"
          onClick={() => {
            logState("router.push click")
            router.push("/surrogates")
            setTimeout(() => logState("after 0ms"), 0)
            setTimeout(() => logState("after 800ms"), 800)
          }}
        >
          router.push("/surrogates")
        </button>

        <button
          type="button"
          onClick={() => {
            logState("router.replace click")
            router.replace("/surrogates")
            setTimeout(() => logState("after 0ms"), 0)
            setTimeout(() => logState("after 800ms"), 800)
          }}
        >
          router.replace("/surrogates")
        </button>

        <button
          type="button"
          onClick={() => {
            logState("location.assign click")
            window.location.assign("/surrogates")
          }}
        >
          window.location.assign("/surrogates")
        </button>
      </div>
    </div>
  )
}
