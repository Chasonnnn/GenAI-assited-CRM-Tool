"use client"

import { useState, useCallback, useEffect } from "react"
import Link from "next/link"
import { useSearchParams, useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
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
    LoaderIcon,
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
import { parseDateInput } from "@/lib/utils/date"

const STATUS_LABELS: Record<IntendedParentStatus, string> = {
    new: "New",
    in_review: "In Review",
    matched: "Matched",
    inactive: "Inactive",
}

const STATUS_COLORS: Record<IntendedParentStatus, string> = {
    new: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    in_review: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
    matched: "bg-green-500/10 text-green-500 border-green-500/20",
    inactive: "bg-gray-500/10 text-gray-500 border-gray-500/20",
}

const VALID_STATUSES = ["all", "new", "in_review", "matched", "inactive"]

export default function IntendedParentsPage() {
    const searchParams = useSearchParams()
    const router = useRouter()

    // Read initial values from URL params
    const urlStatus = searchParams.get("status")
    const urlSearch = searchParams.get("q")

    const [search, setSearch] = useState(urlSearch || "")
    const [debouncedSearch, setDebouncedSearch] = useState(urlSearch || "")
    const [statusFilter, setStatusFilter] = useState<string>(
        urlStatus && VALID_STATUSES.includes(urlStatus) ? urlStatus : "all"
    )
    const [dateRange, setDateRange] = useState<DateRangePreset>('all')
    const [customRange, setCustomRange] = useState<{ from: Date | undefined; to: Date | undefined }>({
        from: undefined,
        to: undefined,
    })
    const [page, setPage] = useState(1)
    const [isCreateOpen, setIsCreateOpen] = useState(false)
    const [sortBy, setSortBy] = useState<string | null>(null)
    const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc")

    // Sync state changes back to URL
    const updateUrlParams = useCallback((status: string, searchValue: string) => {
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
        const newUrl = newParams.toString() ? `?${newParams}` : ""
        router.replace(`/intended-parents${newUrl}`, { scroll: false })
    }, [searchParams, router])

    // Handle status filter change
    const handleStatusChange = useCallback((status: string) => {
        setStatusFilter(status)
        setPage(1)
        updateUrlParams(status, debouncedSearch)
    }, [debouncedSearch, updateUrlParams])

    // Debounce search input
    useEffect(() => {
        const timer = setTimeout(() => setDebouncedSearch(search), 300)
        return () => clearTimeout(timer)
    }, [search])

    // Sync debouncedSearch to URL
    useEffect(() => {
        const urlSearch = searchParams.get("q")
        if (debouncedSearch !== (urlSearch || "")) {
            updateUrlParams(statusFilter, debouncedSearch)
        }
    }, [debouncedSearch]) // eslint-disable-line react-hooks/exhaustive-deps

    useEffect(() => {
        setPage(1)
    }, [dateRange, customRange])

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
            return {
                created_after: customRange.from.toISOString(),
                created_before: customRange.to?.toISOString(),
            }
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
        return from ? { created_after: from.toISOString() } : {}
    }

    const filters = {
        q: debouncedSearch || undefined,
        status: statusFilter !== "all" ? [statusFilter] : undefined,
        page,
        per_page: 20,
        sort_by: sortBy || undefined,
        sort_order: sortOrder,
        ...getDateRangeParams(),
    }
    const { data, isLoading, isError } = useIntendedParents(filters)
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
        await createMutation.mutateAsync({
            full_name: formData.full_name,
            email: formData.email,
            phone: formData.phone || undefined,
            state: formData.state || undefined,
            budget: formData.budget ? parseFloat(formData.budget) : undefined,
            notes_internal: formData.notes_internal || undefined,
        })
        setIsCreateOpen(false)
        resetForm()
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
                    <Button className="bg-teal-600 hover:bg-teal-700" onClick={() => setIsCreateOpen(true)}>
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
                    {(["new", "in_review", "matched", "inactive"] as IntendedParentStatus[]).map((status) => (
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
                            <SelectValue placeholder="All Stages">
                                {(value: string | null) => {
                                    if (!value || value === "all") return "All Stages"
                                    return STATUS_LABELS[value as IntendedParentStatus] ?? value
                                }}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Stages</SelectItem>
                            <SelectItem value="new">New</SelectItem>
                            <SelectItem value="in_review">In Review</SelectItem>
                            <SelectItem value="matched">Matched</SelectItem>
                            <SelectItem value="inactive">Inactive</SelectItem>
                        </SelectContent>
                    </Select>
                    <DateRangePicker
                        preset={dateRange}
                        onPresetChange={setDateRange}
                        customRange={customRange}
                        onCustomRangeChange={setCustomRange}
                    />
                    <div className="flex-1" />
                    <div className="relative w-full max-w-sm">
                        <SearchIcon className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            placeholder="Search name, email, phone..."
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
                                <LoaderIcon className="size-6 animate-spin text-muted-foreground" />
                                <span className="ml-2 text-muted-foreground">Loading...</span>
                            </div>
                        ) : isError ? (
                            <div className="flex flex-col items-center justify-center py-12 text-center">
                                <AlertCircleIcon className="size-12 text-destructive mb-4" />
                                <h3 className="text-lg font-medium">Failed to load intended parents</h3>
                                <p className="text-muted-foreground">Please try again or contact support if the issue persists.</p>
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
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <SortableTableHead column="full_name" label="Name" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <SortableTableHead column="email" label="Email" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <SortableTableHead column="phone" label="Phone" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <SortableTableHead column="state" label="State" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <SortableTableHead column="budget" label="Budget" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <SortableTableHead column="status" label="Stage" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                        <SortableTableHead column="created_at" label="Created" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {data.items.map((ip: IntendedParentListItem) => (
                                        <TableRow key={ip.id} className="cursor-pointer hover:bg-muted/50">
                                            <TableCell>
                                                <Link
                                                    href={`/intended-parents/${ip.id}`}
                                                    className="font-medium hover:text-primary hover:underline"
                                                >
                                                    {ip.full_name}
                                                </Link>
                                            </TableCell>
                                            <TableCell className="text-muted-foreground">{ip.email}</TableCell>
                                            <TableCell className="text-muted-foreground">{ip.phone || "—"}</TableCell>
                                            <TableCell className="text-muted-foreground">{ip.state || "—"}</TableCell>
                                            <TableCell>{formatBudget(ip.budget)}</TableCell>
                                            <TableCell>
                                                <Badge className={STATUS_COLORS[ip.status as IntendedParentStatus]}>
                                                    {STATUS_LABELS[ip.status as IntendedParentStatus]}
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
                        <div className="flex gap-2">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setPage((p) => Math.max(1, p - 1))}
                                disabled={page === 1}
                            >
                                <ChevronLeftIcon className="size-4" />
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                                disabled={page === totalPages}
                            >
                                <ChevronRightIcon className="size-4" />
                            </Button>
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
                                <Input
                                    id="state"
                                    value={formData.state}
                                    onChange={(e) => setFormData({ ...formData, state: e.target.value })}
                                    placeholder="California"
                                />
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
                            className="bg-teal-600 hover:bg-teal-700"
                            onClick={handleCreate}
                            disabled={createMutation.isPending || !formData.full_name || !formData.email}
                        >
                            {createMutation.isPending && <LoaderIcon className="mr-2 size-4 animate-spin" />}
                            Create
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
