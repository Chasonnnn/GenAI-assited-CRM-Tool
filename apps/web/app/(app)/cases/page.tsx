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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { PlusIcon, MoreVerticalIcon, SearchIcon, XIcon, LoaderIcon, CheckIcon, XCircleIcon } from "lucide-react"
import { useCases, useArchiveCase, useRestoreCase, useHandoffQueue, useAcceptHandoff, useDenyHandoff } from "@/lib/hooks/use-cases"
import { STATUS_CONFIG, type CaseStatus, type CaseSource } from "@/lib/types/case"
import { useAuth } from "@/lib/auth-context"

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
    const { user } = useAuth()
    const [activeTab, setActiveTab] = useState<"all" | "handoff">("all")
    const [statusFilter, setStatusFilter] = useState<CaseStatus | "all">("all")
    const [sourceFilter, setSourceFilter] = useState<CaseSource | "all">("all")
    const [searchQuery, setSearchQuery] = useState("")
    const [debouncedSearch, setDebouncedSearch] = useState("")
    const [page, setPage] = useState(1)
    const [handoffPage, setHandoffPage] = useState(1)
    const perPage = 20

    // Deny dialog state
    const [denyDialog, setDenyDialog] = useState<{ open: boolean; caseId: string | null }>({ open: false, caseId: null })
    const [denyReason, setDenyReason] = useState("")

    // Check if user can see handoff queue (case_manager+ only)
    const canSeeHandoffQueue = user?.role && ['case_manager', 'manager', 'developer'].includes(user.role)

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
    const { data, isLoading, error } = useCases({
        page,
        per_page: perPage,
        status: statusFilter === "all" ? undefined : statusFilter,
        source: sourceFilter === "all" ? undefined : sourceFilter,
        q: debouncedSearch || undefined,
    })

    // Fetch handoff queue (case_manager+ only) - skip query for other roles
    const handoffQuery = useHandoffQueue(
        canSeeHandoffQueue ? { page: handoffPage, per_page: perPage } : {},
        { enabled: Boolean(canSeeHandoffQueue) }
    )

    const archiveMutation = useArchiveCase()
    const restoreMutation = useRestoreCase()
    const acceptMutation = useAcceptHandoff()
    const denyMutation = useDenyHandoff()

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

    const handleAccept = async (caseId: string) => {
        await acceptMutation.mutateAsync(caseId)
    }

    const handleDenyClick = (caseId: string) => {
        setDenyDialog({ open: true, caseId })
        setDenyReason("")
    }

    const handleDenyConfirm = async () => {
        if (denyDialog.caseId) {
            await denyMutation.mutateAsync({ caseId: denyDialog.caseId, reason: denyReason || undefined })
            setDenyDialog({ open: false, caseId: null })
        }
    }

    // Handoff queue count for badge
    const handoffCount = handoffQuery.data?.total || 0

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <h1 className="text-2xl font-semibold">Cases</h1>
                    <Button>
                        <PlusIcon className="mr-2 size-4" />
                        New Case
                    </Button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 space-y-4 p-6">
                {/* Tab Navigation (visible to case_manager+ only) */}
                {canSeeHandoffQueue ? (
                    <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as "all" | "handoff")} className="w-full">
                        <TabsList className="mb-4">
                            <TabsTrigger value="all">All Cases</TabsTrigger>
                            <TabsTrigger value="handoff" className="relative">
                                Pending Handoff
                                {handoffCount > 0 && (
                                    <Badge variant="secondary" className="ml-2 bg-orange-500 text-white text-xs px-1.5 py-0.5 min-w-[20px]">
                                        {handoffCount}
                                    </Badge>
                                )}
                            </TabsTrigger>
                        </TabsList>

                        {/* All Cases Tab */}
                        <TabsContent value="all" className="space-y-4">
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
                                <Card className="flex items-center justify-center p-12">
                                    <LoaderIcon className="size-6 animate-spin text-muted-foreground" />
                                    <span className="ml-2 text-muted-foreground">Loading cases...</span>
                                </Card>
                            )}

                            {/* Table Card */}
                            {!isLoading && !error && data && (
                                <Card className="overflow-hidden">
                                    <div className="overflow-x-auto">
                                        <Table className="min-w-[700px]">
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Case #</TableHead>
                                                    <TableHead>Name</TableHead>
                                                    <TableHead>Status</TableHead>
                                                    <TableHead>Source</TableHead>
                                                    <TableHead>Assignee</TableHead>
                                                    <TableHead>Created</TableHead>
                                                    <TableHead className="w-[50px]">Actions</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {data.items.length === 0 ? (
                                                    <TableRow>
                                                        <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                                                            No cases found
                                                        </TableCell>
                                                    </TableRow>
                                                ) : (
                                                    data.items.map((caseItem) => {
                                                        const statusConfig = STATUS_CONFIG[caseItem.status] || { label: caseItem.status, color: 'bg-gray-500' }
                                                        return (
                                                            <TableRow key={caseItem.id}>
                                                                <TableCell>
                                                                    <Link href={`/cases/${caseItem.id}`} className="font-medium text-primary hover:underline">
                                                                        #{caseItem.case_number}
                                                                    </Link>
                                                                </TableCell>
                                                                <TableCell className="font-medium">{caseItem.full_name}</TableCell>
                                                                <TableCell>
                                                                    <Badge variant="secondary" className={`${statusConfig.color} text-white`}>
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
                                                                                    <Avatar className="size-8">
                                                                                        <AvatarFallback>{getInitials(caseItem.assigned_to_name)}</AvatarFallback>
                                                                                    </Avatar>
                                                                                </TooltipTrigger>
                                                                                <TooltipContent>
                                                                                    <p>{caseItem.assigned_to_name}</p>
                                                                                </TooltipContent>
                                                                            </Tooltip>
                                                                        </TooltipProvider>
                                                                    ) : (
                                                                        <span className="text-muted-foreground text-sm">Unassigned</span>
                                                                    )}
                                                                </TableCell>
                                                                <TableCell className="text-muted-foreground">{formatDate(caseItem.created_at)}</TableCell>
                                                                <TableCell>
                                                                    <DropdownMenu>
                                                                        <DropdownMenuTrigger
                                                                            render={
                                                                                <Button variant="ghost" size="sm" className="size-8 p-0">
                                                                                    <MoreVerticalIcon className="size-4" />
                                                                                    <span className="sr-only">Open menu</span>
                                                                                </Button>
                                                                            }
                                                                        />
                                                                        <DropdownMenuContent align="end">
                                                                            <DropdownMenuItem>
                                                                                <Link href={`/cases/${caseItem.id}`} className="w-full">View</Link>
                                                                            </DropdownMenuItem>
                                                                            <DropdownMenuItem>Edit</DropdownMenuItem>
                                                                            {caseItem.is_archived ? (
                                                                                <DropdownMenuItem onClick={() => handleRestore(caseItem.id)}>
                                                                                    Restore
                                                                                </DropdownMenuItem>
                                                                            ) : (
                                                                                <DropdownMenuItem onClick={() => handleArchive(caseItem.id)}>
                                                                                    Archive
                                                                                </DropdownMenuItem>
                                                                            )}
                                                                        </DropdownMenuContent>
                                                                    </DropdownMenu>
                                                                </TableCell>
                                                            </TableRow>
                                                        )
                                                    })
                                                )}
                                            </TableBody>
                                        </Table>
                                    </div>

                                    {/* Pagination */}
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
                                            {Array.from({ length: Math.min(5, data.pages) }, (_, i) => {
                                                const pageNum = i + 1
                                                return (
                                                    <Button
                                                        key={pageNum}
                                                        variant="outline"
                                                        size="sm"
                                                        className={page === pageNum ? "bg-primary/10 text-primary" : ""}
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
                                </Card>
                            )}
                        </TabsContent>

                        {/* Pending Handoff Tab */}
                        <TabsContent value="handoff" className="space-y-4">
                            {handoffQuery.isLoading && (
                                <Card className="flex items-center justify-center p-12">
                                    <LoaderIcon className="size-6 animate-spin text-muted-foreground" />
                                    <span className="ml-2 text-muted-foreground">Loading handoff queue...</span>
                                </Card>
                            )}

                            {handoffQuery.error && (
                                <Card className="p-6 text-center text-destructive">
                                    Error loading handoff queue: {handoffQuery.error.message}
                                </Card>
                            )}

                            {!handoffQuery.isLoading && !handoffQuery.error && handoffQuery.data && (
                                <Card className="overflow-hidden">
                                    <div className="overflow-x-auto">
                                        <Table className="min-w-[700px]">
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Case #</TableHead>
                                                    <TableHead>Name</TableHead>
                                                    <TableHead>Email</TableHead>
                                                    <TableHead>Source</TableHead>
                                                    <TableHead>Created</TableHead>
                                                    <TableHead className="w-[150px]">Actions</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {handoffQuery.data.items.length === 0 ? (
                                                    <TableRow>
                                                        <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                                                            No cases pending handoff
                                                        </TableCell>
                                                    </TableRow>
                                                ) : (
                                                    handoffQuery.data.items.map((caseItem) => (
                                                        <TableRow key={caseItem.id}>
                                                            <TableCell>
                                                                <Link href={`/cases/${caseItem.id}`} className="font-medium text-primary hover:underline">
                                                                    #{caseItem.case_number}
                                                                </Link>
                                                            </TableCell>
                                                            <TableCell className="font-medium">{caseItem.full_name}</TableCell>
                                                            <TableCell className="text-muted-foreground">{caseItem.email}</TableCell>
                                                            <TableCell>
                                                                <Badge variant="secondary" className="capitalize">{caseItem.source}</Badge>
                                                            </TableCell>
                                                            <TableCell className="text-muted-foreground">{formatDate(caseItem.created_at)}</TableCell>
                                                            <TableCell>
                                                                <div className="flex items-center gap-2">
                                                                    <Button
                                                                        size="sm"
                                                                        onClick={() => handleAccept(caseItem.id)}
                                                                        disabled={acceptMutation.isPending}
                                                                    >
                                                                        <CheckIcon className="mr-1 size-4" />
                                                                        Accept
                                                                    </Button>
                                                                    <Button
                                                                        size="sm"
                                                                        variant="outline"
                                                                        onClick={() => handleDenyClick(caseItem.id)}
                                                                        disabled={denyMutation.isPending}
                                                                    >
                                                                        <XCircleIcon className="mr-1 size-4" />
                                                                        Deny
                                                                    </Button>
                                                                </div>
                                                            </TableCell>
                                                        </TableRow>
                                                    ))
                                                )}
                                            </TableBody>
                                        </Table>
                                    </div>

                                    {/* Pagination for Handoff Queue */}
                                    {handoffQuery.data.total > perPage && (
                                        <div className="flex items-center justify-between border-t border-border px-6 py-4">
                                            <div className="text-sm text-muted-foreground">
                                                Showing {((handoffPage - 1) * perPage) + 1}-{Math.min(handoffPage * perPage, handoffQuery.data.total)} of {handoffQuery.data.total} cases
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    disabled={handoffPage === 1}
                                                    onClick={() => setHandoffPage(p => Math.max(1, p - 1))}
                                                >
                                                    Previous
                                                </Button>
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    disabled={handoffPage >= handoffQuery.data.pages}
                                                    onClick={() => setHandoffPage(p => Math.min(handoffQuery.data.pages, p + 1))}
                                                >
                                                    Next
                                                </Button>
                                            </div>
                                        </div>
                                    )}
                                </Card>
                            )}
                        </TabsContent>
                    </Tabs>
                ) : (
                    /* Non-case-manager view: show original filters and table without tabs */
                    <div className="space-y-4">
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

                        {error && (
                            <Card className="p-6 text-center text-destructive">
                                Error loading cases: {error.message}
                            </Card>
                        )}

                        {isLoading && (
                            <Card className="flex items-center justify-center p-12">
                                <LoaderIcon className="size-6 animate-spin text-muted-foreground" />
                                <span className="ml-2 text-muted-foreground">Loading cases...</span>
                            </Card>
                        )}

                        {!isLoading && !error && data && (
                            <Card className="overflow-hidden">
                                <div className="overflow-x-auto">
                                    <Table className="min-w-[700px]">
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead>Case #</TableHead>
                                                <TableHead>Name</TableHead>
                                                <TableHead>Status</TableHead>
                                                <TableHead>Source</TableHead>
                                                <TableHead>Assignee</TableHead>
                                                <TableHead>Created</TableHead>
                                                <TableHead className="w-[50px]">Actions</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {data.items.length === 0 ? (
                                                <TableRow>
                                                    <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                                                        No cases found
                                                    </TableCell>
                                                </TableRow>
                                            ) : (
                                                data.items.map((caseItem) => {
                                                    const statusConfig = STATUS_CONFIG[caseItem.status] || { label: caseItem.status, color: 'bg-gray-500' }
                                                    return (
                                                        <TableRow key={caseItem.id}>
                                                            <TableCell>
                                                                <Link href={`/cases/${caseItem.id}`} className="font-medium text-primary hover:underline">
                                                                    #{caseItem.case_number}
                                                                </Link>
                                                            </TableCell>
                                                            <TableCell className="font-medium">{caseItem.full_name}</TableCell>
                                                            <TableCell>
                                                                <Badge variant="secondary" className={`${statusConfig.color} text-white`}>
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
                                                                                <Avatar className="size-8">
                                                                                    <AvatarFallback>{getInitials(caseItem.assigned_to_name)}</AvatarFallback>
                                                                                </Avatar>
                                                                            </TooltipTrigger>
                                                                            <TooltipContent>
                                                                                <p>{caseItem.assigned_to_name}</p>
                                                                            </TooltipContent>
                                                                        </Tooltip>
                                                                    </TooltipProvider>
                                                                ) : (
                                                                    <span className="text-muted-foreground text-sm">Unassigned</span>
                                                                )}
                                                            </TableCell>
                                                            <TableCell className="text-muted-foreground">{formatDate(caseItem.created_at)}</TableCell>
                                                            <TableCell>
                                                                <DropdownMenu>
                                                                    <DropdownMenuTrigger
                                                                        render={
                                                                            <Button variant="ghost" size="sm" className="size-8 p-0">
                                                                                <MoreVerticalIcon className="size-4" />
                                                                                <span className="sr-only">Open menu</span>
                                                                            </Button>
                                                                        }
                                                                    />
                                                                    <DropdownMenuContent align="end">
                                                                        <DropdownMenuItem>
                                                                            <Link href={`/cases/${caseItem.id}`} className="w-full">View</Link>
                                                                        </DropdownMenuItem>
                                                                        <DropdownMenuItem>Edit</DropdownMenuItem>
                                                                        {caseItem.is_archived ? (
                                                                            <DropdownMenuItem onClick={() => handleRestore(caseItem.id)}>
                                                                                Restore
                                                                            </DropdownMenuItem>
                                                                        ) : (
                                                                            <DropdownMenuItem onClick={() => handleArchive(caseItem.id)}>
                                                                                Archive
                                                                            </DropdownMenuItem>
                                                                        )}
                                                                    </DropdownMenuContent>
                                                                </DropdownMenu>
                                                            </TableCell>
                                                        </TableRow>
                                                    )
                                                })
                                            )}
                                        </TableBody>
                                    </Table>
                                </div>

                                {/* Pagination */}
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
                                        {Array.from({ length: Math.min(5, data.pages) }, (_, i) => {
                                            const pageNum = i + 1
                                            return (
                                                <Button
                                                    key={pageNum}
                                                    variant="outline"
                                                    size="sm"
                                                    className={page === pageNum ? "bg-primary/10 text-primary" : ""}
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
                            </Card>
                        )}
                    </div>
                )}
            </div>

            {/* Deny Dialog */}
            <Dialog open={denyDialog.open} onOpenChange={(open) => setDenyDialog({ ...denyDialog, open })}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Deny Case Handoff</DialogTitle>
                        <DialogDescription>
                            This will return the case to &quot;Under Review&quot; status and notify the intake specialist.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="py-4">
                        <Textarea
                            placeholder="Optional: Provide a reason for denial..."
                            value={denyReason}
                            onChange={(e) => setDenyReason(e.target.value)}
                            rows={3}
                        />
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setDenyDialog({ open: false, caseId: null })}>
                            Cancel
                        </Button>
                        <Button variant="destructive" onClick={handleDenyConfirm} disabled={denyMutation.isPending}>
                            {denyMutation.isPending ? "Denying..." : "Deny Handoff"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
