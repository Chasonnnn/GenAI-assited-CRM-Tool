"use client"

import { useState, useEffect, useCallback } from "react"
import Link from "next/link"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { PlusIcon, MoreVerticalIcon, SearchIcon, XIcon, LoaderIcon } from "lucide-react"
import { useCases, useArchiveCase, useRestoreCase } from "@/lib/hooks/use-cases"
import { STATUS_CONFIG, type CaseStatus, type CaseSource } from "@/lib/types/case"

// Format date for display
function formatDate(dateString: string): string {
    const date = new Date(dateString)
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

export default function CasesPage() {
    const [statusFilter, setStatusFilter] = useState<CaseStatus | "all">("all")
    const [sourceFilter, setSourceFilter] = useState<CaseSource | "all">("all")
    const [searchQuery, setSearchQuery] = useState("")
    const [debouncedSearch, setDebouncedSearch] = useState("")
    const [page, setPage] = useState(1)
    const perPage = 20

    // Debounce search input
    useEffect(() => {
        const timer = setTimeout(() => setDebouncedSearch(searchQuery), 300)
        return () => clearTimeout(timer)
    }, [searchQuery])

    // Reset page when filters change
    useEffect(() => {
        setPage(1)
    }, [statusFilter, sourceFilter, debouncedSearch])

    // Fetch cases with filters
    // Note: Role-based visibility is handled by the backend
    // - Intake specialists only see pre-handoff statuses  
    // - Case managers see all cases including pending_handoff
    const { data, isLoading, error } = useCases({
        page,
        per_page: perPage,
        status: statusFilter === "all" ? undefined : statusFilter,
        source: sourceFilter === "all" ? undefined : sourceFilter,
        q: debouncedSearch || undefined,
    })

    const archiveMutation = useArchiveCase()
    const restoreMutation = useRestoreCase()

    const hasActiveFilters = statusFilter !== "all" || sourceFilter !== "all" || searchQuery !== ""

    const resetFilters = useCallback(() => {
        setStatusFilter("all")
        setSourceFilter("all")
        setSearchQuery("")
    }, [])

    const handleArchive = async (caseId: string) => {
        await archiveMutation.mutateAsync(caseId)
    }

    const handleRestore = async (caseId: string) => {
        await restoreMutation.mutateAsync(caseId)
    }

    return (
        <div className="flex flex-col gap-6 p-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold">Cases</h1>
                    <p className="text-muted-foreground">
                        {data?.total ?? 0} total cases
                    </p>
                </div>
                <Button asChild>
                    <Link href="/cases/new">
                        <PlusIcon className="mr-2 size-4" />
                        New Case
                    </Link>
                </Button>
            </div>

            {/* Filters Row */}
            <div className="flex flex-wrap items-center gap-3">
                <Select value={statusFilter} onValueChange={(value) => setStatusFilter((value || "all") as CaseStatus | "all")}>
                    <SelectTrigger className="w-[180px]">
                        <SelectValue placeholder="All Statuses" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Statuses</SelectItem>
                        <SelectItem value="new_unread">New</SelectItem>
                        <SelectItem value="contacted">Contacted</SelectItem>
                        <SelectItem value="followup_scheduled">Follow-up Scheduled</SelectItem>
                        <SelectItem value="application_submitted">Application Submitted</SelectItem>
                        <SelectItem value="under_review">Under Review</SelectItem>
                        <SelectItem value="approved">Approved</SelectItem>
                        <SelectItem value="pending_handoff">Pending Handoff</SelectItem>
                        <SelectItem value="disqualified">Disqualified</SelectItem>
                        <SelectItem value="pending_match">Pending Match</SelectItem>
                        <SelectItem value="meds_started">Meds Started</SelectItem>
                        <SelectItem value="exam_passed">Exam Passed</SelectItem>
                        <SelectItem value="embryo_transferred">Embryo Transferred</SelectItem>
                        <SelectItem value="delivered">Delivered</SelectItem>
                    </SelectContent>
                </Select>

                <Select value={sourceFilter} onValueChange={(value) => setSourceFilter((value || "all") as CaseSource | "all")}>
                    <SelectTrigger className="w-[180px]">
                        <SelectValue placeholder="All Sources" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Sources</SelectItem>
                        <SelectItem value="manual">Manual</SelectItem>
                        <SelectItem value="meta">Meta</SelectItem>
                        <SelectItem value="website">Website</SelectItem>
                        <SelectItem value="referral">Referral</SelectItem>
                    </SelectContent>
                </Select>

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

            {/* Error State */}
            {error && (
                <Card className="p-6 text-center text-destructive">
                    Error loading cases: {error.message}
                </Card>
            )}

            {/* Loading State */}
            {isLoading && (
                <Card className="p-12 flex items-center justify-center">
                    <LoaderIcon className="size-8 animate-spin text-muted-foreground" />
                </Card>
            )}

            {/* Empty State */}
            {!isLoading && !error && data?.items.length === 0 && (
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
            {!isLoading && !error && data && data.items.length > 0 && (
                <Card className="overflow-hidden">
                    <div className="overflow-x-auto">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead className="w-[100px]">Case #</TableHead>
                                    <TableHead>Name</TableHead>
                                    <TableHead>Phone</TableHead>
                                    <TableHead>Email</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead>Source</TableHead>
                                    <TableHead>Assigned To</TableHead>
                                    <TableHead>Created</TableHead>
                                    <TableHead className="w-[50px]"></TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {data.items.map((caseItem) => {
                                    const statusConfig = STATUS_CONFIG[caseItem.status as CaseStatus] || {
                                        label: caseItem.status,
                                        color: "bg-gray-100 text-gray-700"
                                    }
                                    // Apply gold styling for priority cases
                                    const priorityClass = caseItem.is_priority ? "text-amber-600 font-semibold" : ""

                                    return (
                                        <TableRow key={caseItem.id}>
                                            <TableCell>
                                                <Link href={`/cases/${caseItem.id}`} className={`font-medium hover:underline ${caseItem.is_priority ? "text-amber-600" : "text-primary"}`}>
                                                    {caseItem.is_priority && <span className="mr-1">★</span>}
                                                    #{caseItem.case_number}
                                                </Link>
                                            </TableCell>
                                            <TableCell className={`font-medium ${priorityClass}`}>{caseItem.full_name}</TableCell>
                                            <TableCell className="text-muted-foreground">
                                                {caseItem.phone || "—"}
                                            </TableCell>
                                            <TableCell className="text-muted-foreground max-w-[200px] truncate" title={caseItem.email}>
                                                {caseItem.email}
                                            </TableCell>
                                            <TableCell>
                                                <Badge className={statusConfig.color}>
                                                    {statusConfig.label}
                                                </Badge>
                                            </TableCell>
                                            <TableCell>
                                                <Badge variant="secondary" className="capitalize">{caseItem.source}</Badge>
                                            </TableCell>
                                            <TableCell>
                                                {caseItem.assigned_to_name ? (
                                                    <TooltipProvider>
                                                        <Tooltip>
                                                            <TooltipTrigger>
                                                                <Avatar className="h-7 w-7">
                                                                    <AvatarFallback className="text-xs">
                                                                        {getInitials(caseItem.assigned_to_name)}
                                                                    </AvatarFallback>
                                                                </Avatar>
                                                            </TooltipTrigger>
                                                            <TooltipContent>
                                                                {caseItem.assigned_to_name}
                                                            </TooltipContent>
                                                        </Tooltip>
                                                    </TooltipProvider>
                                                ) : (
                                                    <span className="text-muted-foreground">—</span>
                                                )}
                                            </TableCell>
                                            <TableCell className="text-muted-foreground">
                                                {formatDate(caseItem.created_at)}
                                            </TableCell>
                                            <TableCell>
                                                <DropdownMenu>
                                                    <DropdownMenuTrigger asChild>
                                                        <Button variant="ghost" size="sm" className="size-8 p-0">
                                                            <MoreVerticalIcon className="size-4" />
                                                        </Button>
                                                    </DropdownMenuTrigger>
                                                    <DropdownMenuContent align="end">
                                                        <DropdownMenuItem asChild>
                                                            <Link href={`/cases/${caseItem.id}`}>View Details</Link>
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
        </div>
    )
}
