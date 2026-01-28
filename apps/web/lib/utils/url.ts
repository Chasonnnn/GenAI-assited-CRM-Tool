export function safeOpen(
  url: string | null | undefined,
  target: string = "_blank",
  features?: string
) {
  if (!url || typeof window === "undefined") return

  let resolved: URL | null = null

  try {
    resolved = new URL(url)
  } catch {
    const base = window.location.origin
    if (!base || base === "null") {
      return
    }
    try {
      resolved = new URL(url, base)
    } catch {
      return
    }
  }

  window.open(resolved.toString(), target, features)
}
