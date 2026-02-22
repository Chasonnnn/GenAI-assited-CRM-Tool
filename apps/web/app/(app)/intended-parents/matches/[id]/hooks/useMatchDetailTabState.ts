"use client"

import { useCallback, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"

export type TabType = "notes" | "files" | "tasks" | "activity"
export type DataSource = "surrogate" | "ip" | "match"
export type SourceFilter = "all" | DataSource

export const SOURCE_OPTIONS: { value: SourceFilter; label: string }[] = [
    { value: "all", label: "All Source" },
    { value: "surrogate", label: "Surrogate" },
    { value: "ip", label: "Intended Parent" },
    { value: "match", label: "Match" },
]

export const sourceLabel = (value: SourceFilter | null | undefined) =>
    SOURCE_OPTIONS.find((option) => option.value === value)?.label ?? "All Source"

const isTabType = (value: string | null): value is TabType =>
    value === "notes" || value === "files" || value === "tasks" || value === "activity"

export const isSourceFilter = (value: string | null): value is SourceFilter =>
    value === "all" || value === "surrogate" || value === "ip" || value === "match"

export function useMatchDetailTabState(matchId: string) {
    const searchParams = useSearchParams()
    const router = useRouter()

    const [activeTab, setActiveTab] = useState<TabType>(() => {
        const tab = searchParams.get("tab")
        return isTabType(tab) ? tab : "notes"
    })
    const [sourceFilter, setSourceFilter] = useState<SourceFilter>(() => {
        const source = searchParams.get("source")
        return isSourceFilter(source) ? source : "all"
    })

    const updateUrlParams = useCallback(
        (tab: TabType, source: SourceFilter) => {
            const nextParams = new URLSearchParams(searchParams.toString())
            if (tab !== "notes") {
                nextParams.set("tab", tab)
            } else {
                nextParams.delete("tab")
            }
            if (source !== "all") {
                nextParams.set("source", source)
            } else {
                nextParams.delete("source")
            }

            const nextQuery = nextParams.toString()
            const currentQuery = searchParams.toString()
            if (nextQuery === currentQuery) return

            const nextUrl = nextQuery
                ? `/intended-parents/matches/${matchId}?${nextQuery}`
                : `/intended-parents/matches/${matchId}`
            const currentUrl = currentQuery
                ? `/intended-parents/matches/${matchId}?${currentQuery}`
                : `/intended-parents/matches/${matchId}`
            if (nextUrl === currentUrl) return

            router.replace(nextUrl, { scroll: false })
        },
        [matchId, router, searchParams]
    )

    const handleTabChange = useCallback(
        (tab: TabType) => {
            if (tab !== activeTab) {
                setActiveTab(tab)
                updateUrlParams(tab, sourceFilter)
            }
        },
        [activeTab, sourceFilter, updateUrlParams]
    )

    const handleSourceFilterChange = useCallback(
        (source: SourceFilter) => {
            if (source !== sourceFilter) {
                setSourceFilter(source)
                updateUrlParams(activeTab, source)
            }
        },
        [activeTab, sourceFilter, updateUrlParams]
    )

    return {
        activeTab,
        sourceFilter,
        handleTabChange,
        handleSourceFilterChange,
    }
}
