"use client"

import { useState, useEffect, useRef } from "react"
import type { Route } from "next"
import Link from "@/components/app-link"
import { useSearchParams, useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { PaginationJump } from "@/components/ui/pagination-jump"
import {
    Table,
    TableBody,
    TableCell,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    PlusIcon,
    SearchIcon,
    Loader2Icon,
    UsersIcon,
    ChevronLeftIcon,
    ChevronRightIcon,
    AlertCircleIcon,
} from "lucide-react"
import { SortableTableHead } from "@/components/ui/sortable-table-head"
import { IntendedParentFormFields } from "@/components/intended-parents/IntendedParentFormFields"
import {
    EMPTY_INTENDED_PARENT_FORM_VALUES,
    buildIntendedParentCreatePayload,
    type IntendedParentFormValues,
} from "@/components/intended-parents/intended-parent-form-values"
import {
    useIntendedParents,
    useIntendedParentStats,
    useIntendedParentCreatedDates,
    useCreateIntendedParent,
} from "@/lib/hooks/use-intended-parents"
import { useIntendedParentStatuses } from "@/lib/hooks/use-metadata"
import {
    getIntendedParentStageOptions,
    getIntendedParentStatusLabel,
    getIntendedParentStatusStyle,
} from "@/lib/intended-parent-stage-utils"
import type { IntendedParentListItem } from "@/lib/types/intended-parent"
import { DateRangePicker, type DateRangePreset } from "@/components/ui/date-range-picker"
import { formatLocalDate, parseDateInput } from "@/lib/utils/date"
import { PermissionDeniedState } from "@/components/error-state"
import { isPermissionError } from "@/lib/error-utils"
import { toast } from "@/components/ui/toast"

const VALID_DATE_RANGES: DateRangePreset[] = ["all", "today", "week", "month", "custom"]
type DateRangeSelection = { from: Date | undefined; to: Date | undefined }
type RouterReplace = ReturnType<typeof useRouter>["replace"]
type SearchParamsSnapshot = {
    get: (key: string) => string | null
    toString: () => string
}
type QueryDraft<T> = {
    query: string
    value: T
}
type IntendedParentListUrlState = {
    statusFilter: string
    search: string
    page: number
    dateRange: DateRangePreset
    customRange: DateRangeSelection
}

const isDateRangePreset = (value: string | null): value is DateRangePreset =>
    value !== null && VALID_DATE_RANGES.includes(value as DateRangePreset)

const parsePageParam = (value: string | null): number => {
    const parsed = Number(value)
    return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : 1
}

const parseDateParam = (value: string | null): Date | undefined => {
    if (!value) return undefined
    const parsed = parseDateInput(value)
    return Number.isNaN(parsed.getTime()) ? undefined : parsed
}

function resolveQueryDraft<T>(
    draft: QueryDraft<T> | null,
    currentQuery: string,
    fallback: T,
): T {
    return draft?.query === currentQuery ? draft.value : fallback
}

function readIntendedParentListUrlState(searchParams: SearchParamsSnapshot): IntendedParentListUrlState {
    const range = isDateRangePreset(searchParams.get("range"))
        ? searchParams.get("range") as DateRangePreset
        : "all"

    return {
        statusFilter: searchParams.get("status") || "all",
        search: searchParams.get("q") || "",
        page: parsePageParam(searchParams.get("page")),
        dateRange: range,
        customRange: range === "custom"
            ? {
                  from: parseDateParam(searchParams.get("from")),
                  to: parseDateParam(searchParams.get("to")),
              }
            : { from: undefined, to: undefined },
    }
}

function updateIntendedParentListUrl(
    replace: RouterReplace,
    searchParams: SearchParamsSnapshot,
    status: string,
    searchValue: string,
    currentPage: number,
    range: DateRangePreset,
    rangeDates: DateRangeSelection
) {
    const newParams = new URLSearchParams(searchParams.toString())
    if (status !== "all") {
        newParams.set("status", status)
    } else {
        newParams.delete("status")
    }
    if (searchValue) {
        newParams.set("q", searchValue)
    } else {
        newParams.delete("q")
    }
    if (currentPage > 1) {
        newParams.set("page", String(currentPage))
    } else {
        newParams.delete("page")
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
    const nextQuery = newParams.toString()
    const currentQuery = searchParams.toString()
    if (nextQuery === currentQuery) return
    const newUrl = nextQuery ? `/intended-parents?${nextQuery}` : "/intended-parents"
    const currentUrl = currentQuery ? `/intended-parents?${currentQuery}` : "/intended-parents"
    if (newUrl === currentUrl) return
    replace(newUrl as Route, { scroll: false })
}

function formatIntendedParentCreatedDate(dateStr: string) {
    const parsed = parseDateInput(dateStr)
    if (Number.isNaN(parsed.getTime())) return "—"
    return parsed.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
    })
}

