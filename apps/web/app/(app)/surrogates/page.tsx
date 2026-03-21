"use client"

import { useState, useEffect, useCallback, useTransition, useRef } from "react"
import Link from "@/components/app-link"
import { useSearchParams, useRouter } from "next/navigation"
import { Card, CardContent } from "@/components/ui/card"
import { Button, buttonVariants } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Checkbox } from "@/components/ui/checkbox"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { PaginationJump } from "@/components/ui/pagination-jump"
import { MoreVerticalIcon, SearchIcon, XIcon, Loader2Icon, ArchiveIcon, UserPlusIcon, UploadIcon, PlusIcon, SlidersHorizontalIcon } from "lucide-react"
import { SortableTableHead } from "@/components/ui/sortable-table-head"
import { useSurrogates, useArchiveSurrogate, useRestoreSurrogate, useUpdateSurrogate, useAssignees, useBulkAssign, useBulkArchive, useCreateSurrogate, useIntelligentSuggestionSummary, useSurrogateCreatedDates } from "@/lib/hooks/use-surrogates"
import { useQueues } from "@/lib/hooks/use-queues"
import { useDefaultPipeline } from "@/lib/hooks/use-pipelines"
import { useAuth } from "@/lib/auth-context"
import type { SurrogateSource } from "@/lib/types/surrogate"
import { isDynamicSurrogateFilter, type DynamicSurrogateFilter, type SurrogateMassEditStageFilters } from "@/lib/api/surrogates"
import { DateRangePicker, type DateRangePreset } from "@/components/ui/date-range-picker"
import { cn } from "@/lib/utils"
import { formatRace } from "@/lib/formatters"
import { formatLocalDate, parseDateInput } from "@/lib/utils/date"
import { toast } from "sonner"
import { MassEditStageModal } from "@/components/surrogates/MassEditStageModal"
import { SurrogatesFloatingScrollbar } from "@/components/surrogates/SurrogatesFloatingScrollbar"

// Format date for display
function formatDate(dateString: string | null | undefined): string {
    if (!dateString) return "—"
    const date = parseDateInput(dateString)
    return new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "2-digit",
        year: "numeric",
    }).format(date)
}

