"use client"

import { useState } from "react"
import type { Route } from "next"
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

type RouterReplace = ReturnType<typeof useRouter>["replace"]
type SearchParamsSnapshot = {
    toString: () => string
}

function updateMatchDetailTabUrl(
    replace: RouterReplace,
    searchParams: SearchParamsSnapshot,
    matchId: string,
    tab: TabType,
    source: SourceFilter
) {
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

    replace(nextUrl as Route, { scroll: false })
}

export function useMatchDetailTabState(matchId: string) {
    const searchParams = useSearchParams()
    const { replace } = useRouter()

    const [activeTab, setActiveTab] = useState<TabType>(() => {
        const tab = searchParams.get("tab")
        return isTabType(tab) ? tab : "notes"
    })
    const [sourceFilter, setSourceFilter] = useState<SourceFilter>(() => {
        const source = searchParams.get("source")
        return isSourceFilter(source) ? source : "all"
    })

    const handleTabChange = (tab: TabType) => {
        if (tab !== activeTab) {
            setActiveTab(tab)
            updateMatchDetailTabUrl(replace, searchParams, matchId, tab, sourceFilter)
        }
    }

    const handleSourceFilterChange = (source: SourceFilter) => {
        if (source !== sourceFilter) {
            setSourceFilter(source)
            updateMatchDetailTabUrl(replace, searchParams, matchId, activeTab, source)
        }
    }

    return {
        activeTab,
        sourceFilter,
        handleTabChange,
        handleSourceFilterChange,
    }
}
