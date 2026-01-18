"use client"

import { useState, useCallback, useEffect } from "react"
import Link from "next/link"
import { useSearchParams, useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
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
import { Textarea } from "@/components/ui/textarea"
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
import {
    useIntendedParents,
    useIntendedParentStats,
    useCreateIntendedParent,
} from "@/lib/hooks/use-intended-parents"
import type { IntendedParentStatus, IntendedParentListItem } from "@/lib/types/intended-parent"
import { DateRangePicker, type DateRangePreset } from "@/components/ui/date-range-picker"
import { formatLocalDate, parseDateInput } from "@/lib/utils/date"
import { toast } from "sonner"
import { US_STATES } from "@/lib/constants/us-states"

const STATUS_LABELS: Record<IntendedParentStatus, string> = {
    new: "New",
    ready_to_match: "Ready to Match",
    matched: "Matched",
    delivered: "Delivered",
}

const STATUS_COLORS: Record<IntendedParentStatus, string> = {
    new: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    ready_to_match: "bg-amber-500/10 text-amber-600 border-amber-500/20",
    matched: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20",
    delivered: "bg-teal-500/10 text-teal-600 border-teal-500/20",
}

const STATUS_OPTIONS: IntendedParentStatus[] = ["new", "ready_to_match", "matched", "delivered"]
const VALID_STATUSES = ["all", ...STATUS_OPTIONS]
const VALID_DATE_RANGES: DateRangePreset[] = ["all", "today", "week", "month", "custom"]
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

const datesEqual = (left?: Date, right?: Date) => {
    return (left?.getTime() ?? null) === (right?.getTime() ?? null)
}

export default function IntendedParentsPage() {
    const searchParams = useSearchParams()
    const router = useRouter()
    const currentQuery = searchParams.toString()

    // Read initial values from URL params
    const urlStatus = searchParams.get("status")
    const urlSearch = searchParams.get("q")
    const urlPage = searchParams.get("page")
    const urlRange = searchParams.get("range")
    const urlFrom = searchParams.get("from")
    const urlTo = searchParams.get("to")

    const [search, setSearch] = useState(urlSearch || "")
    const [debouncedSearch, setDebouncedSearch] = useState(urlSearch || "")
    const [statusFilter, setStatusFilter] = useState<string>(
        urlStatus && VALID_STATUSES.includes(urlStatus) ? urlStatus : "all"
    )
    const initialRange = isDateRangePreset(urlRange) ? urlRange : "all"
    const initialCustomRange = initialRange === "custom"
        ? {
            from: parseDateParam(urlFrom),
            to: parseDateParam(urlTo),
        }
        : { from: undefined, to: undefined }
    const [dateRange, setDateRange] = useState<DateRangePreset>(initialRange)
    const [customRange, setCustomRange] = useState<{ from: Date | undefined; to: Date | undefined }>(initialCustomRange)
    const [page, setPage] = useState(parsePageParam(urlPage))
    const [isCreateOpen, setIsCreateOpen] = useState(false)
    const [sortBy, setSortBy] = useState<string | null>("intended_parent_number")
    const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc")

    // Sync state changes back to URL
    const updateUrlParams = useCallback((
        status: string,
        searchValue: string,
        currentPage: number,
        range: DateRangePreset,
        rangeDates: { from: Date | undefined; to: Date | undefined }
    ) => {
        const newParams = new URLSearchParams()
        if (status !== "all") {
            newParams.set("status", status)
        }
        if (searchValue) {
            newParams.set("q", searchValue)
        }
        if (currentPage > 1) {
            newParams.set("page", String(currentPage))
        }
        if (range !== "all") {
            newParams.set("range", range)
            if (range === "custom") {
                if (rangeDates.from) {
                    newParams.set("from", formatLocalDate(rangeDates.from))
                }
                if (rangeDates.to) {
                    newParams.set("to", formatLocalDate(rangeDates.to))
                }
            }
        }
        const nextQuery = newParams.toString()
        if (nextQuery === currentQuery) return
        const newUrl = nextQuery ? `?${nextQuery}` : ""
        router.replace(`/intended-parents${newUrl}`, { scroll: false })
    }, [router, currentQuery])

    // Handle status filter change
    const handleStatusChange = useCallback((status: string) => {
        setStatusFilter(status)
        setPage(1)
        updateUrlParams(status, debouncedSearch, 1, dateRange, customRange)
    }, [debouncedSearch, updateUrlParams, dateRange, customRange])

    const handlePageChange = useCallback((nextPage: number) => {
        setPage(nextPage)
        updateUrlParams(statusFilter, debouncedSearch, nextPage, dateRange, customRange)
    }, [statusFilter, debouncedSearch, updateUrlParams, dateRange, customRange])

    const handlePresetChange = useCallback((preset: DateRangePreset) => {
        setDateRange(preset)
        if (preset !== "custom") {
            setCustomRange({ from: undefined, to: undefined })
        }
        setPage(1)
        updateUrlParams(statusFilter, debouncedSearch, 1, preset, preset === "custom" ? customRange : { from: undefined, to: undefined })
    }, [statusFilter, debouncedSearch, updateUrlParams, customRange])

    const handleCustomRangeChange = useCallback((range: { from: Date | undefined; to: Date | undefined }) => {
        setCustomRange(range)
        if (dateRange !== "custom") {
            setDateRange("custom")
        }
        setPage(1)
        updateUrlParams(statusFilter, debouncedSearch, 1, "custom", range)
    }, [statusFilter, debouncedSearch, updateUrlParams, dateRange])

    // Debounce search input
    useEffect(() => {
        const timer = setTimeout(() => setDebouncedSearch(search), 300)
        return () => clearTimeout(timer)
    }, [search])

    // Sync debouncedSearch to URL
    useEffect(() => {
        const urlSearchValue = searchParams.get("q") || ""
        if (debouncedSearch !== urlSearchValue) {
            setPage(1)
            updateUrlParams(statusFilter, debouncedSearch, 1, dateRange, customRange)
        }
    }, [debouncedSearch, searchParams, statusFilter, updateUrlParams, dateRange, customRange])

    // Sync state when URL changes (back/forward)
    useEffect(() => {
        const nextStatus = searchParams.get("status") && VALID_STATUSES.includes(searchParams.get("status") as string)
            ? searchParams.get("status") as string
            : "all"
        if (nextStatus !== statusFilter) {
            setStatusFilter(nextStatus)
        }
        const nextSearch = searchParams.get("q") || ""
        if (nextSearch !== search) {
            setSearch(nextSearch)
        }
        if (nextSearch !== debouncedSearch) {
            setDebouncedSearch(nextSearch)
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
    }, [currentQuery]) // eslint-disable-line react-hooks/exhaustive-deps

    // Form state
    const [formData, setFormData] = useState({
        full_name: "",
        email: "",
        phone: "",
        state: "",
        budget: "",
        notes_internal: "",
    })

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
        ...(debouncedSearch ? { q: debouncedSearch } : {}),
        ...(statusFilter !== "all" ? { status: [statusFilter] } : {}),
        ...(sortBy ? { sort_by: sortBy } : {}),
    }
    const { data, isLoading, isError, refetch } = useIntendedParents(filters)
    const { data: stats } = useIntendedParentStats()
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
        setFormData({
            full_name: "",
            email: "",
            phone: "",
            state: "",
            budget: "",
            notes_internal: "",
        })
    }

    const handleCreate = async () => {
        try {
            const phone = formData.phone.trim()
            const state = formData.state.trim()
            const notesInternal = formData.notes_internal.trim()
            await createMutation.mutateAsync({
                full_name: formData.full_name,
                email: formData.email,
                ...(phone ? { phone } : {}),
                ...(state ? { state } : {}),
                ...(formData.budget ? { budget: parseFloat(formData.budget) } : {}),
                ...(notesInternal ? { notes_internal: notesInternal } : {}),
            })
            setIsCreateOpen(false)
            resetForm()
            toast.success("Intended parent created successfully")
        } catch (error) {
            const message = error instanceof Error ? error.message : "Failed to create intended parent"
            toast.error(message)
        }
    }

    const formatDate = (dateStr: string) => {
        const parsed = parseDateInput(dateStr)
        if (Number.isNaN(parsed.getTime())) return "—"
        return parsed.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
        })
    }

    const formatBudget = (budget: number | null) => {
        if (!budget) return "—"
        return new Intl.NumberFormat("en-US", {
            style: "currency",
            currency: "USD",
            maximumFractionDigits: 0,
        }).format(budget)
    }

    const totalPages = data ? Math.ceil(data.total / data.per_page) : 1

    return (
        <div className="flex flex-col h-full overflow-hidden">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <h1 className="text-2xl font-semibold">Intended Parents</h1>
                    <Button onClick={() => setIsCreateOpen(true)}>
                        <PlusIcon className="mr-2 size-4" />
                        New Intended Parent
                    </Button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-6 space-y-6">
                {/* Stats Cards */}
                <div className="grid gap-4 md:grid-cols-5">
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">Total</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{stats?.total ?? 0}</div>
                        </CardContent>
                    </Card>
                    {STATUS_OPTIONS.map((status) => (
                        <Card key={status}>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-muted-foreground">
                                    {STATUS_LABELS[status]}
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold">{stats?.by_status[status] ?? 0}</div>
                            </CardContent>
                        </Card>
                    ))}
                </div>

                {/* Filters */}
                <div className="flex flex-col gap-4 md:flex-row md:items-center">
                    <Select value={statusFilter} onValueChange={(v) => { if (v) handleStatusChange(v) }}>
                        <SelectTrigger className="w-[180px]">
                            <SelectValue placeholder="All Statuses">
                                {(value: string | null) => {
                                    if (!value || value === "all") return "All Statuses"
                                    const status = STATUS_OPTIONS.find((option) => option === value)
                                    return status ? STATUS_LABELS[status] : value
                                }}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Statuses</SelectItem>
                            <SelectItem value="new">New</SelectItem>
                            <SelectItem value="ready_to_match">Ready to Match</SelectItem>
                            <SelectItem value="matched">Matched</SelectItem>
                            <SelectItem value="delivered">Delivered</SelectItem>
                        </SelectContent>
                    </Select>
                    <DateRangePicker
                        preset={dateRange}
                        onPresetChange={handlePresetChange}
                        customRange={customRange}
                        onCustomRangeChange={handleCustomRangeChange}
                    />
                    <div className="flex-1" />
                    <div className="relative w-full max-w-sm">
                        <SearchIcon className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            placeholder="Search name, number, email, phone..."
                            value={search}
                            onChange={(e) => {
                                setSearch(e.target.value)
                                setPage(1)
                            }}
                            className="pl-9"
                        />
                    </div>
                </div>

                {/* Table */}
                <Card className="py-0">
                    <CardContent className="p-0">
                        {isLoading ? (
                            <div className="flex items-center justify-center py-12">
                                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                                <span className="ml-2 text-muted-foreground">Loading...</span>
                            </div>
                        ) : isError ? (
                            <div className="flex flex-col items-center justify-center py-12 text-center">
                                <AlertCircleIcon className="size-12 text-destructive mb-4" />
                                <h3 className="text-lg font-medium">Failed to load intended parents</h3>
                                <p className="text-muted-foreground">Please try again or contact support if the issue persists.</p>
                                <Button variant="outline" size="sm" className="mt-4" onClick={() => refetch()}>
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
                                        <SortableTableHead column="intended_parent_number" label="IP#" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <SortableTableHead column="full_name" label="Name" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <SortableTableHead column="email" label="Email" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <SortableTableHead column="phone" label="Phone" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <SortableTableHead column="state" label="State" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <SortableTableHead column="budget" label="Budget" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <SortableTableHead column="status" label="Status" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <SortableTableHead column="created_at" label="Created" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {data.items.map((ip: IntendedParentListItem) => (
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
                                            <TableCell>{formatBudget(ip.budget)}</TableCell>
                                            <TableCell>
                                                <Badge className={STATUS_COLORS[ip.status]}>
                                                    {STATUS_LABELS[ip.status]}
                                                </Badge>
                                            </TableCell>
                                            <TableCell className="text-muted-foreground">
                                                {formatDate(ip.created_at)}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        )}
                    </CardContent>
                </Card>

                {/* Pagination */}
                {data && data.total > data.per_page && (
                    <div className="flex items-center justify-between">
                        <p className="text-sm text-muted-foreground">
                            Showing {(page - 1) * data.per_page + 1} to{" "}
                            {Math.min(page * data.per_page, data.total)} of {data.total}
                        </p>
                        <div className="flex items-center gap-2 flex-wrap">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handlePageChange(Math.max(1, page - 1))}
                                disabled={page === 1}
                            >
                                <ChevronLeftIcon className="size-4" />
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handlePageChange(Math.min(totalPages, page + 1))}
                                disabled={page === totalPages}
                            >
                                <ChevronRightIcon className="size-4" />
                            </Button>
                            <PaginationJump page={page} totalPages={totalPages} onPageChange={handlePageChange} />
                        </div>
                    </div>
                )}
            </div>

            {/* Create Modal */}
            <Dialog open={isCreateOpen} onOpenChange={(open) => { setIsCreateOpen(open); if (!open) resetForm() }}>
                <DialogContent className="max-w-lg">
                    <DialogHeader>
                        <DialogTitle>New Intended Parent</DialogTitle>
                        <DialogDescription>Add a new intended parent to the system</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="full_name">Full Name *</Label>
                            <Input
                                id="full_name"
                                value={formData.full_name}
                                onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                                placeholder="John and Jane Doe"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="email">Email *</Label>
                            <Input
                                id="email"
                                type="email"
                                value={formData.email}
                                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                placeholder="john@example.com"
                            />
                        </div>
                        <div className="grid gap-4 md:grid-cols-2">
                            <div className="space-y-2">
                                <Label htmlFor="phone">Phone</Label>
                                <Input
                                    id="phone"
                                    value={formData.phone}
                                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                                    placeholder="+1 (555) 123-4567"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="state">State</Label>
                                <Select
                                    value={formData.state || undefined}
                                    onValueChange={(value) => setFormData({ ...formData, state: value ?? "" })}
                                >
                                    <SelectTrigger id="state">
                                        <SelectValue placeholder="Select a state" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {US_STATES.map((state) => (
                                            <SelectItem key={state.value} value={state.value}>
                                                {state.label} ({state.value})
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="budget">Budget</Label>
                            <Input
                                id="budget"
                                type="number"
                                value={formData.budget}
                                onChange={(e) => setFormData({ ...formData, budget: e.target.value })}
                                placeholder="100000"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="notes">Internal Notes</Label>
                            <Textarea
                                id="notes"
                                value={formData.notes_internal}
                                onChange={(e) => setFormData({ ...formData, notes_internal: e.target.value })}
                                placeholder="Notes visible only to staff..."
                                rows={3}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsCreateOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleCreate}
                            disabled={createMutation.isPending || !formData.full_name || !formData.email}
                        >
                            {createMutation.isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                            Create
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