// Get initials from name
function getInitials(name: string | null): string {
    if (!name) return "?"
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

// Floating Action Bar for bulk operations
function FloatingActionBar({
    selectedCount,
    selectedSurrogateIds,
    onClear,
}: {
    selectedCount: number
    selectedSurrogateIds: string[]
    onClear: () => void
}) {
    const { user } = useAuth()
    const { data: assignees } = useAssignees()
    const bulkAssignMutation = useBulkAssign()
    const bulkArchiveMutation = useBulkArchive()

    const canAssign = user?.role && ['case_manager', 'admin', 'developer'].includes(user.role)

    const handleAssign = async (userId: string) => {
        await bulkAssignMutation.mutateAsync({
            surrogate_ids: selectedSurrogateIds,
            owner_type: 'user',
            owner_id: userId,
        })
        onClear()
    }

    const handleArchive = async () => {
        await bulkArchiveMutation.mutateAsync(selectedSurrogateIds)
        onClear()
    }

    const isLoading = bulkAssignMutation.isPending || bulkArchiveMutation.isPending

    return (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50">
            <div className="bg-primary text-primary-foreground shadow-lg rounded-lg px-6 py-3 flex items-center gap-4">
                <span className="font-medium">{selectedCount} surrogate{selectedCount > 1 ? 's' : ''} selected</span>
                <div className="h-4 w-px bg-primary-foreground/30" />

                {/* Assign Dropdown - case_manager+ only */}
                {canAssign && (
                    <DropdownMenu>
                        <DropdownMenuTrigger
                            className={cn(buttonVariants({ variant: "secondary", size: "sm" }))}
                            disabled={isLoading}
                            aria-label="Assign to user"
                        >
                            <span className="inline-flex items-center gap-1">
                                <UserPlusIcon className="h-4 w-4" />
                                Assign to...
                            </span>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent>
                            {assignees?.map((user) => (
                                <DropdownMenuItem key={user.id} onClick={() => handleAssign(user.id)}>
                                    {user.name}
                                </DropdownMenuItem>
                            ))}
                        </DropdownMenuContent>
                    </DropdownMenu>
                )}

                {/* Archive Button */}
                <Button variant="secondary" size="sm" onClick={handleArchive} disabled={isLoading}>
                    <ArchiveIcon className="h-4 w-4 mr-1" />
                    Archive
                </Button>

                {/* Clear Button */}
                <Button variant="ghost" size="sm" onClick={onClear} disabled={isLoading}>
                    <XIcon className="h-4 w-4 mr-1" />
                    Clear
                </Button>
            </div>
        </div>
    )
}

const VALID_SOURCES = [
    "all",
    "manual",
    "meta",
    "tiktok",
    "google",
    "website",
    "referral",
    "other",
] as const
type SourceFilter = (typeof VALID_SOURCES)[number]
const isSourceFilter = (value: string | null): value is SourceFilter =>
    value !== null && VALID_SOURCES.includes(value as SourceFilter)

const CREATE_SOURCE_OPTIONS: { value: SurrogateSource; label: string }[] = [
    { value: "manual", label: "Manual" },
    { value: "website", label: "Website" },
    { value: "referral", label: "Referral" },
    { value: "meta", label: "Meta" },
    { value: "tiktok", label: "TikTok" },
    { value: "google", label: "Google" },
    { value: "other", label: "Others" },
]

const VALID_DATE_RANGES: DateRangePreset[] = ["all", "today", "week", "month", "custom"]
const isDateRangePreset = (value: string | null): value is DateRangePreset =>
    value !== null && VALID_DATE_RANGES.includes(value as DateRangePreset)

const DYNAMIC_FILTER_LABELS: Record<DynamicSurrogateFilter, string> = {
    intelligent_any: "Intelligent Suggestions",
    intelligent_new_unread_stale: "New Unread Needs Follow-up",
    intelligent_meeting_outcome_missing: "Meeting Outcome Missing",
    intelligent_stuck_preapproval: "Pre-approval Stuck Cases",
    attention_unreached: "Attention Needed: Unreached Leads",
    attention_stuck: "Attention Needed: Stuck Leads",
}

const SOURCE_LABELS: Record<string, string> = {
    manual: "Manual",
    meta: "Meta",
    tiktok: "TikTok",
    google: "Google",
    website: "Website",
    referral: "Referral",
    other: "Others",
    agency: "Agency",
    import: "Import",
}

const getStageFilterLabel = (
    value: string | null | undefined,
    stages: Array<{ id: string; label: string }>
) => {
    if (!value || value === "all") return "All Stages"
    return stages.find((stage) => stage.id === value)?.label ?? value
}

const getSourceFilterLabel = (value: string | null | undefined) => {
    if (!value || value === "all") return "All Sources"
    return SOURCE_LABELS[value] ?? value
}

const getQueueFilterLabel = (
    value: string | null | undefined,
    queues?: Array<{ id: string; name: string }>
) => {
    if (!value || value === "all") return "All Queues"
    return queues?.find((queue) => queue.id === value)?.name ?? value
}

const getAssigneeFilterLabel = (
    value: string | null | undefined,
    assignees?: Array<{ id: string; name: string }>
) => {
    if (!value || value === "all") return "All Assignees"
    return assignees?.find((assignee) => assignee.id === value)?.name ?? value
}

const getDynamicFilterLabel = (value: DynamicSurrogateFilter | null | undefined) => {
    if (!value) return "No smart filter"
    return DYNAMIC_FILTER_LABELS[value]
}

const parsePageParam = (value: string | null): number => {
    const parsed = Number(value)
    return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : 1
}

const parseSortOrderParam = (value: string | null): "asc" | "desc" => {
    return value === "asc" ? "asc" : "desc"
}

const parseDateParam = (value: string | null): Date | undefined => {
    if (!value) return undefined
    const parsed = parseDateInput(value)
    return Number.isNaN(parsed.getTime()) ? undefined : parsed
}

const datesEqual = (left?: Date, right?: Date) => {
    return (left?.getTime() ?? null) === (right?.getTime() ?? null)
}

const SURROGATES_LIST_PATH = "/surrogates"

const buildSurrogatesListHref = (query: string) => {
    return query ? `${SURROGATES_LIST_PATH}?${query}` : SURROGATES_LIST_PATH
}

const buildSurrogateDetailHref = (surrogateId: string, returnTo: string) => {
    const params = new URLSearchParams({ return_to: returnTo })
    return `/surrogates/${surrogateId}?${params.toString()}`
}

export default function SurrogatesPage() {
    const searchParams = useSearchParams()
    const router = useRouter()
    const currentQuery = searchParams.toString()
    const currentListHref = buildSurrogatesListHref(currentQuery)

    // Read initial values from URL params
    const urlStage = searchParams.get("stage")
    const urlSource = searchParams.get("source")
    const urlQueue = searchParams.get("queue")
    const urlSearch = searchParams.get("q")
    const urlPage = searchParams.get("page")
    const urlOwnerId = searchParams.get("owner_id")
    const urlRange = searchParams.get("range")
    const urlFrom = searchParams.get("from")
    const urlTo = searchParams.get("to")
    const urlDynamicFilter = searchParams.get("dynamic_filter")
    const urlPriority = searchParams.get("priority")
    const urlSortBy = searchParams.get("sort_by")
    const urlSortOrder = searchParams.get("sort_order")
    const { user } = useAuth()
    const canFilterByAssignee = user?.role === "admin" || user?.role === "developer"
    const canManagePriority = user?.role === "admin" || user?.role === "developer"
    const effectiveUrlOwnerId = canFilterByAssignee ? urlOwnerId : null
    const initialDynamicFilter = isDynamicSurrogateFilter(urlDynamicFilter) ? urlDynamicFilter : null
    const initialPriorityOnly = urlPriority === "only"
    const initialSortBy = urlSortBy || null
    const initialSortOrder = parseSortOrderParam(urlSortOrder)

    const [stageFilter, setStageFilter] = useState<string>(urlStage || "all")
    const [sourceFilter, setSourceFilter] = useState<SourceFilter>(
        isSourceFilter(urlSource) ? urlSource : "all"
    )
    const [queueFilter, setQueueFilter] = useState<string>(urlQueue || "all")
    const [ownerFilter, setOwnerFilter] = useState<string>(effectiveUrlOwnerId || "all")
    const initialRange = isDateRangePreset(urlRange) ? urlRange : "all"
    const initialCustomRange = initialRange === "custom"
        ? {
            from: parseDateParam(urlFrom),
            to: parseDateParam(urlTo),
        }
        : { from: undefined, to: undefined }
    const [dateRange, setDateRange] = useState<DateRangePreset>(initialRange)
    const [customRange, setCustomRange] = useState<{ from: Date | undefined; to: Date | undefined }>(initialCustomRange)
    const [searchQuery, setSearchQuery] = useState(urlSearch || "")
    const [debouncedSearch, setDebouncedSearch] = useState(urlSearch || "")
    const [dynamicFilter, setDynamicFilter] = useState<DynamicSurrogateFilter | null>(initialDynamicFilter)
    const [priorityOnly, setPriorityOnly] = useState(initialPriorityOnly)
    const [page, setPage] = useState(() => parsePageParam(urlPage))
    const [selectedSurrogates, setSelectedSurrogates] = useState<Set<string>>(new Set())
    const [sortBy, setSortBy] = useState<string | null>(initialSortBy)
    const [sortOrder, setSortOrder] = useState<"asc" | "desc">(initialSortOrder)
    const [isMoreFiltersOpen, setIsMoreFiltersOpen] = useState(false)
    const [isCreateOpen, setIsCreateOpen] = useState(false)
    const [isMassEditOpen, setIsMassEditOpen] = useState(false)
    const [createForm, setCreateForm] = useState({
        full_name: "",
        email: "",
        source: "manual" as SurrogateSource,
    })
    const perPage = 30
    const { data: assignees } = useAssignees()
    const createMutation = useCreateSurrogate()
    const { data: intelligentSummary } = useIntelligentSuggestionSummary()
    const [isFilterPending, startFilterTransition] = useTransition()
    const hasSyncedSearchRef = useRef(false)

    // Sync state changes back to URL
    const updateUrlParams = useCallback((
        stage: string,
        source: SourceFilter,
        queue: string,
        search: string,
        owner: string,
        currentPage: number,
        range: DateRangePreset,
        rangeDates: { from: Date | undefined; to: Date | undefined },
        activeDynamicFilter: DynamicSurrogateFilter | null,
        isPriorityOnly: boolean,
        nextSortBy: string | null,
        nextSortOrder: "asc" | "desc",
    ) => {
        const newParams = new URLSearchParams(searchParams.toString())

        if (activeDynamicFilter) {
            newParams.set("dynamic_filter", activeDynamicFilter)
        } else {
            newParams.delete("dynamic_filter")
        }

        if (stage !== "all") {
            newParams.set("stage", stage)
        } else {
            newParams.delete("stage")
        }

        if (source !== "all") {
            newParams.set("source", source)
        } else {
            newParams.delete("source")
        }

        if (queue !== "all") {
            newParams.set("queue", queue)
        } else {
            newParams.delete("queue")
        }

        if (search) {
            newParams.set("q", search)
        } else {
            newParams.delete("q")
        }

        if (owner !== "all") {
            newParams.set("owner_id", owner)
        } else {
            newParams.delete("owner_id")
        }

        if (isPriorityOnly) {
            newParams.set("priority", "only")
        } else {
            newParams.delete("priority")
        }

        if (range !== "all") {
            newParams.set("range", range)
            if (range === "custom") {
                if (rangeDates.from) {
                    newParams.set("from", formatLocalDate(rangeDates.from))
                } else {
                    newParams.delete("from")
                }
                if (rangeDates.to) {
                    newParams.set("to", formatLocalDate(rangeDates.to))
                } else {
                    newParams.delete("to")
                }
            } else {
                newParams.delete("from")
                newParams.delete("to")
            }
        } else {
            newParams.delete("range")
            newParams.delete("from")
            newParams.delete("to")
        }

        if (currentPage > 1) {
            newParams.set("page", String(currentPage))
        } else {
            newParams.delete("page")
        }

        if (nextSortBy) {
            newParams.set("sort_by", nextSortBy)
            newParams.set("sort_order", nextSortOrder)
        } else {
            newParams.delete("sort_by")
            newParams.delete("sort_order")
        }

        const nextQuery = newParams.toString()
        const currentQuery = searchParams.toString()
        if (nextQuery === currentQuery) return
        const newUrl = nextQuery ? `/surrogates?${nextQuery}` : "/surrogates"
        const currentUrl = currentQuery ? `/surrogates?${currentQuery}` : "/surrogates"
        if (newUrl === currentUrl) return
        router.replace(newUrl, { scroll: false })
    }, [router, searchParams])

    // Update URL when filters change - wrapped in startTransition for smoother UI
    const handleStageChange = useCallback((stage: string) => {
        startFilterTransition(() => {
            setStageFilter(stage)
            setPage(1)
            updateUrlParams(
                stage,
                sourceFilter,
                queueFilter,
                debouncedSearch,
                ownerFilter,
                1,
                dateRange,
                customRange,
                dynamicFilter,
                priorityOnly,
                sortBy,
                sortOrder,
            )
        })
    }, [sourceFilter, queueFilter, debouncedSearch, ownerFilter, updateUrlParams, dateRange, customRange, dynamicFilter, priorityOnly, sortBy, sortOrder])

    const handleSourceChange = useCallback((source: SourceFilter) => {
        startFilterTransition(() => {
            setSourceFilter(source)
            setPage(1)
            updateUrlParams(
                stageFilter,
                source,
                queueFilter,
                debouncedSearch,
                ownerFilter,
                1,
                dateRange,
                customRange,
                dynamicFilter,
                priorityOnly,
                sortBy,
                sortOrder,
            )
        })
    }, [stageFilter, queueFilter, debouncedSearch, ownerFilter, updateUrlParams, dateRange, customRange, dynamicFilter, priorityOnly, sortBy, sortOrder])

    const handleQueueChange = useCallback((queue: string) => {
        startFilterTransition(() => {
            setQueueFilter(queue)
            setPage(1)
            updateUrlParams(
                stageFilter,
                sourceFilter,
                queue,
                debouncedSearch,
                ownerFilter,
                1,
                dateRange,
                customRange,
                dynamicFilter,
                priorityOnly,
                sortBy,
                sortOrder,
            )
        })
    }, [stageFilter, sourceFilter, debouncedSearch, ownerFilter, updateUrlParams, dateRange, customRange, dynamicFilter, priorityOnly, sortBy, sortOrder])

    const handleOwnerChange = useCallback((owner: string) => {
        startFilterTransition(() => {
            setOwnerFilter(owner)
            setPage(1)
            updateUrlParams(
                stageFilter,
                sourceFilter,
                queueFilter,
                debouncedSearch,
                owner,
                1,
                dateRange,
                customRange,
                dynamicFilter,
                priorityOnly,
                sortBy,
                sortOrder,
            )
        })
    }, [stageFilter, sourceFilter, queueFilter, debouncedSearch, updateUrlParams, dateRange, customRange, dynamicFilter, priorityOnly, sortBy, sortOrder])

    const handleDynamicFilterChange = useCallback((nextDynamicFilter: DynamicSurrogateFilter | null) => {
        startFilterTransition(() => {
            setDynamicFilter(nextDynamicFilter)
            setPage(1)
            updateUrlParams(
                stageFilter,
                sourceFilter,
                queueFilter,
                debouncedSearch,
                ownerFilter,
                1,
                dateRange,
                customRange,
                nextDynamicFilter,
                priorityOnly,
                sortBy,
                sortOrder,
            )
        })
    }, [customRange, dateRange, debouncedSearch, ownerFilter, priorityOnly, queueFilter, sortBy, sortOrder, sourceFilter, stageFilter, updateUrlParams])

    const handlePriorityOnlyChange = useCallback((nextPriorityOnly: boolean) => {
        startFilterTransition(() => {
            setPriorityOnly(nextPriorityOnly)
            setPage(1)
            updateUrlParams(
                stageFilter,
                sourceFilter,
                queueFilter,
                debouncedSearch,
                ownerFilter,
                1,
                dateRange,
                customRange,
                dynamicFilter,
                nextPriorityOnly,
                sortBy,
                sortOrder,
            )
        })
    }, [customRange, dateRange, debouncedSearch, dynamicFilter, ownerFilter, queueFilter, sortBy, sortOrder, sourceFilter, stageFilter, updateUrlParams])

    const handlePageChange = useCallback((nextPage: number) => {
        startFilterTransition(() => {
            setPage(nextPage)
            updateUrlParams(
                stageFilter,
                sourceFilter,
                queueFilter,
                debouncedSearch,
                ownerFilter,
                nextPage,
                dateRange,
                customRange,
                dynamicFilter,
                priorityOnly,
                sortBy,
                sortOrder,
            )
        })
    }, [stageFilter, sourceFilter, queueFilter, debouncedSearch, ownerFilter, updateUrlParams, dateRange, customRange, dynamicFilter, priorityOnly, sortBy, sortOrder])

    const handlePresetChange = useCallback((preset: DateRangePreset) => {
        startFilterTransition(() => {
            setDateRange(preset)
            if (preset !== "custom") {
                setCustomRange({ from: undefined, to: undefined })
            }
            setPage(1)
            updateUrlParams(
                stageFilter,
                sourceFilter,
                queueFilter,
                debouncedSearch,
                ownerFilter,
                1,
                preset,
                preset === "custom" ? customRange : { from: undefined, to: undefined },
                dynamicFilter,
                priorityOnly,
                sortBy,
                sortOrder,
            )
        })
    }, [stageFilter, sourceFilter, queueFilter, debouncedSearch, ownerFilter, updateUrlParams, customRange, dynamicFilter, priorityOnly, sortBy, sortOrder])

    const handleCustomRangeChange = useCallback((range: { from: Date | undefined; to: Date | undefined }) => {
        startFilterTransition(() => {
            setCustomRange(range)
            if (dateRange !== "custom") {
                setDateRange("custom")
            }
            setPage(1)
            updateUrlParams(
                stageFilter,
                sourceFilter,
                queueFilter,
                debouncedSearch,
                ownerFilter,
                1,
                "custom",
                range,
                dynamicFilter,
                priorityOnly,
                sortBy,
                sortOrder,
            )
        })
    }, [stageFilter, sourceFilter, queueFilter, debouncedSearch, ownerFilter, updateUrlParams, dateRange, dynamicFilter, priorityOnly, sortBy, sortOrder])

    const handleIntelligentSuggestionToggle = useCallback(() => {
        handleDynamicFilterChange(dynamicFilter === "intelligent_any" ? null : "intelligent_any")
    }, [dynamicFilter, handleDynamicFilterChange])

    // Fetch queues for filter dropdown (case_manager+ only)
    const canSeeQueues = user?.role && ['case_manager', 'admin', 'developer'].includes(user.role)
    const isDeveloper = user?.role === "developer"
    const { data: queues } = useQueues(false, { enabled: !!canSeeQueues })
    const { data: defaultPipeline } = useDefaultPipeline()
    const stageOptions = defaultPipeline?.stages || []
    const stageById = new Map(stageOptions.map(stage => [stage.id, stage]))

    // Debounce search input
    useEffect(() => {
        const timer = setTimeout(() => setDebouncedSearch(searchQuery), 300)
        return () => clearTimeout(timer)
    }, [searchQuery])

    // Sync debouncedSearch to URL (separate effect to avoid circular updates)
    useEffect(() => {
        if (!hasSyncedSearchRef.current) {
            hasSyncedSearchRef.current = true
            return
        }
        const urlSearchValue = searchParams.get("q") || ""
        if (debouncedSearch !== urlSearchValue) {
            setPage(1)
            updateUrlParams(
                stageFilter,
                sourceFilter,
                queueFilter,
                debouncedSearch,
                ownerFilter,
                1,
                dateRange,
                customRange,
                dynamicFilter,
                priorityOnly,
                sortBy,
                sortOrder,
            )
        }
    }, [debouncedSearch, searchParams, stageFilter, sourceFilter, queueFilter, ownerFilter, updateUrlParams, dateRange, customRange, dynamicFilter, priorityOnly, sortBy, sortOrder])

    // Sync state when URL changes (back/forward)
    useEffect(() => {
        const dynamicFilterParam = searchParams.get("dynamic_filter")
        const nextDynamicFilter = isDynamicSurrogateFilter(dynamicFilterParam)
            ? dynamicFilterParam
            : null
        if (nextDynamicFilter !== dynamicFilter) {
            setDynamicFilter(nextDynamicFilter)
        }

        const nextStage = searchParams.get("stage") || "all"
        if (nextStage !== stageFilter) {
            setStageFilter(nextStage)
        }
        const nextSource = isSourceFilter(searchParams.get("source")) ? searchParams.get("source") as SourceFilter : "all"
        if (nextSource !== sourceFilter) {
            setSourceFilter(nextSource)
        }
        const nextQueue = searchParams.get("queue") || "all"
        if (nextQueue !== queueFilter) {
            setQueueFilter(nextQueue)
        }
        const nextOwner = canFilterByAssignee ? (searchParams.get("owner_id") || "all") : "all"
        if (nextOwner !== ownerFilter) {
            setOwnerFilter(nextOwner)
        }
        const nextPriorityOnly = searchParams.get("priority") === "only"
        if (nextPriorityOnly !== priorityOnly) {
            setPriorityOnly(nextPriorityOnly)
        }
        const nextSearch = searchParams.get("q") || ""
        if (nextSearch !== searchQuery) {
            setSearchQuery(nextSearch)
        }
        if (nextSearch !== debouncedSearch) {
            setDebouncedSearch(nextSearch)
        }
        const nextSortBy = searchParams.get("sort_by") || null
        if (nextSortBy !== sortBy) {
            setSortBy(nextSortBy)
        }
        const nextSortOrder = parseSortOrderParam(searchParams.get("sort_order"))
        if (nextSortOrder !== sortOrder) {
            setSortOrder(nextSortOrder)
        }

        const nextPage = parsePageParam(searchParams.get("page"))
        if (nextPage !== page) {
            setPage(nextPage)
        }
        const nextRange = isDateRangePreset(searchParams.get("range")) ? searchParams.get("range") as DateRangePreset : "all"
        if (nextRange !== dateRange) {
            setDateRange(nextRange)
        }
        if (nextRange === "custom") {
            const nextFrom = parseDateParam(searchParams.get("from"))
            const nextTo = parseDateParam(searchParams.get("to"))
            if (!datesEqual(nextFrom, customRange.from) || !datesEqual(nextTo, customRange.to)) {
                setCustomRange({ from: nextFrom, to: nextTo })
            }
        } else if (customRange.from || customRange.to) {
            setCustomRange({ from: undefined, to: undefined })
        }

    }, [canFilterByAssignee, currentQuery]) // eslint-disable-line react-hooks/exhaustive-deps

    // Convert date range to ISO strings
    const getDateRangeParams = () => {
        if (dateRange === 'all') return {}
        if (dateRange === 'custom' && customRange.from) {
            const params = { created_from: formatLocalDate(customRange.from) }
            return customRange.to ? { ...params, created_to: formatLocalDate(customRange.to) } : params
        }
        // For presets, calculate dates
        const now = new Date()
        let from: Date | undefined
        if (dateRange === 'today') {
            from = new Date(now.getFullYear(), now.getMonth(), now.getDate())
        } else if (dateRange === 'week') {
            from = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
        } else if (dateRange === 'month') {
            from = new Date(now.getFullYear(), now.getMonth(), 1)
        }
        return from ? { created_from: formatLocalDate(from) } : {}
    }

    const baseMassEditFilters: SurrogateMassEditStageFilters = {
        ...(stageFilter === "all" ? {} : { stage_ids: [stageFilter] }),
        ...(sourceFilter === "all" ? {} : { source: sourceFilter as SurrogateSource }),
        ...(queueFilter === "all" ? {} : { queue_id: queueFilter }),
        ...(ownerFilter === "all" ? {} : { owner_id: ownerFilter }),
        ...(priorityOnly ? { is_priority: true } : {}),
        ...(debouncedSearch ? { q: debouncedSearch } : {}),
        ...getDateRangeParams(),
    }

    const isIntelligentDynamicFilter = dynamicFilter?.startsWith("intelligent_") ?? false
    const intelligentSuggestionCount = intelligentSummary?.total ?? 0
    const hasIntelligentSuggestions = intelligentSuggestionCount > 0

    const createdDateFilters = {
        ...(dynamicFilter ? { dynamic_filter: dynamicFilter } : {}),
        ...(stageFilter === "all" ? {} : { stage_id: stageFilter }),
        ...(sourceFilter === "all" ? {} : { source: sourceFilter }),
        ...(priorityOnly ? { is_priority: true } : {}),
        ...(debouncedSearch ? { q: debouncedSearch } : {}),
        ...(queueFilter === "all" ? {} : { queue_id: queueFilter }),
        ...(ownerFilter === "all" ? {} : { owner_id: ownerFilter }),
    } as const

    const { data: availableCreatedDateKeys } = useSurrogateCreatedDates(createdDateFilters)

    const { data, isLoading, isError, error, refetch } = useSurrogates({
        page,
        per_page: perPage,
        ...getDateRangeParams(),
        ...(stageFilter === "all" ? {} : { stage_id: stageFilter }),
        ...(sourceFilter === "all" ? {} : { source: sourceFilter }),
        ...(priorityOnly ? { is_priority: true } : {}),
        ...(debouncedSearch ? { q: debouncedSearch } : {}),
        ...(queueFilter === "all" ? {} : { queue_id: queueFilter }),
        ...(ownerFilter === "all" ? {} : { owner_id: ownerFilter }),
        ...(dynamicFilter ? { dynamic_filter: dynamicFilter } : {}),
        ...(sortBy ? { sort_by: sortBy, sort_order: sortOrder } : {}),
    })

    const totalCount = data?.total ?? null
    const totalPages = data?.pages ?? null
    const hasTotal = totalCount !== null
    const totalCountValue = totalCount ?? 0
    const totalPagesValue = totalPages ?? 0
    const pageStart = (page - 1) * perPage + 1
    const pageEnd = data?.items?.length ? pageStart + data.items.length - 1 : 0

    const handleSort = (column: string) => {
        startFilterTransition(() => {
            const nextSortBy = column
            const nextSortOrder =
                sortBy === column ? (sortOrder === "asc" ? "desc" : "asc") : "desc"
            setSortBy(nextSortBy)
            setSortOrder(nextSortOrder)
            setPage(1)
            updateUrlParams(
                stageFilter,
                sourceFilter,
                queueFilter,
                debouncedSearch,
                ownerFilter,
                1,
                dateRange,
                customRange,
                dynamicFilter,
                priorityOnly,
                nextSortBy,
                nextSortOrder,
            )
        })
    }

    const archiveMutation = useArchiveSurrogate()
    const restoreMutation = useRestoreSurrogate()
    const updateMutation = useUpdateSurrogate()

    const hasActiveFilters =
        dynamicFilter !== null ||
        stageFilter !== "all" ||
        sourceFilter !== "all" ||
        queueFilter !== "all" ||
        ownerFilter !== "all" ||
        priorityOnly ||
        searchQuery !== "" ||
        dateRange !== "all"
    const hasActiveSecondaryFilters =
        sourceFilter !== "all" ||
        queueFilter !== "all" ||
        ownerFilter !== "all" ||
        (dynamicFilter !== null && dynamicFilter !== "intelligent_any") ||
        priorityOnly

    const resetFilters = useCallback(() => {
        setStageFilter("all")
        setSourceFilter("all")
        setQueueFilter("all")
        setOwnerFilter("all")
        setDynamicFilter(null)
        setPriorityOnly(false)
        setDateRange("all")
        setCustomRange({ from: undefined, to: undefined })
        setSearchQuery("")
        setDebouncedSearch("")
        setPage(1)
        setSortBy(null)
        setSortOrder("desc")
        setIsMoreFiltersOpen(false)
        setSelectedSurrogates(new Set())
        // Clear URL params
        router.replace('/surrogates', { scroll: false })
    }, [router])

    const clearSecondaryFilter = useCallback((filterKey: "source" | "queue" | "owner" | "dynamic" | "priority") => {
        if (filterKey === "source") {
            handleSourceChange("all")
            return
        }
        if (filterKey === "queue") {
            handleQueueChange("all")
            return
        }
        if (filterKey === "owner") {
            handleOwnerChange("all")
            return
        }

        if (filterKey === "dynamic") {
            handleDynamicFilterChange(null)
            return
        }

        handlePriorityOnlyChange(false)
    }, [handleDynamicFilterChange, handleOwnerChange, handlePriorityOnlyChange, handleQueueChange, handleSourceChange])

    const secondaryFilterChips = [
        ...(sourceFilter !== "all"
            ? [{
                key: "source" as const,
                label: `Source: ${getSourceFilterLabel(sourceFilter)}`,
            }]
            : []),
        ...(queueFilter !== "all"
            ? [{
                key: "queue" as const,
                label: `Queue: ${getQueueFilterLabel(queueFilter, queues)}`,
            }]
            : []),
        ...(ownerFilter !== "all"
            ? [{
                key: "owner" as const,
                label: `Assignee: ${getAssigneeFilterLabel(ownerFilter, assignees)}`,
            }]
            : []),
        ...(dynamicFilter && dynamicFilter !== "intelligent_any"
            ? [{
                key: "dynamic" as const,
                label: getDynamicFilterLabel(dynamicFilter),
            }]
            : []),
        ...(priorityOnly
            ? [{
                key: "priority" as const,
                label: "Priority Only",
            }]
            : []),
    ]

    // Multi-select handlers
    const handleSelectAll = (checked: boolean) => {
        if (checked && data?.items) {
            setSelectedSurrogates(new Set(data.items.map(s => s.id)))
        } else {
            setSelectedSurrogates(new Set())
        }
    }

    const handleSelectSurrogate = (surrogateId: string, checked: boolean) => {
        const newSelected = new Set(selectedSurrogates)
        if (checked) {
            newSelected.add(surrogateId)
        } else {
            newSelected.delete(surrogateId)
        }
        setSelectedSurrogates(newSelected)
    }

    const clearSelection = () => {
        setSelectedSurrogates(new Set())
    }

    const handleArchive = async (surrogateId: string) => {
        await archiveMutation.mutateAsync(surrogateId)
    }

    const handleRestore = async (surrogateId: string) => {
        await restoreMutation.mutateAsync(surrogateId)
    }

    const handleTogglePriority = async (surrogateId: string, currentPriority: boolean) => {
        await updateMutation.mutateAsync({ surrogateId, data: { is_priority: !currentPriority } })
    }

    const resetCreateForm = () => {
        setCreateForm({
            full_name: "",
            email: "",
            source: "manual",
        })
    }

    const handleCreate = async () => {
        try {
            const fullName = createForm.full_name.trim()
            const email = createForm.email.trim()
            if (!fullName || !email) {
                toast.error("Name and email are required")
                return
            }
            const created = await createMutation.mutateAsync({
                full_name: fullName,
                email,
                source: createForm.source,
                assign_to_user: user?.role === "intake_specialist",
            })
            setIsCreateOpen(false)
            resetCreateForm()
            toast.success("Surrogate created successfully")
            router.push(buildSurrogateDetailHref(created.id, currentListHref))
        } catch (error) {
            const message = error instanceof Error ? error.message : "Failed to create surrogate"
            toast.error(message)
        }
    }

    return (
        <div className="flex flex-col h-full overflow-hidden">
            {/* Page Header - Fixed Height */}
            <div className="flex-shrink-0 border-b border-border bg-background/95 backdrop-blur">
                <div className="flex h-14 items-center justify-between px-6">
                    <div>
                        <h1 className="text-xl font-semibold">Surrogates</h1>
                        <p className="text-sm text-muted-foreground">
                            {hasTotal ? totalCount.toLocaleString() : "—"} total surrogates
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        {isDeveloper && (
                            <Button
                                variant="outline"
                                onClick={() => setIsMassEditOpen(true)}
                                disabled={!stageOptions.length}
                            >
                                Mass Edit
                            </Button>
                        )}
                        <Button onClick={() => setIsCreateOpen(true)}>
                            <PlusIcon className="mr-2 size-4" />
                            New Surrogates
                        </Button>
                    </div>
                </div>
            </div>

            {/* Dev-only Mass Edit Modal */}
            {isDeveloper && (
                <MassEditStageModal
                    open={isMassEditOpen}
                    onOpenChange={setIsMassEditOpen}
                    stages={stageOptions}
                    baseFilters={baseMassEditFilters}
                />
            )}

            {/* Filters Row */}
            <div className="flex-shrink-0 border-b border-border px-6 py-3">
                <div className="flex flex-col gap-3">
                    <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
                        <div className="flex flex-wrap items-center gap-3">
                            {hasIntelligentSuggestions && (
                                <Button
                                    variant="outline"
                                    onClick={handleIntelligentSuggestionToggle}
                                    disabled={isFilterPending}
                                    className={cn(
                                        "border-sky-400/30 bg-background/90 text-sky-100 shadow-[0_0_0_1px_rgba(59,130,246,0.08),0_0_18px_-10px_rgba(56,189,248,0.95)] hover:border-sky-300/45 hover:bg-background hover:text-white hover:shadow-[0_0_0_1px_rgba(125,211,252,0.18),0_0_24px_-10px_rgba(56,189,248,1)]",
                                        dynamicFilter === "intelligent_any" &&
                                            "border-sky-300/60 bg-background text-white shadow-[0_0_0_1px_rgba(125,211,252,0.24),0_0_28px_-8px_rgba(56,189,248,1)]"
                                    )}
                                >
                                    Intelligent Suggestions ({intelligentSuggestionCount})
                                </Button>
                            )}

                            <div className="hidden md:block">
                                <Select
                                    value={stageFilter}
                                    onValueChange={(value) => handleStageChange(value || "all")}
                                >
                                    <SelectTrigger className="w-[180px]">
                                        <SelectValue placeholder="All Stages">
                                            {(value: string | null) => getStageFilterLabel(value, stageOptions)}
                                        </SelectValue>
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="all">All Stages</SelectItem>
                                        {stageOptions.map((stage) => (
                                            <SelectItem key={stage.id} value={stage.id}>
                                                {stage.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="hidden md:block">
                                <DateRangePicker
                                    preset={dateRange}
                                    onPresetChange={handlePresetChange}
                                    customRange={customRange}
                                    onCustomRangeChange={handleCustomRangeChange}
                                    availableDateKeys={availableCreatedDateKeys ?? []}
                                />
                            </div>

                            <Popover open={isMoreFiltersOpen} onOpenChange={setIsMoreFiltersOpen}>
                                <PopoverTrigger
                                    type="button"
                                    aria-label="More Filters"
                                    className={buttonVariants({
                                        variant: "outline",
                                        className: cn(
                                            "justify-between border-border/70 bg-background/85 shadow-xs backdrop-blur-sm",
                                            hasActiveSecondaryFilters &&
                                                "border-foreground/15 bg-accent/40 text-foreground shadow-[0_14px_30px_-24px_rgba(15,23,42,0.9)]"
                                        ),
                                    })}
                                >
                                    <SlidersHorizontalIcon className="size-4" />
                                    More Filters
                                </PopoverTrigger>
                                <PopoverContent
                                    align="end"
                                    className="w-[min(24rem,calc(100vw-2rem))] gap-4 border border-border/70 bg-background/95 p-4 shadow-[0_24px_64px_-28px_rgba(15,23,42,0.9)] backdrop-blur-xl"
                                >
                                    <div className="grid gap-4">
                                        <div className="grid gap-2">
                                            <Label>Source</Label>
                                            <Select
                                                value={sourceFilter}
                                                onValueChange={(value) =>
                                                    handleSourceChange(isSourceFilter(value) ? value : "all")
                                                }
                                            >
                                                <SelectTrigger>
                                                    <SelectValue placeholder="All Sources">
                                                        {(value: string | null) => getSourceFilterLabel(value)}
                                                    </SelectValue>
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="all">All Sources</SelectItem>
                                                    <SelectItem value="manual">Manual</SelectItem>
                                                    <SelectItem value="meta">Meta</SelectItem>
                                                    <SelectItem value="tiktok">TikTok</SelectItem>
                                                    <SelectItem value="google">Google</SelectItem>
                                                    <SelectItem value="website">Website</SelectItem>
                                                    <SelectItem value="referral">Referral</SelectItem>
                                                    <SelectItem value="other">Others</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>

                                        {canSeeQueues && queues && queues.length > 0 && (
                                            <div className="grid gap-2">
                                                <Label>Queue</Label>
                                                <Select
                                                    value={queueFilter}
                                                    onValueChange={(value) => handleQueueChange(value || "all")}
                                                >
                                                    <SelectTrigger>
                                                        <SelectValue placeholder="All Queues">
                                                            {(value: string | null) =>
                                                                getQueueFilterLabel(value, queues)
                                                            }
                                                        </SelectValue>
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        <SelectItem value="all">All Queues</SelectItem>
                                                        {queues.map((queue) => (
                                                            <SelectItem key={queue.id} value={queue.id}>
                                                                {queue.name}
                                                            </SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                        )}

                                        {canFilterByAssignee && (
                                            <div className="grid gap-2">
                                                <Label>Assignee</Label>
                                                <Select
                                                    value={ownerFilter}
                                                    onValueChange={(value) => handleOwnerChange(value || "all")}
                                                >
                                                    <SelectTrigger aria-label="Filter by assignee">
                                                        <SelectValue placeholder="All Assignees">
                                                            {(value: string | null) =>
                                                                getAssigneeFilterLabel(value, assignees)
                                                            }
                                                        </SelectValue>
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        <SelectItem value="all">All Assignees</SelectItem>
                                                        {(assignees ?? []).map((assignee) => (
                                                            <SelectItem key={assignee.id} value={assignee.id}>
                                                                {assignee.name}
                                                            </SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                        )}

                                        <div className="grid gap-2">
                                            <Label>Attention / Smart Filter</Label>
                                            <Select
                                                value={dynamicFilter ?? "none"}
                                                onValueChange={(value) =>
                                                    handleDynamicFilterChange(
                                                        value === "none" || !isDynamicSurrogateFilter(value)
                                                            ? null
                                                            : value
                                                    )
                                                }
                                            >
                                                <SelectTrigger>
                                                    <SelectValue placeholder="No smart filter">
                                                        {(value: string | null) =>
                                                            getDynamicFilterLabel(
                                                                value === "none" || !isDynamicSurrogateFilter(value)
                                                                    ? null
                                                                    : value
                                                            )
                                                        }
                                                    </SelectValue>
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="none">No smart filter</SelectItem>
                                                    {(Object.entries(DYNAMIC_FILTER_LABELS) as Array<[DynamicSurrogateFilter, string]>)
                                                        .filter(([key]) => key !== "intelligent_any")
                                                        .map(([key, label]) => (
                                                            <SelectItem key={key} value={key}>
                                                                {label}
                                                            </SelectItem>
                                                        ))}
                                                </SelectContent>
                                            </Select>
                                        </div>

                                        <div className="rounded-xl border border-border/70 bg-muted/30 p-3">
                                            <div className="flex items-start gap-3">
                                                <Checkbox
                                                    id="surrogate-priority-only"
                                                    checked={priorityOnly}
                                                    onCheckedChange={(checked) =>
                                                        handlePriorityOnlyChange(Boolean(checked))
                                                    }
                                                />
                                                <div className="space-y-1">
                                                    <Label htmlFor="surrogate-priority-only">Priority only</Label>
                                                    <p className="text-sm text-muted-foreground">
                                                        Show only surrogates marked as priority.
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </PopoverContent>
                            </Popover>
                        </div>

                        <div className="relative w-full xl:ml-auto xl:w-[320px] xl:flex-none">
                            <SearchIcon className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                            <Input
                                placeholder="Search surrogates..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="pl-9"
                                aria-label="Search surrogates"
                            />
                        </div>
                    </div>

                    {hasActiveFilters && (
                        <div className="flex flex-wrap items-center gap-2">
                            {secondaryFilterChips.map((chip) => (
                                <Button
                                    key={chip.key}
                                    variant="outline"
                                    size="sm"
                                    onClick={() => clearSecondaryFilter(chip.key)}
                                    className="gap-2"
                                >
                                    {chip.label}
                                    <XIcon className="size-3" />
                                </Button>
                            ))}
                            <Button variant="ghost" size="sm" onClick={resetFilters}>
                                Reset
                            </Button>
                        </div>
                    )}
                </div>
            </div>

            {/* Create Modal */}
            <Dialog open={isCreateOpen} onOpenChange={(open) => { setIsCreateOpen(open); if (!open) resetCreateForm() }}>
                <DialogContent className="max-w-lg">
                    <DialogHeader>
                        <DialogTitle>New Surrogates</DialogTitle>
                        <DialogDescription>Add a new surrogate to the system</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="surrogate-full-name">Full Name *</Label>
                            <Input
                                id="surrogate-full-name"
                                value={createForm.full_name}
                                onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
                                placeholder="Jane Smith"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="surrogate-email">Email *</Label>
                            <Input
                                id="surrogate-email"
                                type="email"
                                value={createForm.email}
                                onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                                placeholder="jane@example.com"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="surrogate-source">Source *</Label>
                            <Select
                                value={createForm.source}
                                onValueChange={(value) => setCreateForm({ ...createForm, source: value as SurrogateSource })}
                            >
                                <SelectTrigger id="surrogate-source">
                                    <SelectValue placeholder="Select a source" />
                                </SelectTrigger>
                                <SelectContent>
                                    {CREATE_SOURCE_OPTIONS.map((source) => (
                                        <SelectItem key={source.value} value={source.value}>
                                            {source.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <Card className="bg-muted/50">
                            <CardContent className="py-4 flex items-center justify-between gap-3">
                                <div>
                                    <p className="text-sm font-medium">Import CSV</p>
                                    <p className="text-xs text-muted-foreground">
                                        Bulk upload surrogates from a CSV file.
                                    </p>
                                </div>
                                <Button
                                    render={<Link href="/surrogates/import" />}
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setIsCreateOpen(false)}
                                >
                                    <UploadIcon className="mr-2 size-4" />
                                    Import CSV
                                </Button>
                            </CardContent>
                        </Card>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsCreateOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleCreate}
                            disabled={createMutation.isPending || !createForm.full_name.trim() || !createForm.email.trim()}
                        >
                            {createMutation.isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                            Create
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Scrollable Content Area */}
            <div className="flex-1 overflow-auto p-6">

                {/* Error State */}
                {isError && (
                    <Card className="p-6 text-center border-destructive/40 bg-destructive/5">
                        <p className="text-destructive">Unable to load surrogates.</p>
                        {error instanceof Error && (
                            <p className="mt-2 text-xs text-muted-foreground">{error.message}</p>
                        )}
                        <Button variant="outline" size="sm" className="mt-4" onClick={() => refetch()}>
                            Retry
                        </Button>
                    </Card>
                )}

                {/* Loading State */}
                {isLoading && (
                    <Card className="p-12 flex items-center justify-center">
                        <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                    </Card>
                )}

                {/* Empty State */}
                {!isLoading && !isError && data?.items.length === 0 && (
                    <Card className="p-12 text-center">
                        <div className="flex flex-col items-center gap-3">
                            <p className="text-muted-foreground">
                                {isIntelligentDynamicFilter
                                    ? "Intelligent suggestions are not available right now."
                                    : hasActiveFilters
                                    ? "No surrogates match your filters"
                                    : "No surrogates yet"
                                }
                            </p>
                            {isIntelligentDynamicFilter && (
                                <p className="text-sm text-muted-foreground">
                                    All suggested cases have been addressed.
                                </p>
                            )}
                            {hasActiveFilters && (
                                <Button variant="outline" onClick={resetFilters}>
                                    Clear Filters
                                </Button>
                            )}
                        </div>
                    </Card>
                )}

                {/* Surrogates Table */}
                {!isLoading && !isError && data && data.items.length > 0 && (
                    <Card className="overflow-hidden py-0">
                        <SurrogatesFloatingScrollbar>
                            <Table className={cn("min-w-max [&_th]:!text-center [&_td]:!text-center [&_th>div]:justify-center transition-opacity", isFilterPending && "opacity-60")}>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="w-[40px]">
                                            <Checkbox
                                                checked={data?.items && data.items.length > 0 && selectedSurrogates.size === data.items.length}
                                                onCheckedChange={(checked) => handleSelectAll(!!checked)}
                                                aria-label="Select all surrogates"
                                            />
                                        </TableHead>
                                        <SortableTableHead column="surrogate_number" label="Surrogate #" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} className="w-[100px]" />
                                        <SortableTableHead column="full_name" label="Name" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <TableHead>Age</TableHead>
                                        <TableHead>BMI</TableHead>
                                        <SortableTableHead column="race" label="Race" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <SortableTableHead column="state" label="State" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <TableHead>Phone</TableHead>
                                        <TableHead>Email</TableHead>
                                        <TableHead>Stage</TableHead>
                                        <SortableTableHead column="source" label="Source" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <TableHead>Assigned To</TableHead>
                                        <SortableTableHead column="created_at" label="Created" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <SortableTableHead column="updated_at" label="Last Modified" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <TableHead className="w-[50px]"></TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {data.items.map((surrogateItem) => {
                                        const stage = stageById.get(surrogateItem.stage_id)
                                        const statusLabel = surrogateItem.status_label || stage?.label || "Unknown"
                                        const statusColor = stage?.color || "#6B7280"
                                        const detailHref = buildSurrogateDetailHref(surrogateItem.id, currentListHref)
                                        // Apply gold styling for entire row on priority surrogates
                                        const rowClass = surrogateItem.is_priority ? "text-amber-600" : ""
                                        const mutedCellClass = surrogateItem.is_priority ? "text-amber-600" : "text-muted-foreground"

                                        return (
                                            <TableRow
                                                key={surrogateItem.id}
                                                className={cn(rowClass, "[content-visibility:auto] [contain-intrinsic-size:auto_53px]")}
                                            >
                                                <TableCell>
                                                    <Checkbox
                                                        checked={selectedSurrogates.has(surrogateItem.id)}
                                                        onCheckedChange={(checked) => handleSelectSurrogate(surrogateItem.id, !!checked)}
                                                        aria-label={`Select ${surrogateItem.full_name}`}
                                                    />
                                                </TableCell>
                                                <TableCell>
                                                    <Link href={detailHref} className={`font-medium hover:underline ${surrogateItem.is_priority ? "text-amber-600" : "text-primary"}`}>
                                                        #{surrogateItem.surrogate_number}
                                                    </Link>
                                                </TableCell>
                                                <TableCell className="font-medium">{surrogateItem.full_name}</TableCell>
                                                <TableCell className={cn("text-center", mutedCellClass)}>
                                                    {surrogateItem.age ?? "—"}
                                                </TableCell>
                                                <TableCell className={cn("text-center", mutedCellClass)}>
                                                    {surrogateItem.bmi ?? "—"}
                                                </TableCell>
                                                <TableCell className={mutedCellClass}>
                                                    {formatRace(surrogateItem.race) || "—"}
                                                </TableCell>
                                                <TableCell className={mutedCellClass}>
                                                    {surrogateItem.state || "—"}
                                                </TableCell>
                                                <TableCell className={mutedCellClass}>
                                                    {surrogateItem.phone || "—"}
                                                </TableCell>
                                                <TableCell className={cn("max-w-[200px] truncate", mutedCellClass)} title={surrogateItem.email}>
                                                    {surrogateItem.email}
                                                </TableCell>
                                                <TableCell>
                                                    <Badge style={{ backgroundColor: statusColor, color: "white" }}>
                                                        {statusLabel}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant="secondary" className="capitalize">
                                                        {getSourceFilterLabel(surrogateItem.source)}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>
                                                    {surrogateItem.owner_name ? (
                                                        <TooltipProvider>
                                                            <Tooltip>
                                                                <TooltipTrigger>
                                                                    <Avatar className="h-7 w-7">
                                                                        <AvatarFallback className="text-xs">
                                                                            {getInitials(surrogateItem.owner_name)}
                                                                        </AvatarFallback>
                                                                    </Avatar>
                                                                </TooltipTrigger>
                                                                <TooltipContent>
                                                                    {surrogateItem.owner_name}
                                                                </TooltipContent>
                                                            </Tooltip>
                                                        </TooltipProvider>
                                                    ) : (
                                                        <span className="text-muted-foreground">—</span>
                                                    )}
                                                </TableCell>
                                                <TableCell className={mutedCellClass}>
                                                    {formatDate(surrogateItem.created_at)}
                                                </TableCell>
                                                <TableCell className={mutedCellClass}>
                                                    {formatDate(surrogateItem.updated_at)}
                                                </TableCell>
                                                <TableCell>
                                                    <DropdownMenu>
                                                        <DropdownMenuTrigger
                                                            className={cn(buttonVariants({ variant: "ghost", size: "icon" }), "size-8")}
                                                            aria-label={`Actions for ${surrogateItem.full_name}`}
                                                        >
                                                            <MoreVerticalIcon className="size-4" />
                                                        </DropdownMenuTrigger>
                                                        <DropdownMenuContent align="end">
                                                            <DropdownMenuItem onClick={() => window.location.href = detailHref}>
                                                                View Details
                                                            </DropdownMenuItem>
                                                            {canManagePriority && (
                                                                <DropdownMenuItem
                                                                    onClick={() => handleTogglePriority(surrogateItem.id, surrogateItem.is_priority)}
                                                                    disabled={updateMutation.isPending}
                                                                >
                                                                    {surrogateItem.is_priority ? "Remove Priority" : "Mark as Priority"}
                                                                </DropdownMenuItem>
                                                            )}
                                                            {!surrogateItem.is_archived ? (
                                                                <DropdownMenuItem
                                                                    onClick={() => handleArchive(surrogateItem.id)}
                                                                    disabled={archiveMutation.isPending}
                                                                    className="text-destructive"
                                                                >
                                                                    Archive
                                                                </DropdownMenuItem>
                                                            ) : (
                                                                <DropdownMenuItem
                                                                    onClick={() => handleRestore(surrogateItem.id)}
                                                                    disabled={restoreMutation.isPending}
                                                                >
                                                                    Restore
                                                                </DropdownMenuItem>
                                                            )}
                                                        </DropdownMenuContent>
                                                    </DropdownMenu>
                                                </TableCell>
                                            </TableRow>
                                        )
                                    })}
                                </TableBody>
                            </Table>
                        </SurrogatesFloatingScrollbar>

                        {/* Pagination */}
                        {totalPages && totalPages > 1 && (
                            <div className="flex items-center justify-between border-t border-border px-6 py-4">
                                <div className="text-sm text-muted-foreground">
                                    {hasTotal ? (
                                        <>Showing {pageStart}-{Math.min(page * perPage, totalCountValue)} of {totalCountValue} surrogates</>
                                    ) : (
                                        <>Showing {pageStart}-{pageEnd} surrogates</>
                                    )}
                                </div>
                                <div className="flex items-center gap-2 flex-wrap">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        disabled={page === 1}
                                        onClick={() => handlePageChange(Math.max(1, page - 1))}
                                    >
                                        Previous
                                    </Button>
                                    {[...Array(Math.min(5, totalPagesValue))].map((_, i) => {
                                        const pageNum = i + 1
                                        return (
                                            <Button
                                                key={pageNum}
                                                variant={page === pageNum ? "default" : "outline"}
                                                size="sm"
                                                onClick={() => handlePageChange(pageNum)}
                                            >
                                                {pageNum}
                                            </Button>
                                        )
                                    })}
                                    {totalPagesValue > 5 && <span className="text-muted-foreground">...</span>}
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        disabled={page >= totalPagesValue}
                                        onClick={() => handlePageChange(Math.min(totalPagesValue, page + 1))}
                                    >
                                        Next
                                    </Button>
                                    <PaginationJump
                                        page={page}
                                        totalPages={totalPagesValue}
                                        onPageChange={handlePageChange}
                                    />
                                </div>
                            </div>
                        )}
                    </Card>
                )}

                {/* Floating Action Bar for Multi-Select */}
                {selectedSurrogates.size > 0 && (
                    <FloatingActionBar
                        selectedCount={selectedSurrogates.size}
                        selectedSurrogateIds={Array.from(selectedSurrogates)}
                        onClear={clearSelection}
                    />
                )}
            </div>
        </div>
    )
}
