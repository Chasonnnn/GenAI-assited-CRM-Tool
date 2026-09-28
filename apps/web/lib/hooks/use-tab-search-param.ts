"use client"

import { usePathname, useSearchParams } from "next/navigation"

/**
 * Tab state stored in a URL search param (default `tab`). Unknown values fall back to
 * `defaultValue`, and the default tab removes the param so the canonical URL stays clean.
 * Other params are kept.
 *
 * It writes with `window.history.replaceState`, which Next.js syncs into `useSearchParams`
 * without a server request. `router.replace` would refetch a dynamic page on every tab click.
 */
export function useTabSearchParam<T extends string>(
    values: readonly T[],
    defaultValue: T,
    param = "tab",
): readonly [T, (next: unknown) => void] {
    const searchParams = useSearchParams()
    const pathname = usePathname()

    const isValue = (candidate: unknown): candidate is T =>
        typeof candidate === "string" && (values as readonly string[]).includes(candidate)

    const raw = searchParams.get(param)
    const value = isValue(raw) ? raw : defaultValue

    const setValue = (next: unknown) => {
        if (!isValue(next) || next === value) return
        const params = new URLSearchParams(searchParams.toString())
        if (next === defaultValue) {
            params.delete(param)
        } else {
            params.set(param, next)
        }
        const query = params.toString()
        window.history.replaceState(null, "", query ? `${pathname}?${query}` : pathname)
    }

    return [value, setValue] as const
}
