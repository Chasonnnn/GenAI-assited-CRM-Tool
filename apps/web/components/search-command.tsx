"use client"

import { useState } from "react"
import type { Route } from "next"
import { useRouter } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import {
    Command,
    CommandDialog,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
} from "@/components/ui/command"
import { FileText, Paperclip, Users, Loader2 } from "lucide-react"
import {
    createEmptySearchResponse,
    globalSearch,
    type SearchResult,
    type SearchResponse,
} from "@/lib/api/search"
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value"

export { useSearchHotkey } from "@/lib/hooks/use-search-hotkey"

const ENTITY_CONFIG = {
    surrogate: {
        icon: FileText,
        label: "Surrogate",
        getUrl: (result: SearchResult) => `/surrogates/${result.entity_id}`,
    },
    note: {
        icon: FileText,
        label: "Note",
        getUrl: (result: SearchResult) =>
            result.surrogate_id ? `/surrogates/${result.surrogate_id}` : "#",
    },
    attachment: {
        icon: Paperclip,
        label: "File",
        getUrl: (result: SearchResult) =>
            result.surrogate_id ? `/surrogates/${result.surrogate_id}` : "#",
    },
    intended_parent: {
        icon: Users,
        label: "Intended Parent",
        getUrl: (result: SearchResult) => `/intended-parents/${result.entity_id}`,
    },
}

interface SearchCommandDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
}

export function SearchCommandDialog({ open, onOpenChange }: SearchCommandDialogProps) {
    return (
        <SearchCommandDialogContent
            key={open ? "open" : "closed"}
            open={open}
            onOpenChange={onOpenChange}
        />
    )
}

function SearchCommandDialogContent({ open, onOpenChange }: SearchCommandDialogProps) {
    const { push } = useRouter()
    const [query, setQuery] = useState("")
    const debouncedQuery = useDebouncedValue(query, 400)

    const {
        data: results = createEmptySearchResponse(debouncedQuery),
        isLoading,
    } = useQuery<SearchResponse>({
        queryKey: ["search-command", debouncedQuery],
        queryFn: () => globalSearch({ q: debouncedQuery, limit: 10 }),
        enabled: open && debouncedQuery.length >= 2,
        staleTime: 30000,
        placeholderData: (previousData) =>
            previousData ?? createEmptySearchResponse(debouncedQuery),
    })

    const handleSelect = (result: SearchResult) => {
        const config = ENTITY_CONFIG[result.entity_type]
        const url = config.getUrl(result)
        onOpenChange(false)
        push(url as Route)
    }

    return (
        <CommandDialog
            open={open}
            onOpenChange={onOpenChange}
            title="Search"
            description="Search across surrogates, notes, files, and intended parents"
        >
            <Command shouldFilter={false}>
            <CommandInput
                placeholder="Search surrogates, intended parents, notes, files"
                value={query}
                onValueChange={setQuery}
            />
                <CommandList>
                    {isLoading && debouncedQuery.length >= 2 && (
                        <div className="flex items-center justify-center py-6 text-sm text-muted-foreground">
                            <Loader2 className="mr-2 size-4 animate-spin" />
                            Searching
                        </div>
                    )}

                    {!isLoading && debouncedQuery.length >= 2 && results?.total === 0 && (
                        <CommandEmpty>No results found.</CommandEmpty>
                    )}

                    {!isLoading && debouncedQuery.length < 2 && (
                        <div className="py-6 text-center text-sm text-muted-foreground">
                            Type at least 2 characters to search
                        </div>
                    )}

                    {results && results.total > 0 && (
                        <CommandGroup heading={`${results.total} results`}>
                            {results.results.map((result) => {
                                const config = ENTITY_CONFIG[result.entity_type]
                                const Icon = config.icon

                                return (
                                    <CommandItem
                                        key={`${result.entity_type}-${result.entity_id}`}
                                        value={`${result.entity_type}-${result.entity_id}`}
                                        onSelect={() => handleSelect(result)}
                                    >
                                        <Icon className="mr-2 size-4" />
                                        <div className="flex flex-col">
                                            <span>{result.title}</span>
                                            <span className="text-xs text-muted-foreground">
                                                {config.label}
                                                {result.surrogate_name && result.entity_type !== "surrogate" && (
                                                    <> · {result.surrogate_name}</>
                                                )}
                                            </span>
                                        </div>
                                    </CommandItem>
                                )
                            })}
                        </CommandGroup>
                    )}
                </CommandList>
            </Command>
        </CommandDialog>
    )
}
