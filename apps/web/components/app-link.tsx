"use client"

import * as React from "react"
import Link, { type LinkProps } from "next/link"
import { useRouter } from "next/navigation"

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

function resolveHref(href: LinkProps["href"]) {
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

export type AppLinkProps = LinkProps &
  React.AnchorHTMLAttributes<HTMLAnchorElement> & {
    fallbackMode?: "router" | "reload" | "none"
    fallbackTimeoutMs?: number
  }

const AppLink = React.forwardRef<HTMLAnchorElement, AppLinkProps>(
  (
    {
      href,
      onClick,
      replace,
      scroll,
      fallbackMode = "none",
      fallbackTimeoutMs = 400,
      target,
      download,
      ...props
    },
    ref
  ) => {
    const router = useRouter()
    const handleClick = React.useCallback(
      (event: React.MouseEvent<HTMLAnchorElement>) => {
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

        if (event.defaultPrevented) {
          if (fallbackMode === "none") return

          if (targetUrl.origin === window.location.origin) {
            if (replace) {
              router.replace(targetUrl.toString(), scroll === undefined ? undefined : { scroll })
            } else {
              router.push(targetUrl.toString(), scroll === undefined ? undefined : { scroll })
            }
          } else {
            window.location.assign(targetUrl.toString())
          }
          return
        }

        if (fallbackMode !== "reload") return

        window.setTimeout(() => {
          if (window.location.href !== currentUrl) return
          if (targetUrl.protocol !== "http:" && targetUrl.protocol !== "https:") return
          window.location.assign(targetUrl.toString())
        }, fallbackTimeoutMs)
      },
      [onClick, href, target, download, fallbackMode, fallbackTimeoutMs, replace, router, scroll]
    )

    const linkProps = {
      href,
      onClick: handleClick,
      target,
      download,
      ref,
      ...props,
      ...(replace !== undefined ? { replace } : {}),
      ...(scroll !== undefined ? { scroll } : {}),
    }

    return <Link {...linkProps} />
  }
)

AppLink.displayName = "AppLink"

export default AppLink