type IntendedParentStatusMetadata = Parameters<typeof getIntendedParentStatusLabel>[0]
type IntendedParentStageOption = ReturnType<typeof getIntendedParentStageOptions>[number]
type IntendedParentStatsData = {
    total: number
    by_status: Record<string, number>
}
type IntendedParentListData = {
    items: IntendedParentListItem[]
    total: number
    per_page: number
}
type IntendedParentSortOrder = "asc" | "desc"

function IntendedParentsPageHeader({
    onCreateClick,
}: {
    onCreateClick: () => void
}) {
    return (
        <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="flex h-16 items-center justify-between px-6">
                <h1 className="text-2xl font-semibold">Intended Parents</h1>
                <Button onClick={onCreateClick}>
                    <PlusIcon className="mr-2 size-4" />
                    New Intended Parent
                </Button>
            </div>
        </div>
    )
}

function IntendedParentStatsGrid({
    stats,
    statusOptions,
}: {
    stats: IntendedParentStatsData | undefined
    statusOptions: IntendedParentStageOption[]
}) {
    return (
        <div className="grid gap-4 md:grid-cols-5">
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">Total</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold">{stats?.total ?? 0}</div>
                </CardContent>
            </Card>
            {statusOptions.map((status) => (
                <Card key={status.id}>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">
                            {status.label}
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">
                            {stats?.by_status[status.stage_key] ?? 0}
                        </div>
                    </CardContent>
                </Card>
            ))}
        </div>
    )
}

