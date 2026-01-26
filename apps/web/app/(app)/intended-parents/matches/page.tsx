"use client"

import { useState, useEffect, useCallback } from "react"
import Link from "@/components/app-link"
import { useSearchParams, useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { PaginationJump } from "@/components/ui/pagination-jump"
import {
    HeartHandshakeIcon,
    Loader2Icon,
    ChevronLeftIcon,
    ChevronRightIcon,
    SearchIcon,
} from "lucide-react"
import { useMatches, useMatchStats, type MatchStatus, type ListMatchesParams } from "@/lib/hooks/use-matches"
import { parseDateInput } from "@/lib/utils/date"

const STATUS_LABELS: Record<MatchStatus, string> = {
    proposed: "Proposed",
    reviewing: "Reviewing",
    accepted: "Accepted",
    cancel_pending: "Cancellation Pending",
    rejected: "Rejected",
    cancelled: "Cancelled",
}

const STATUS_COLORS: Record<MatchStatus, string> = {
    proposed: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
    reviewing: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    accepted: "bg-green-500/10 text-green-500 border-green-500/20",
    cancel_pending: "bg-amber-500/10 text-amber-600 border-amber-500/20",
    rejected: "bg-red-500/10 text-red-500 border-red-500/20",
    cancelled: "bg-gray-500/10 text-gray-500 border-gray-500/20",
}

const MATCH_STATUSES = ["proposed", "reviewing", "accepted", "cancel_pending", "rejected", "cancelled"] as const
type MatchStatusFilter = (typeof MATCH_STATUSES)[number] | "all"
const isMatchStatus = (value: string): value is MatchStatus =>
    MATCH_STATUSES.includes(value as MatchStatus)

const parsePageParam = (value: string | null): number => {
    const parsed = Number(value)
    return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : 1
}

export default function MatchesPage() {
    const searchParams = useSearchParams()
    const router = useRouter()
    const currentQuery = searchParams.toString()

    const urlStatus = searchParams.get("status")
    const urlSearch = searchParams.get("q")
    const urlPage = searchParams.get("page")

    const [statusFilter, setStatusFilter] = useState<MatchStatusFilter>(
        urlStatus && (urlStatus === "all" || isMatchStatus(urlStatus)) ? urlStatus : "all"
    )
    const [page, setPage] = useState(parsePageParam(urlPage))
    const [search, setSearch] = useState(urlSearch || "")
    const [debouncedSearch, setDebouncedSearch] = useState(urlSearch || "")

    const updateUrlParams = useCallback((status: MatchStatusFilter, searchValue: string, currentPage: number) => {
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
        const nextQuery = newParams.toString()
        if (nextQuery === currentQuery) return
        const newUrl = nextQuery ? `?${nextQuery}` : ""
        router.replace(`/intended-parents/matches${newUrl}`, { scroll: false })
    }, [router, currentQuery])

    const handleStatusChange = useCallback((value: string) => {
        const nextStatus = value === "all" || isMatchStatus(value) ? value : "all"
        setStatusFilter(nextStatus)
        setPage(1)
        updateUrlParams(nextStatus, debouncedSearch, 1)
    }, [debouncedSearch, updateUrlParams])

    const handlePageChange = useCallback((nextPage: number) => {
        setPage(nextPage)
        updateUrlParams(statusFilter, debouncedSearch, nextPage)
    }, [statusFilter, debouncedSearch, updateUrlParams])

    // Debounce search input
    useEffect(() => {
        const timer = setTimeout(() => setDebouncedSearch(search), 300)
        return () => clearTimeout(timer)
    }, [search])

    useEffect(() => {
        const urlSearchValue = searchParams.get("q") || ""
        if (debouncedSearch !== urlSearchValue) {
            setPage(1)
            updateUrlParams(statusFilter, debouncedSearch, 1)
        }
    }, [debouncedSearch, searchParams, statusFilter, updateUrlParams])

    useEffect(() => {
        const nextStatus = searchParams.get("status") && (searchParams.get("status") === "all" || isMatchStatus(searchParams.get("status") as string))
            ? (searchParams.get("status") as MatchStatusFilter)
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
    }, [currentQuery]) // eslint-disable-line react-hooks/exhaustive-deps

    const filters = {
        page,
        per_page: 20,
        sort_by: "match_number",
        sort_order: "desc",
        ...(statusFilter !== "all" && isMatchStatus(statusFilter)
            ? { status: statusFilter }
            : {}),
        ...(debouncedSearch ? { q: debouncedSearch } : {}),
    } satisfies ListMatchesParams
    const { data, isLoading, isError } = useMatches(filters)
    const { data: stats } = useMatchStats()

    const formatDate = (dateStr: string) => {
        const parsed = parseDateInput(dateStr)
        if (Number.isNaN(parsed.getTime())) return "—"
        return parsed.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
        })
    }

    const totalPages = data ? Math.ceil(data.total / data.per_page) : 1

    return (
        <div className="flex flex-col h-full overflow-hidden">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <h1 className="text-2xl font-semibold">Matches</h1>
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
                    {(["proposed", "reviewing", "accepted", "rejected"] as const).map((status) => (
                        <Card key={status}>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-muted-foreground">
                                    {STATUS_LABELS[status]}
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold">
                                    {stats?.by_status?.[status] ?? 0}
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>

                {/* Filters */}
                <div className="flex flex-col gap-4 md:flex-row md:items-center">
                    <Select value={statusFilter} onValueChange={(v) => { if (v) { handleStatusChange(v) } }}>
                        <SelectTrigger className="w-[180px]">
                            <SelectValue placeholder="All Stages">
                                {(value: string | null) => {
                                    if (!value || value === "all") return "All Stages"
                                    if (isMatchStatus(value)) return STATUS_LABELS[value]
                                    return value
                                }}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Stages</SelectItem>
                            <SelectItem value="proposed">Proposed</SelectItem>
                            <SelectItem value="reviewing">Reviewing</SelectItem>
                            <SelectItem value="accepted">Accepted</SelectItem>
                            <SelectItem value="rejected">Rejected</SelectItem>
                            <SelectItem value="cancelled">Cancelled</SelectItem>
                        </SelectContent>
                    </Select>
                    <div className="flex-1" />
                    <div className="relative w-full max-w-sm">
                        <SearchIcon className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            placeholder="Search case or IP name..."
                            value={search}
                            onChange={(e) => {
                                setSearch(e.target.value)
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
                                <HeartHandshakeIcon className="size-12 text-muted-foreground mb-4" />
                                <h3 className="text-lg font-medium">Unable to load matches</h3>
                                <p className="text-muted-foreground">
                                    Please try again in a moment.
                                </p>
                            </div>
                        ) : !data?.items.length ? (
                            <div className="flex flex-col items-center justify-center py-12 text-center">
                                <HeartHandshakeIcon className="size-12 text-muted-foreground mb-4" />
                                <h3 className="text-lg font-medium">No matches found</h3>
                                <p className="text-muted-foreground">
                                    {statusFilter !== "all"
                                        ? "Try adjusting your filter"
                                        : "Matches will appear here when surrogates are paired with intended parents"}
                                </p>
                            </div>
                        ) : (
                            <Table className="[&_th]:!text-center [&_td]:!text-center [&_th>div]:justify-center">
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Match #</TableHead>
                                        <TableHead>Surrogate</TableHead>
                                        <TableHead>Surrogate #</TableHead>
                                        <TableHead>Intended Parents</TableHead>
                                        <TableHead>Compatibility</TableHead>
                                        <TableHead>Match Stage</TableHead>
                                        <TableHead>Surrogate Stage</TableHead>
                                        <TableHead>Proposed</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {data.items.map((match) => (
                                        <TableRow key={match.id} className="cursor-pointer hover:bg-muted/50">
                                            <TableCell>
                                                <Link
                                                    href={`/intended-parents/matches/${match.id}`}
                                                    className="font-medium text-primary hover:underline"
                                                >
                                                    {match.match_number || "—"}
                                                </Link>
                                            </TableCell>
                                            <TableCell className="font-medium">
                                                <Link
                                                    href={`/intended-parents/matches/${match.id}`}
                                                    className="text-primary hover:underline underline-offset-4"
                                                >
                                                    {match.surrogate_name || "—"}
                                                </Link>
                                            </TableCell>
                                            <TableCell className="text-muted-foreground">
                                                {match.surrogate_number || "—"}
                                            </TableCell>
                                            <TableCell className="text-muted-foreground">
                                                <Link
                                                    href={`/intended-parents/matches/${match.id}`}
                                                    className="text-primary hover:underline underline-offset-4"
                                                >
                                                    {match.ip_name || "—"}
                                                </Link>
                                            </TableCell>
                                            <TableCell>
                                                {match.compatibility_score !== null
                                                    ? `${match.compatibility_score}%`
                                                    : "—"}
                                            </TableCell>
                                            <TableCell>
                                                {(() => {
                                                    const status = isMatchStatus(match.status)
                                                        ? match.status
                                                        : "proposed"
                                                    return (
                                                        <Badge className={STATUS_COLORS[status]}>
                                                            {STATUS_LABELS[status]}
                                                        </Badge>
                                                    )
                                                })()}
                                            </TableCell>
                                            <TableCell>
                                                {match.surrogate_stage_label ? (
                                                    <Badge variant="outline" className="text-xs">
                                                        {match.surrogate_stage_label}
                                                    </Badge>
                                                ) : (
                                                    <span className="text-muted-foreground">—</span>
                                                )}
                                            </TableCell>
                                            <TableCell className="text-muted-foreground">
                                                {formatDate(match.proposed_at)}
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
        </div>
    )
}
