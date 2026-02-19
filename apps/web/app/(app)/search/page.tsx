"use client"

import { useState, useCallback } from "react"
import Link from "@/components/app-link"
import { useQuery } from "@tanstack/react-query"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
    Search,
    FileText,
    Paperclip,
    Users,
    Loader2,
    AlertCircle,
    ArrowRight,
} from "lucide-react"
import { globalSearch, type SearchResult, type SearchResponse } from "@/lib/api/search"
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value"
import { sanitizeHtml } from "@/lib/utils/sanitize"

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
            result.surrogate_id ? `/surrogates/${result.surrogate_id}` : "#",
    },
    attachment: {
        icon: Paperclip,
        label: "File",
        color: "bg-green-500/10 text-green-600 dark:text-green-400",
        getUrl: (result: SearchResult) =>
            result.surrogate_id ? `/surrogates/${result.surrogate_id}` : "#",
    },
    intended_parent: {
        icon: Users,
        label: "Intended Parent",
        color: "bg-purple-500/10 text-purple-600 dark:text-purple-400",
        getUrl: (result: SearchResult) => `/intended-parents/${result.entity_id}`,
    },
}

export default function SearchPage() {
    const [query, setQuery] = useState("")
    // Debounce search by 400ms to reduce API calls
    const debouncedQuery = useDebouncedValue(query, 400)

    const {
        data: results,
        isLoading,
        isError,
    } = useQuery<SearchResponse>({
        queryKey: ["search", debouncedQuery],
        queryFn: () => globalSearch({ q: debouncedQuery, limit: 50 }),
        enabled: debouncedQuery.length >= 2,
        staleTime: 30000,
    })

    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
        if (e.key === "Escape") {
            setQuery("")
        }
    }, [])

    return (
        <div className="flex flex-1 flex-col gap-6 p-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-semibold">Search</h1>
                <p className="text-muted-foreground">
                    Search across surrogates, notes, files, and intended parents
                </p>
            </div>

            {/* Search Input */}
            <div className="relative max-w-2xl">
                <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
                <Input
                    placeholder="Search surrogates, intended parents, notes, files..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                    className="pl-10 h-12 text-lg"
                    autoFocus
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

            {/* Search Tips */}
            {!query && (
                <Card className="max-w-2xl">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-sm font-medium">Search Tips</CardTitle>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground space-y-2">
                        <p>• Search by name, email, phone, or surrogate/intended parent number</p>
                        <p>• Use quotes for exact phrases: &quot;contract signed&quot;</p>
                        <p>• Results are ranked by relevance</p>
                    </CardContent>
                </Card>
            )}

            {/* Loading State */}
            {isLoading && debouncedQuery.length >= 2 && (
                <div className="flex items-center gap-2 text-muted-foreground">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <span>Searching...</span>
                </div>
            )}

            {/* Error State */}
            {isError && (
                <div className="flex items-center gap-2 text-destructive">
                    <AlertCircle className="h-5 w-5" />
                    <span>Failed to search. Please try again.</span>
                </div>
            )}

            {/* No Results */}
            {results && results.total === 0 && debouncedQuery.length >= 2 && (
                <div className="text-muted-foreground">
                    No results found for &quot;{debouncedQuery}&quot;
                </div>
            )}

            {/* Results */}
            {results && results.total > 0 && (
                <div className="space-y-4">
                    <div className="text-sm text-muted-foreground">
                        {results.total} result{results.total !== 1 ? "s" : ""} for &quot;{results.query}&quot;
                    </div>

                    <div className="space-y-3 max-w-4xl">
                        {results.results.map((result) => {
                            const config = ENTITY_CONFIG[result.entity_type]
                            const Icon = config.icon
                            const url = config.getUrl(result)

                            return (
                                <Link
                                    key={`${result.entity_type}-${result.entity_id}`}
                                    href={url}
                                >
                                    <Card className="hover:bg-accent/50 transition-colors cursor-pointer">
                                        <CardContent className="flex items-start gap-4 p-4">
                                            <div
                                                className={`flex h-10 w-10 items-center justify-center rounded-lg ${config.color}`}
                                            >
                                                <Icon className="h-5 w-5" />
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
                                                    <p
                                                        className="text-sm text-muted-foreground line-clamp-2"
                                                        dangerouslySetInnerHTML={{
                                                            __html: sanitizeHtml(result.snippet),
                                                        }}
                                                    />
                                                )}
                                                {result.surrogate_name &&
                                                    result.entity_type !== "surrogate" && (
                                                        <p className="text-xs text-muted-foreground">
                                                            Surrogate: {result.surrogate_name}
                                                        </p>
                                                    )}
                                            </div>
                                            <ArrowRight className="h-5 w-5 text-muted-foreground shrink-0" />
                                        </CardContent>
                                    </Card>
                                </Link>
                            )
                        })}
                    </div>
                </div>
            )}
        </div>
    )
}
