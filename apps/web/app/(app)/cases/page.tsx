"use client"

import { useState, useEffect, useCallback } from "react"
import Link from "next/link"
import { useSearchParams, useRouter } from "next/navigation"
import { Card } from "@/components/ui/card"
import { Button, buttonVariants } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Checkbox } from "@/components/ui/checkbox"
import { MoreVerticalIcon, SearchIcon, XIcon, LoaderIcon, ArchiveIcon, UserPlusIcon, UsersIcon, UploadIcon } from "lucide-react"
import { SortableTableHead } from "@/components/ui/sortable-table-head"
import { useCases, useArchiveCase, useRestoreCase, useUpdateCase, useAssignees, useBulkAssign, useBulkArchive } from "@/lib/hooks/use-cases"
import { useQueues } from "@/lib/hooks/use-queues"
import { useDefaultPipeline } from "@/lib/hooks/use-pipelines"
import { useAuth } from "@/lib/auth-context"
import type { CaseSource } from "@/lib/types/case"
import { DateRangePicker, type DateRangePreset } from "@/components/ui/date-range-picker"
import { cn } from "@/lib/utils"
import { formatLocalDate, parseDateInput } from "@/lib/utils/date"

// Format date for display
function formatDate(dateString: string): string {
    const date = parseDateInput(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffDays === 0) return "Today"
    if (diffDays === 1) return "Yesterday"
    if (diffDays < 7) return `${diffDays} days ago`
    if (diffDays < 14) return "1 week ago"
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
    if (diffDays < 60) return "1 month ago"
    return `${Math.floor(diffDays / 30)} months ago`
}