function IntendedParentsFilters({
    statusFilter,
    statusOptions,
    statusMetadata,
    dateRange,
    customRange,
    availableDateKeys,
    search,
    onStatusChange,
    onPresetChange,
    onCustomRangeChange,
    onSearchChange,
}: {
    statusFilter: string
    statusOptions: IntendedParentStageOption[]
    statusMetadata: IntendedParentStatusMetadata
    dateRange: DateRangePreset
    customRange: DateRangeSelection
    availableDateKeys: string[]
    search: string
    onStatusChange: (status: string) => void
    onPresetChange: (preset: DateRangePreset) => void
    onCustomRangeChange: (range: DateRangeSelection) => void
    onSearchChange: (search: string) => void
}) {
    return (
        <div className="flex flex-col gap-4 md:flex-row md:items-center">
            <Select value={statusFilter} onValueChange={(value) => { if (value) onStatusChange(value) }}>
                <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="All Stages">
                        {(value: string | null) => {
                            if (!value || value === "all") return "All Stages"
                            return getIntendedParentStatusLabel(statusMetadata, value)
                        }}
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="all">All Stages</SelectItem>
                    {statusOptions.map((status) => (
                        <SelectItem key={status.id} value={status.stage_key}>
                            {status.label}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
            <DateRangePicker
                preset={dateRange}
                onPresetChange={onPresetChange}
                customRange={customRange}
                onCustomRangeChange={onCustomRangeChange}
                availableDateKeys={availableDateKeys}
            />
            <div className="flex-1" />
            <div className="relative w-full max-w-sm">
                <SearchIcon className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                    placeholder="Search name, number, email, phone…"
                    value={search}
                    onChange={(event) => {
                        onSearchChange(event.target.value)
                    }}
                    className="pl-9"
                />
            </div>
        </div>
    )
}

function IntendedParentsTableCard({
    data,
    isLoading,
    isError,
    error,
    search,
    statusFilter,
    sortBy,
    sortOrder,
    statusMetadata,
    onSort,
    onRetry,
}: {
    data: IntendedParentListData | undefined
    isLoading: boolean
    isError: boolean
    error: unknown
    search: string
    statusFilter: string
    sortBy: string | null
    sortOrder: IntendedParentSortOrder
    statusMetadata: IntendedParentStatusMetadata
    onSort: (column: string) => void
    onRetry: () => void
}) {
    return (
        <Card className="py-0">
            <CardContent className="p-0">
                {isLoading ? (
                    <div className="flex items-center justify-center py-12">
                        <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                        <span className="ml-2 text-muted-foreground">Loading…</span>
                    </div>
                ) : isPermissionError(error) ? (
                    <PermissionDeniedState
                        description="Your account does not have permission to view intended parents. Ask an admin to update your role or permissions."
                        onRetry={onRetry}
                    />
                ) : isError ? (
                    <div className="flex flex-col items-center justify-center py-12 text-center">
                        <AlertCircleIcon className="size-12 text-destructive mb-4" />
                        <h3 className="text-lg font-medium">Failed to load intended parents</h3>
                        <p className="text-muted-foreground">Please try again or contact support if the issue persists.</p>
                        <Button variant="outline" size="sm" className="mt-4" onClick={onRetry}>
                            Retry
                        </Button>
                    </div>
                ) : !data?.items.length ? (
                    <div className="flex flex-col items-center justify-center py-12 text-center">
                        <UsersIcon className="size-12 text-muted-foreground mb-4" />
                        <h3 className="text-lg font-medium">No intended parents found</h3>
                        <p className="text-muted-foreground">
                            {search || statusFilter !== "all"
                                ? "Try adjusting your filters"
                                : "Create your first intended parent to get started"}
                        </p>
                    </div>
                ) : (
                    <Table className="[&_th]:!text-center [&_td]:!text-center [&_th>div]:justify-center">
                        <TableHeader>
                            <TableRow>
                                <SortableTableHead column="intended_parent_number" label="IP#" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                                <SortableTableHead column="full_name" label="Name" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                                <SortableTableHead column="email" label="Email" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                                <SortableTableHead column="phone" label="Phone" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                                <SortableTableHead column="state" label="State" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                                <SortableTableHead column="partner_name" label="Partner" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                                <SortableTableHead column="status" label="Stage" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                                <SortableTableHead column="created_at" label="Created" currentSort={sortBy} currentOrder={sortOrder} onSort={onSort} />
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {data.items.map((ip) => (
                                <TableRow key={ip.id} className="cursor-pointer hover:bg-muted/50">
                                    <TableCell>
                                        <Link
                                            href={`/intended-parents/${ip.id}`}
                                            className="font-medium text-primary hover:underline"
                                        >
                                            {ip.intended_parent_number}
                                        </Link>
                                    </TableCell>
                                    <TableCell className="font-medium">
                                        {ip.full_name}
                                    </TableCell>
                                    <TableCell className="text-muted-foreground">{ip.email}</TableCell>
                                    <TableCell className="text-muted-foreground">{ip.phone || "—"}</TableCell>
                                    <TableCell className="text-muted-foreground">{ip.state || "—"}</TableCell>
                                    <TableCell className="text-muted-foreground">{ip.partner_name || "—"}</TableCell>
                                    <TableCell>
                                        <Badge
                                            variant="outline"
                                            style={getIntendedParentStatusStyle(
                                                statusMetadata,
                                                ip.stage_key ?? ip.status,
                                            )}
                                        >
                                            {getIntendedParentStatusLabel(
                                                statusMetadata,
                                                ip.stage_key ?? ip.status,
                                                ip.status_label,
                                            )}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-muted-foreground">
                                        {formatIntendedParentCreatedDate(ip.created_at)}
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                )}
            </CardContent>
        </Card>
    )
}

function IntendedParentsPagination({
    data,
    page,
    totalPages,
    onPageChange,
}: {
    data: IntendedParentListData | undefined
    page: number
    totalPages: number
    onPageChange: (page: number) => void
}) {
    if (!data || data.total <= data.per_page) return null

    return (
        <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
                Showing {(page - 1) * data.per_page + 1} to{" "}
                {Math.min(page * data.per_page, data.total)} of {data.total}
            </p>
            <div className="flex items-center gap-2 flex-wrap">
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onPageChange(Math.max(1, page - 1))}
                    disabled={page === 1}
                >
                    <ChevronLeftIcon className="size-4" />
                </Button>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onPageChange(Math.min(totalPages, page + 1))}
                    disabled={page === totalPages}
                >
                    <ChevronRightIcon className="size-4" />
                </Button>
                <PaginationJump page={page} totalPages={totalPages} onPageChange={onPageChange} />
            </div>
        </div>
    )
}

function CreateIntendedParentDialog({
    open,
    formData,
    isPending,
    onOpenChange,
    onFieldChange,
    onCancel,
    onCreate,
}: {
    open: boolean
    formData: IntendedParentFormValues
    isPending: boolean
    onOpenChange: (open: boolean) => void
    onFieldChange: <K extends keyof IntendedParentFormValues>(
        field: K,
        value: IntendedParentFormValues[K],
    ) => void
    onCancel: () => void
    onCreate: () => void
}) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-lg">
                <DialogHeader>
                    <DialogTitle>New Intended Parent</DialogTitle>
                    <DialogDescription>Add a new intended parent to the system</DialogDescription>
                </DialogHeader>
                <IntendedParentFormFields
                    values={formData}
                    onChange={onFieldChange}
                    idPrefix="create_"
                    showAddressSection={false}
                    showClinicSection={false}
                />
                <DialogFooter>
                    <Button variant="outline" onClick={onCancel}>
                        Cancel
                    </Button>
                    <Button
                        onClick={onCreate}
                        disabled={
                            isPending ||
                            !formData.full_name.trim() ||
                            !formData.email.trim()
                        }
                    >
                        {isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                        Create
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

export default function IntendedParentsPage() {
    const searchParams = useSearchParams()
    const { replace } = useRouter()
    const currentQuery = searchParams.toString()
    const urlState = readIntendedParentListUrlState(searchParams)
    const [searchDraft, setSearchDraft] = useState<QueryDraft<string> | null>(null)
    const [statusDraft, setStatusDraft] = useState<QueryDraft<string> | null>(null)
    const [pageDraft, setPageDraft] = useState<QueryDraft<number> | null>(null)
    const [dateSelectionDraft, setDateSelectionDraft] =
        useState<QueryDraft<{ range: DateRangePreset; customRange: DateRangeSelection }> | null>(null)
    const search = resolveQueryDraft(searchDraft, currentQuery, urlState.search)
    const statusFilter = resolveQueryDraft(statusDraft, currentQuery, urlState.statusFilter)
    const page = resolveQueryDraft(pageDraft, currentQuery, urlState.page)
    const dateSelection = resolveQueryDraft(dateSelectionDraft, currentQuery, {
        range: urlState.dateRange,
        customRange: urlState.customRange,
    })
    const dateRange = dateSelection.range
    const customRange = dateSelection.customRange
    const [isCreateOpen, setIsCreateOpen] = useState(false)
    const [sortBy, setSortBy] = useState<string | null>("intended_parent_number")
    const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc")
    const searchDebounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

    useEffect(() => {
        return () => {
            if (searchDebounceTimerRef.current) {
                clearTimeout(searchDebounceTimerRef.current)
                searchDebounceTimerRef.current = null
            }
        }
    }, [currentQuery])

    const clearPendingSearchUpdate = () => {
        if (searchDebounceTimerRef.current) {
            clearTimeout(searchDebounceTimerRef.current)
            searchDebounceTimerRef.current = null
        }
    }

    // Handle status filter change
    const handleStatusChange = (status: string) => {
        clearPendingSearchUpdate()
        setStatusDraft({ query: currentQuery, value: status })
        setPageDraft({ query: currentQuery, value: 1 })
        updateIntendedParentListUrl(replace, searchParams, status, search, 1, dateRange, customRange)
    }

    const handlePageChange = (nextPage: number) => {
        clearPendingSearchUpdate()
        setPageDraft({ query: currentQuery, value: nextPage })
        updateIntendedParentListUrl(
            replace,
            searchParams,
            statusFilter,
            search,
            nextPage,
            dateRange,
            customRange,
        )
    }

    const handlePresetChange = (preset: DateRangePreset) => {
        const nextCustomRange = preset === "custom" ? customRange : { from: undefined, to: undefined }
        clearPendingSearchUpdate()
        setDateSelectionDraft({
            query: currentQuery,
            value: { range: preset, customRange: nextCustomRange },
        })
        setPageDraft({ query: currentQuery, value: 1 })
        updateIntendedParentListUrl(
            replace,
            searchParams,
            statusFilter,
            search,
            1,
            preset,
            nextCustomRange,
        )
    }

    const handleCustomRangeChange = (range: DateRangeSelection) => {
        clearPendingSearchUpdate()
        setDateSelectionDraft({
            query: currentQuery,
            value: { range: "custom", customRange: range },
        })
        setPageDraft({ query: currentQuery, value: 1 })
        updateIntendedParentListUrl(replace, searchParams, statusFilter, search, 1, "custom", range)
    }

    const handleSearchChange = (nextSearch: string) => {
        setSearchDraft({ query: currentQuery, value: nextSearch })
        setPageDraft({ query: currentQuery, value: 1 })
        clearPendingSearchUpdate()
        const scheduledQuery = currentQuery
        searchDebounceTimerRef.current = setTimeout(() => {
            searchDebounceTimerRef.current = null
            if (searchParams.toString() !== scheduledQuery) return
            updateIntendedParentListUrl(
                replace,
                searchParams,
                statusFilter,
                nextSearch,
                1,
                dateRange,
                customRange,
            )
        }, 300)
    }

    // Form state
    const [formData, setFormData] = useState<IntendedParentFormValues>(EMPTY_INTENDED_PARENT_FORM_VALUES)

    // Queries
    const getDateRangeParams = () => {
        if (dateRange === 'all') return {}
        if (dateRange === 'custom' && customRange.from) {
            const params = { created_after: formatLocalDate(customRange.from) }
            return customRange.to ? { ...params, created_before: formatLocalDate(customRange.to) } : params
        }
        const now = new Date()
        let from: Date | undefined
        if (dateRange === 'today') {
            from = new Date(now.getFullYear(), now.getMonth(), now.getDate())
        } else if (dateRange === 'week') {
            from = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
        } else if (dateRange === 'month') {
            from = new Date(now.getFullYear(), now.getMonth(), 1)
        }
        return from ? { created_after: formatLocalDate(from) } : {}
    }

    const filters = {
        page,
        per_page: 20,
        sort_order: sortOrder,
        ...getDateRangeParams(),
        ...(urlState.search ? { q: urlState.search } : {}),
        ...(statusFilter !== "all" ? { status: [statusFilter] } : {}),
        ...(sortBy ? { sort_by: sortBy } : {}),
    }
    const { data, isLoading, isError, error, refetch } = useIntendedParents(filters)
    const { data: availableCreatedDateKeys } = useIntendedParentCreatedDates({
        ...(urlState.search ? { q: urlState.search } : {}),
        ...(statusFilter !== "all" ? { status: [statusFilter] } : {}),
    })
    const { data: stats } = useIntendedParentStats()
    const { data: stageOptionsResponse } = useIntendedParentStatuses()
    const createMutation = useCreateIntendedParent()

    const handleSort = (column: string) => {
        if (sortBy === column) {
            setSortOrder(sortOrder === "asc" ? "desc" : "asc")
        } else {
            setSortBy(column)
            setSortOrder("desc")
        }
    }

    const resetForm = () => {
        setFormData(EMPTY_INTENDED_PARENT_FORM_VALUES)
    }

    const handleCreate = async () => {
        try {
            await createMutation.mutateAsync(
                buildIntendedParentCreatePayload(formData),
            )
            setIsCreateOpen(false)
            resetForm()
            toast.success("Intended parent created successfully")
        } catch (error) {
            const message = error instanceof Error ? error.message : "Failed to create intended parent"
            toast.error(message)
        }
    }

    const updateFormField = <K extends keyof IntendedParentFormValues>(
        field: K,
        value: IntendedParentFormValues[K],
    ) => {
        setFormData((previous) => ({ ...previous, [field]: value }))
    }

    const totalPages = data ? Math.ceil(data.total / data.per_page) : 1
    const statusOptions = getIntendedParentStageOptions(stageOptionsResponse?.statuses)

    return (
        <div className="flex flex-col h-full overflow-hidden">
            <IntendedParentsPageHeader onCreateClick={() => setIsCreateOpen(true)} />

            <div className="flex-1 p-6 space-y-6">
                <IntendedParentStatsGrid stats={stats} statusOptions={statusOptions} />
                <IntendedParentsFilters
                    statusFilter={statusFilter}
                    statusOptions={statusOptions}
                    statusMetadata={stageOptionsResponse?.statuses}
                    dateRange={dateRange}
                    customRange={customRange}
                    availableDateKeys={availableCreatedDateKeys ?? []}
                    search={search}
                    onStatusChange={handleStatusChange}
                    onPresetChange={handlePresetChange}
                    onCustomRangeChange={handleCustomRangeChange}
                    onSearchChange={handleSearchChange}
                />
                <IntendedParentsTableCard
                    data={data}
                    isLoading={isLoading}
                    isError={isError}
                    error={error}
                    search={search}
                    statusFilter={statusFilter}
                    sortBy={sortBy}
                    sortOrder={sortOrder}
                    statusMetadata={stageOptionsResponse?.statuses}
                    onSort={handleSort}
                    onRetry={() => { void refetch() }}
                />
                <IntendedParentsPagination
                    data={data}
                    page={page}
                    totalPages={totalPages}
                    onPageChange={handlePageChange}
                />
            </div>

            <CreateIntendedParentDialog
                open={isCreateOpen}
                formData={formData}
                isPending={createMutation.isPending}
                onOpenChange={(open) => { setIsCreateOpen(open); if (!open) resetForm() }}
                onFieldChange={updateFormField}
                onCancel={() => setIsCreateOpen(false)}
                onCreate={handleCreate}
            />
        </div>
    )
}
