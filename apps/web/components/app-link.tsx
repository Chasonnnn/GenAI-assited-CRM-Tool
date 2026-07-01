"use client"

import * as React from "react"
import Link from "next/link"
import type { Route } from "next"
import type { UrlObject } from "url"
import { useRouter } from "next/navigation"

// AppLink is a permissive runtime wrapper that resolves arbitrary hrefs (including
// external and dynamically-built URLs), so it accepts plain strings in addition to
// the typedRoutes `Route` type and casts to `Route` where Next requires it.
type AppLinkHref = Route | UrlObject | string

function toSearchParams(query: Record<string, unknown> | undefined) {
  if (!query) return ""
  const params = new URLSearchParams()
  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === null) return
    if (Array.isArray(value)) {
      value.forEach((item) => {
        if (item === undefined || item === null) return
        params.append(key, String(item))
      })
      return
    }
    params.set(key, String(value))
  })
  const qs = params.toString()
  return qs ? `?${qs}` : ""
}

function resolveHref(href: AppLinkHref) {
  if (typeof href === "string") return href
  if (href instanceof URL) return href.toString()

  const pathname = href.pathname ?? ""
  const search = href.search
  const hash = href.hash
  const queryString = search
    ? search.startsWith("?")
      ? search
      : `?${search}`
    : toSearchParams(href.query as Record<string, unknown> | undefined)
  const hashString = hash
    ? hash.startsWith("#")
      ? hash
      : `#${hash}`
    : ""

  return `${pathname}${queryString}${hashString}`
}

type AppLinkProps = Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & {
  href: AppLinkHref
  replace?: boolean
  scroll?: boolean
  prefetch?: boolean
  fallbackMode?: "router" | "reload" | "none"
  ref?: React.Ref<HTMLAnchorElement>
}

function AppLink({
  href,
  onClick,
  replace,
  scroll,
  prefetch = false,
  fallbackMode = "none",
  target,
  download,
  ref,
  ...props
}: AppLinkProps) {
  const { push, replace: replaceRoute } = useRouter()
  const handleClick = (event: React.MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event)

    const ariaDisabled = event.currentTarget.getAttribute("aria-disabled")
    if (ariaDisabled === "true" || event.currentTarget.hasAttribute("disabled")) {
      return
    }

    if (event.button !== 0) return
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    if (target && target !== "_self") return
    if (download) return

    const hrefString = resolveHref(href)
    if (!hrefString) return

    const currentUrl = window.location.href
    const targetUrl = new URL(hrefString, currentUrl)

    if (currentUrl === targetUrl.toString()) return

    if (fallbackMode === "none") return

    const targetHref =
      targetUrl.origin === window.location.origin
        ? `${targetUrl.pathname}${targetUrl.search}${targetUrl.hash}`
        : targetUrl.toString()

    if (fallbackMode === "reload") {
      event.preventDefault()
      window.location.assign(targetHref)
      return
    }

    // Default: client-side navigation via router for same-origin routes.
    event.preventDefault()
    if (targetUrl.origin === window.location.origin) {
      if (replace) {
        replaceRoute(targetHref as Route, scroll === undefined ? undefined : { scroll })
      } else {
        push(targetHref as Route, scroll === undefined ? undefined : { scroll })
      }
    } else {
      window.location.assign(targetHref)
    }
  }

  const linkProps = {
    href: href as Route | UrlObject,
    onClick: handleClick,
    ...props,
    // Conditionally spread optional props so we never pass explicit `undefined`
    // (incompatible with the Link types under exactOptionalPropertyTypes).
    ...(target !== undefined ? { target } : {}),
    ...(download !== undefined ? { download } : {}),
    ...(ref !== undefined ? { ref } : {}),
    ...(replace ? { replace: true } : {}),
    ...(scroll !== undefined ? { scroll } : {}),
    ...(prefetch !== undefined ? { prefetch } : {}),
  }

  // The wrapper forwards arbitrary anchor attributes; assert the assembled props match
  // Link's prop type (broad optional spread is otherwise rejected under exactOptionalPropertyTypes).
  return <Link {...(linkProps as React.ComponentProps<typeof Link>)} />
}

export default AppLink
