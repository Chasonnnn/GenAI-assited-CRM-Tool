"use client"

import { Suspense, useState } from "react"
import { usePathname, useSearchParams } from "next/navigation"
import Link from "@/components/app-link"
import { useQuery } from "@tanstack/react-query"
import { PageHeader } from "@/components/page-header"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
    Search,
    FileText,
    Paperclip,
    Users,
    Loader2,
    AlertCircle,
    ArrowRight,
    CircleUserRound,
} from "lucide-react"
import {
    createEmptySearchResponse,
    globalSearch,
    type SearchResult,
    type SearchResponse,
} from "@/lib/api/search"
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value"
import { SafeHtmlContent } from "@/components/safe-html-content"

const ENTITY_CONFIG = {
    surrogate: {
        icon: FileText,
        label: "Surrogate",
        color: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
        getUrl: (result: SearchResult) => `/surrogates/${result.entity_id}`,
    },
    note: {
        icon: FileText,
        label: "Note",
        color: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
        getUrl: (result: SearchResult) =>
            result.donor_id
                ? `/donors/${result.donor_id}`
                : result.surrogate_id
                    ? `/surrogates/${result.surrogate_id}`
                    : "#",
    },
    attachment: {
        icon: Paperclip,
        label: "File",
        color: "bg-green-500/10 text-green-600 dark:text-green-400",
        getUrl: (result: SearchResult) =>
            result.donor_id
                ? `/donors/${result.donor_id}`
                : result.surrogate_id
                    ? `/surrogates/${result.surrogate_id}`
                    : "#",
    },
    intended_parent: {
        icon: Users,
        label: "Intended Parent",
        color: "bg-purple-500/10 text-purple-600 dark:text-purple-400",
        getUrl: (result: SearchResult) => `/intended-parents/${result.entity_id}`,
    },
    donor: {
        icon: CircleUserRound,
        label: "Donor",
        color: "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400",
        getUrl: (result: SearchResult) => `/donors/${result.entity_id}`,
    },
}

export default function SearchPage() {
    return (
        <Suspense fallback={null}>
            <SearchPageContent />
        </Suspense>
    )
}

function SearchPageContent() {
    const searchParams = useSearchParams()
    const pathname = usePathname()
    // The URL seeds the input once; typing then writes ?q= so a search can be linked or reloaded.
    const [query, setQueryState] = useState(() => searchParams.get("q") ?? "")
    const debouncedQuery = useDebouncedValue(query, 400)

    const setQuery = (value: string) => {
        setQueryState(value)
        const params = new URLSearchParams(searchParams.toString())
        if (value) {
            params.set("q", value)
        } else {
            params.delete("q")
        }
        const nextQuery = params.toString()
        // replaceState keeps typing out of history and avoids a server round trip per keystroke.
        window.history.replaceState(null, "", nextQuery ? `${pathname}?${nextQuery}` : pathname)
    }

    const {
        data: results = createEmptySearchResponse(debouncedQuery),
        isLoading,
        isError,
    } = useQuery<SearchResponse>({
        queryKey: ["search", debouncedQuery],
        queryFn: () => globalSearch({ q: debouncedQuery, limit: 50 }),
        enabled: debouncedQuery.length >= 2,
        staleTime: 30000,
        placeholderData: (previousData) =>
            previousData ?? createEmptySearchResponse(debouncedQuery),
    })

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Escape") {
            setQuery("")
        }
    }

    return (
        <div className="flex flex-1 flex-col">
            <PageHeader title="Search" />

            <div className="flex flex-1 flex-col gap-6 p-6">
                <div className="relative max-w-2xl">
                    <Search className="absolute left-3 top-1/2 size-5 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
                    <Input
                        type="search"
                        aria-label="Search"
                        placeholder="Search surrogates, intended parents, donors, notes, files"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={handleKeyDown}
                        className="pl-10 pr-16 h-12 text-lg [&::-webkit-search-cancel-button]:hidden"
                    />
                    {query && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setQuery("")}
                            className="absolute right-2 top-1/2 -translate-y-1/2 h-8 px-2 text-muted-foreground hover:text-foreground"
                        >
                            Clear
                        </Button>
                    )}
                </div>

                {isLoading && debouncedQuery.length >= 2 && (
                    <div className="flex items-center gap-2 text-muted-foreground">
                        <Loader2 className="size-5 animate-spin" aria-hidden="true" />
                        <span>Searching&hellip;</span>
                    </div>
                )}

                {isError && (
                    <div className="flex items-center gap-2 text-destructive">
                        <AlertCircle className="size-5" aria-hidden="true" />
                        <span>Failed to search. Please try again.</span>
                    </div>
                )}

                {results && results.total === 0 && debouncedQuery.length >= 2 && (
                    <div className="text-muted-foreground">
                        No results found for &quot;{debouncedQuery}&quot;
                    </div>
                )}

                {results && results.total > 0 && (
                    <div className="space-y-3">
                        <div className="text-sm text-muted-foreground">
                            {results.total} result{results.total !== 1 ? "s" : ""} for &quot;{results.query}&quot;
                        </div>

                        <ul className="max-w-4xl divide-y overflow-hidden rounded-xl border bg-card">
                            {results.results.map((result) => {
                                const config = ENTITY_CONFIG[result.entity_type]
                                const Icon = config.icon
                                const url = config.getUrl(result)

                                return (
                                    <li key={`${result.entity_type}-${result.entity_id}`}>
                                        <Link
                                            href={url}
                                            className="flex items-start gap-4 px-4 py-3 transition-colors hover:bg-accent/50 focus-visible:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                                        >
                                            <div
                                                className={`flex size-9 shrink-0 items-center justify-center rounded-lg ${config.color}`}
                                            >
                                                <Icon className="size-4" aria-hidden="true" />
                                            </div>
                                            <div className="flex-1 space-y-1 min-w-0">
                                                <div className="flex items-center gap-2">
                                                    <span className="font-medium truncate">
                                                        {result.title}
                                                    </span>
                                                    <Badge variant="secondary" className="text-xs shrink-0">
                                                        {config.label}
                                                    </Badge>
                                                </div>
                                                {result.snippet && (
                                                    <SafeHtmlContent
                                                        html={result.snippet}
                                                        className="text-sm text-muted-foreground line-clamp-2"
                                                    />
                                                )}
                                                {result.surrogate_name &&
                                                    result.entity_type !== "surrogate" && (
                                                        <p className="text-xs text-muted-foreground">
                                                            Surrogate: {result.surrogate_name}
                                                        </p>
                                                    )}
                                            </div>
                                            <ArrowRight className="mt-2 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                                        </Link>
                                    </li>
                                )
                            })}
                        </ul>
                    </div>
                )}
            </div>
        </div>
    )
}