// Get initials from name
function getInitials(name: string | null): string {
    if (!name) return "?"
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

// Floating Action Bar for bulk operations
function FloatingActionBar({
    selectedCount,
    selectedCaseIds,
    onClear,
}: {
    selectedCount: number
    selectedCaseIds: string[]
    onClear: () => void
}) {
    const { user } = useAuth()
    const { data: assignees } = useAssignees()
    const bulkAssignMutation = useBulkAssign()
    const bulkArchiveMutation = useBulkArchive()

    const canAssign = user?.role && ['case_manager', 'admin', 'developer'].includes(user.role)

    const handleAssign = async (userId: string) => {
        await bulkAssignMutation.mutateAsync({
            case_ids: selectedCaseIds,
            owner_type: 'user',
            owner_id: userId,
        })
        onClear()
    }

    const handleArchive = async () => {
        await bulkArchiveMutation.mutateAsync(selectedCaseIds)
        onClear()
    }

    const isLoading = bulkAssignMutation.isPending || bulkArchiveMutation.isPending

    return (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50">
            <div className="bg-primary text-primary-foreground shadow-lg rounded-lg px-6 py-3 flex items-center gap-4">
                <span className="font-medium">{selectedCount} case{selectedCount > 1 ? 's' : ''} selected</span>
                <div className="h-4 w-px bg-primary-foreground/30" />

                {/* Assign Dropdown - case_manager+ only */}
                {canAssign && (
                    <DropdownMenu>
                        <DropdownMenuTrigger
                            className={cn(buttonVariants({ variant: "secondary", size: "sm" }))}
                            disabled={isLoading}
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

const VALID_SOURCES: (CaseSource | "all")[] = ["all", "manual", "meta", "website", "referral"]
export default function CasesPage() {
    const searchParams = useSearchParams()
    const router = useRouter()

    // Read initial values from URL params
    const urlStage = searchParams.get("stage")
    const urlSource = searchParams.get("source") as CaseSource | "all" | null
    const urlQueue = searchParams.get("queue")
    const urlSearch = searchParams.get("q")

    const [stageFilter, setStageFilter] = useState<string>(urlStage || "all")
    const [sourceFilter, setSourceFilter] = useState<CaseSource | "all">(
        urlSource && VALID_SOURCES.includes(urlSource) ? urlSource : "all"
    )
    const [queueFilter, setQueueFilter] = useState<string>(urlQueue || "all")
    const [dateRange, setDateRange] = useState<DateRangePreset>('all')
    const [customRange, setCustomRange] = useState<{ from: Date | undefined; to: Date | undefined }>({
        from: undefined,
        to: undefined,
    })
    const [searchQuery, setSearchQuery] = useState(urlSearch || "")
    const [debouncedSearch, setDebouncedSearch] = useState(urlSearch || "")
    const [page, setPage] = useState(1)
    const [selectedCases, setSelectedCases] = useState<Set<string>>(new Set())
    const [sortBy, setSortBy] = useState<string | null>(null)
    const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc")
    const perPage = 20
    const { user } = useAuth()

    // Sync state changes back to URL (preserving other params)
    const updateUrlParams = useCallback((stage: string, source: CaseSource | "all", queue: string, search: string) => {
        const newParams = new URLSearchParams(searchParams.toString())
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
        const newUrl = newParams.toString() ? `?${newParams}` : ""
        router.replace(`/cases${newUrl}`, { scroll: false })
    }, [searchParams, router])

    // Update URL when filters change
    const handleStageChange = useCallback((stage: string) => {
        setStageFilter(stage)
        updateUrlParams(stage, sourceFilter, queueFilter, debouncedSearch)
    }, [sourceFilter, queueFilter, debouncedSearch, updateUrlParams])

    const handleSourceChange = useCallback((source: CaseSource | "all") => {
        setSourceFilter(source)
        updateUrlParams(stageFilter, source, queueFilter, debouncedSearch)
    }, [stageFilter, queueFilter, debouncedSearch, updateUrlParams])

    const handleQueueChange = useCallback((queue: string) => {
        setQueueFilter(queue)
        updateUrlParams(stageFilter, sourceFilter, queue, debouncedSearch)
    }, [stageFilter, sourceFilter, debouncedSearch, updateUrlParams])

    // Fetch queues for filter dropdown (case_manager+ only)
    const canSeeQueues = user?.role && ['case_manager', 'admin', 'developer'].includes(user.role)
    const { data: queues } = useQueues()
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
        // Only sync if this is from a user search, not initial load
        const urlSearch = searchParams.get("q")
        if (debouncedSearch !== (urlSearch || "")) {
            updateUrlParams(stageFilter, sourceFilter, queueFilter, debouncedSearch)
        }
    }, [debouncedSearch]) // eslint-disable-line react-hooks/exhaustive-deps

    // Reset page when filters change
    useEffect(() => {
        setPage(1)
    }, [stageFilter, sourceFilter, queueFilter, debouncedSearch, dateRange, customRange])

    // Convert date range to ISO strings
    const getDateRangeParams = () => {
        if (dateRange === 'all') return {}
        if (dateRange === 'custom' && customRange.from) {
            return {
                created_from: formatLocalDate(customRange.from),
                created_to: customRange.to ? formatLocalDate(customRange.to) : undefined,
            }
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

    const { data, isLoading, isError, error } = useCases({
        page,
        per_page: perPage,
        stage_id: stageFilter === "all" ? undefined : stageFilter,
        source: sourceFilter === "all" ? undefined : sourceFilter,
        q: debouncedSearch || undefined,
        queue_id: queueFilter !== "all" ? queueFilter : undefined,
        sort_by: sortBy || undefined,
        sort_order: sortOrder,
        ...getDateRangeParams(),
    })

    const handleSort = (column: string) => {
        if (sortBy === column) {
            setSortOrder(sortOrder === "asc" ? "desc" : "asc")
        } else {
            setSortBy(column)
            setSortOrder("desc")
        }
    }

    const archiveMutation = useArchiveCase()
    const restoreMutation = useRestoreCase()
    const updateMutation = useUpdateCase()

    const hasActiveFilters = stageFilter !== "all" || sourceFilter !== "all" || queueFilter !== "all" || searchQuery !== "" || dateRange !== "all"

    const resetFilters = useCallback(() => {
        setStageFilter("all")
        setSourceFilter("all")
        setQueueFilter("all")
        setDateRange("all")
        setCustomRange({ from: undefined, to: undefined })
        setSearchQuery("")
        setSelectedCases(new Set())
        // Clear URL params
        router.replace('/cases', { scroll: false })
    }, [router])

    // Multi-select handlers
    const handleSelectAll = (checked: boolean) => {
        if (checked && data?.items) {
            setSelectedCases(new Set(data.items.map(c => c.id)))
        } else {
            setSelectedCases(new Set())
        }
    }

    const handleSelectCase = (caseId: string, checked: boolean) => {
        const newSelected = new Set(selectedCases)
        if (checked) {
            newSelected.add(caseId)
        } else {
            newSelected.delete(caseId)
        }
        setSelectedCases(newSelected)
    }

    const clearSelection = () => {
        setSelectedCases(new Set())
    }

    const handleArchive = async (caseId: string) => {
        await archiveMutation.mutateAsync(caseId)
    }

    const handleRestore = async (caseId: string) => {
        await restoreMutation.mutateAsync(caseId)
    }

    const handleTogglePriority = async (caseId: string, currentPriority: boolean) => {
        await updateMutation.mutateAsync({ caseId, data: { is_priority: !currentPriority } })
    }

    return (
        <div className="flex flex-col h-full overflow-hidden">
            {/* Sticky Header */}
            <div className="flex-shrink-0 p-6 pb-0">
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h1 className="text-2xl font-bold">Cases</h1>
                        <p className="text-muted-foreground">
                            {data?.total ?? 0} total cases
                        </p>
                    </div>
                    <Link href="/settings/import">
                        <Button>
                            <UploadIcon className="mr-2 size-4" />
                            Import CSV
                        </Button>
                    </Link>
                </div>

                {/* Filters Row */}
                <div className="flex flex-wrap items-center gap-3">
                    <Select value={stageFilter} onValueChange={(value) => handleStageChange(value || "all")}>
                        <SelectTrigger className="w-[180px]">
                            <SelectValue placeholder="All Stages">
                                {(value: string | null) => {
                                    if (!value || value === "all") return "All Stages"
                                    const stage = stageOptions.find(s => s.id === value)
                                    return stage?.label ?? value
                                }}
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

                    <Select value={sourceFilter} onValueChange={(value) => handleSourceChange((value || "all") as CaseSource | "all")}>
                        <SelectTrigger className="w-[180px]">
                            <SelectValue placeholder="All Sources">
                                {(value: string | null) => {
                                    if (!value || value === "all") return "All Sources"
                                    const labels: Record<string, string> = {
                                        manual: "Manual",
                                        meta: "Meta",
                                        website: "Website",
                                        referral: "Referral",
                                    }
                                    return labels[value] ?? value
                                }}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Sources</SelectItem>
                            <SelectItem value="manual">Manual</SelectItem>
                            <SelectItem value="meta">Meta</SelectItem>
                            <SelectItem value="website">Website</SelectItem>
                            <SelectItem value="referral">Referral</SelectItem>
                        </SelectContent>
                    </Select>

                    <DateRangePicker
                        preset={dateRange}
                        onPresetChange={setDateRange}
                        customRange={customRange}
                        onCustomRangeChange={setCustomRange}
                    />

                    {/* Queue Filter (case_manager+ only) */}
                    {canSeeQueues && queues && queues.length > 0 && (
                        <Select value={queueFilter} onValueChange={(value) => handleQueueChange(value || "all")}>
                            <SelectTrigger className="w-[180px]">
                                <UsersIcon className="h-4 w-4 mr-2" />
                                <SelectValue placeholder="All Queues">
                                    {(value: string | null) => {
                                        if (!value || value === "all") return "All Queues"
                                        const queue = queues?.find(q => q.id === value)
                                        return queue?.name ?? value
                                    }}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All Queues</SelectItem>
                                {queues.map((q) => (
                                    <SelectItem key={q.id} value={q.id}>{q.name}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    )}

                    <div className="relative ml-auto w-full max-w-sm">
                        <SearchIcon className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            placeholder="Search cases..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="pl-9"
                        />
                    </div>

                    {hasActiveFilters && (
                        <Button variant="ghost" onClick={resetFilters}>
                            <XIcon className="mr-2 size-4" />
                            Reset
                        </Button>
                    )}
                </div>
            </div>

            {/* Scrollable Content Area */}
            <div className="flex-1 overflow-auto p-6 pt-4">

                {/* Error State */}
                {isError && (
                    <Card className="p-6 text-center border-destructive/40 bg-destructive/5">
                        <p className="text-destructive">Unable to load cases.</p>
                        {error instanceof Error && (
                            <p className="mt-2 text-xs text-muted-foreground">{error.message}</p>
                        )}
                    </Card>
                )}

                {/* Loading State */}
                {isLoading && (
                    <Card className="p-12 flex items-center justify-center">
                        <LoaderIcon className="size-8 animate-spin text-muted-foreground" />
                    </Card>
                )}

                {/* Empty State */}
                {!isLoading && !isError && data?.items.length === 0 && (
                    <Card className="p-12 text-center">
                        <div className="flex flex-col items-center gap-3">
                            <p className="text-muted-foreground">
                                {hasActiveFilters
                                    ? "No cases match your filters"
                                    : "No cases yet"
                                }
                            </p>
                            {hasActiveFilters && (
                                <Button variant="outline" onClick={resetFilters}>
                                    Clear Filters
                                </Button>
                            )}
                        </div>
                    </Card>
                )}

                {/* Cases Table */}
                {!isLoading && !isError && data && data.items.length > 0 && (
                    <Card className="overflow-hidden py-0">
                        <div className="overflow-x-auto">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="w-[40px]">
                                            <Checkbox
                                                checked={data?.items && data.items.length > 0 && selectedCases.size === data.items.length}
                                                onCheckedChange={(checked) => handleSelectAll(!!checked)}
                                            />
                                        </TableHead>
                                        <SortableTableHead column="case_number" label="Case #" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} className="w-[100px]" />
                                        <SortableTableHead column="full_name" label="Name" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <SortableTableHead column="date_of_birth" label="Age" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <TableHead>BMI</TableHead>
                                        <SortableTableHead column="race" label="Race" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <SortableTableHead column="state" label="State" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <SortableTableHead column="phone" label="Phone" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <SortableTableHead column="email" label="Email" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <TableHead>Stage</TableHead>
                                        <SortableTableHead column="source" label="Source" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <TableHead>Assigned To</TableHead>
                                        <SortableTableHead column="created_at" label="Created" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <TableHead className="w-[50px]"></TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {data.items.map((caseItem) => {
                                        const stage = stageById.get(caseItem.stage_id)
                                        const statusLabel = stage?.label || "Unknown"
                                        const statusColor = stage?.color || "#6B7280"
                                        // Apply gold styling for entire row on priority cases
                                        const rowClass = caseItem.is_priority ? "text-amber-600" : ""

                                        return (
                                            <TableRow key={caseItem.id} className={rowClass}>
                                                <TableCell>
                                                    <Checkbox
                                                        checked={selectedCases.has(caseItem.id)}
                                                        onCheckedChange={(checked) => handleSelectCase(caseItem.id, !!checked)}
                                                    />
                                                </TableCell>
                                                <TableCell>
                                                    <Link href={`/cases/${caseItem.id}`} className={`font-medium hover:underline ${caseItem.is_priority ? "text-amber-600" : "text-primary"}`}>
                                                        #{caseItem.case_number}
                                                    </Link>
                                                </TableCell>
                                                <TableCell className="font-medium">{caseItem.full_name}</TableCell>
                                                <TableCell className="text-center">
                                                    {caseItem.age ?? "—"}
                                                </TableCell>
                                                <TableCell className="text-center">
                                                    {caseItem.bmi ?? "—"}
                                                </TableCell>
                                                <TableCell>
                                                    {caseItem.race || "—"}
                                                </TableCell>
                                                <TableCell>
                                                    {caseItem.state || "—"}
                                                </TableCell>
                                                <TableCell>
                                                    {caseItem.phone || "—"}
                                                </TableCell>
                                                <TableCell className="max-w-[200px] truncate" title={caseItem.email}>
                                                    {caseItem.email}
                                                </TableCell>
                                                <TableCell>
                                                    <Badge style={{ backgroundColor: statusColor, color: "white" }}>
                                                        {statusLabel}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant="secondary" className="capitalize">{caseItem.source}</Badge>
                                                </TableCell>
                                                <TableCell>
                                                    {caseItem.owner_name ? (
                                                        <TooltipProvider>
                                                            <Tooltip>
                                                                <TooltipTrigger>
                                                                    <Avatar className="h-7 w-7">
                                                                        <AvatarFallback className="text-xs">
                                                                            {getInitials(caseItem.owner_name)}
                                                                        </AvatarFallback>
                                                                    </Avatar>
                                                                </TooltipTrigger>
                                                                <TooltipContent>
                                                                    {caseItem.owner_name}
                                                                </TooltipContent>
                                                            </Tooltip>
                                                        </TooltipProvider>
                                                    ) : (
                                                        <span className="text-muted-foreground">—</span>
                                                    )}
                                                </TableCell>
                                                <TableCell>
                                                    {formatDate(caseItem.created_at)}
                                                </TableCell>
                                                <TableCell>
                                                    <DropdownMenu>
                                                        <DropdownMenuTrigger className="inline-flex items-center justify-center size-8 p-0 rounded-md hover:bg-accent hover:text-accent-foreground">
                                                            <span className="inline-flex items-center justify-center">
                                                                <MoreVerticalIcon className="size-4" />
                                                            </span>
                                                        </DropdownMenuTrigger>
                                                        <DropdownMenuContent align="end">
                                                            <DropdownMenuItem onClick={() => window.location.href = `/cases/${caseItem.id}`}>
                                                                View Details
                                                            </DropdownMenuItem>
                                                            <DropdownMenuItem
                                                                onClick={() => handleTogglePriority(caseItem.id, caseItem.is_priority)}
                                                                disabled={updateMutation.isPending}
                                                            >
                                                                {caseItem.is_priority ? "Remove Priority" : "Mark as Priority"}
                                                            </DropdownMenuItem>
                                                            {!caseItem.is_archived ? (
                                                                <DropdownMenuItem
                                                                    onClick={() => handleArchive(caseItem.id)}
                                                                    disabled={archiveMutation.isPending}
                                                                    className="text-destructive"
                                                                >
                                                                    Archive
                                                                </DropdownMenuItem>
                                                            ) : (
                                                                <DropdownMenuItem
                                                                    onClick={() => handleRestore(caseItem.id)}
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
                        </div>

                        {/* Pagination */}
                        {data.pages > 1 && (
                            <div className="flex items-center justify-between border-t border-border px-6 py-4">
                                <div className="text-sm text-muted-foreground">
                                    Showing {((page - 1) * perPage) + 1}-{Math.min(page * perPage, data.total)} of {data.total} cases
                                </div>
                                <div className="flex items-center gap-2">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        disabled={page === 1}
                                        onClick={() => setPage(p => Math.max(1, p - 1))}
                                    >
                                        Previous
                                    </Button>
                                    {[...Array(Math.min(5, data.pages))].map((_, i) => {
                                        const pageNum = i + 1
                                        return (
                                            <Button
                                                key={pageNum}
                                                variant={page === pageNum ? "default" : "outline"}
                                                size="sm"
                                                onClick={() => setPage(pageNum)}
                                            >
                                                {pageNum}
                                            </Button>
                                        )
                                    })}
                                    {data.pages > 5 && <span className="text-muted-foreground">...</span>}
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        disabled={page >= data.pages}
                                        onClick={() => setPage(p => Math.min(data.pages, p + 1))}
                                    >
                                        Next
                                    </Button>
                                </div>
                            </div>
                        )}
                    </Card>
                )}

                {/* Floating Action Bar for Multi-Select */}
                {selectedCases.size > 0 && (
                    <FloatingActionBar
                        selectedCount={selectedCases.size}
                        selectedCaseIds={Array.from(selectedCases)}
                        onClear={clearSelection}
                    />
                )}
            </div>
        </div>
    )
}
