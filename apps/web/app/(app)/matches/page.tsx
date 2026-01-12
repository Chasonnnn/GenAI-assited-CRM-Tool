"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Loader2Icon, UsersIcon, CheckCircleIcon, XCircleIcon, ArrowRightIcon, PlusIcon, SearchIcon, AlertCircleIcon } from "lucide-react"
import { useMatches, useCreateMatch, type MatchStatus, type MatchListItem } from "@/lib/hooks/use-matches"
import { useCases } from "@/lib/hooks/use-cases"
import { useIntendedParents } from "@/lib/hooks/use-intended-parents"
import { formatDistanceToNow } from "date-fns"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { toast } from "sonner"
import { useQueryClient } from "@tanstack/react-query"

const STATUS_CONFIG: Record<MatchStatus, { label: string; color: string; icon?: React.ReactNode }> = {
    proposed: { label: "Proposed", color: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300" },
    reviewing: { label: "Reviewing", color: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300" },
    accepted: { label: "Accepted", color: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300", icon: <CheckCircleIcon className="size-3" /> },
    rejected: { label: "Rejected", color: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300", icon: <XCircleIcon className="size-3" /> },
    cancelled: { label: "Cancelled", color: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300" },
}

const isMatchStatus = (value: string): value is MatchStatus =>
    Object.prototype.hasOwnProperty.call(STATUS_CONFIG, value)

function StatusBadge({ status }: { status: MatchStatus }) {
    const config = STATUS_CONFIG[status] || STATUS_CONFIG.proposed
    return (
        <Badge variant="outline" className={`gap-1 ${config.color}`}>
            {config.icon}
            {config.label}
        </Badge>
    )
}

function MatchRow({ match }: { match: MatchListItem }) {
    const status = isMatchStatus(match.status) ? match.status : "proposed"

    return (
        <TableRow className="hover:bg-accent/50">
            <TableCell>
                <div className="space-y-1">
                    <Link href={`/cases/${match.case_id}`} className="font-medium text-teal-600 hover:underline">
                        {match.case_name || "Unknown Surrogate"}
                    </Link>
                    {match.case_number && (
                        <p className="text-xs text-muted-foreground">{match.case_number}</p>
                    )}
                </div>
            </TableCell>
            <TableCell>
                <Link href={`/intended-parents/${match.intended_parent_id}`} className="font-medium text-teal-600 hover:underline">
                    {match.ip_name || "Unknown IP"}
                </Link>
            </TableCell>
            <TableCell>
                <StatusBadge status={status} />
            </TableCell>
            <TableCell>
                {match.compatibility_score !== null ? (
                    <span className="font-medium">{match.compatibility_score.toFixed(0)}%</span>
                ) : (
                    <span className="text-muted-foreground">—</span>
                )}
            </TableCell>
            <TableCell className="text-muted-foreground text-sm">
                {formatDistanceToNow(new Date(match.proposed_at), { addSuffix: true })}
            </TableCell>
            <TableCell className="text-right">
                <Link
                    href={`/intended-parents/matches/${match.id}`}
                    className="inline-flex items-center justify-center h-8 w-8 rounded-md hover:bg-accent hover:text-accent-foreground"
                >
                    <ArrowRightIcon className="size-4" />
                </Link>
            </TableCell>
        </TableRow>
    )
}

// =============================================================================
// New Match Dialog
// =============================================================================

interface NewMatchDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    onSuccess?: () => void
}

function NewMatchDialog({ open, onOpenChange, onSuccess }: NewMatchDialogProps) {
    const [selectedCaseId, setSelectedCaseId] = useState("")
    const [selectedIpId, setSelectedIpId] = useState("")
    const [notes, setNotes] = useState("")
    const [error, setError] = useState<string | null>(null)

    const queryClient = useQueryClient()
    const { data: casesData, isLoading: casesLoading } = useCases({ per_page: 100 })
    const { data: ipsData, isLoading: ipsLoading } = useIntendedParents({ per_page: 100 })
    const createMatch = useCreateMatch()

    // Filter cases to pending_match status
    const eligibleCases = casesData?.items?.filter((c) => {
        if (c.stage_slug) {
            return c.stage_slug === "pending_match"
        }
        return c.status_label?.toLowerCase() === "pending match"
    }) || []

    const handleSubmit = async () => {
        if (!selectedCaseId || !selectedIpId) return
        setError(null)

        try {
            await createMatch.mutateAsync({
                case_id: selectedCaseId,
                intended_parent_id: selectedIpId,
                ...(notes.trim() ? { notes: notes.trim() } : {}),
            })
            toast.success("Match proposed successfully!")
            queryClient.invalidateQueries({ queryKey: ["matches"] })
            onOpenChange(false)
            resetForm()
            onSuccess?.()
        } catch (e: unknown) {
            console.error("Failed to propose match:", e instanceof Error ? e.message : e)
            setError(e instanceof Error ? e.message : "Failed to propose match. Please try again.")
        }
    }

    const resetForm = () => {
        setSelectedCaseId("")
        setSelectedIpId("")
        setNotes("")
        setError(null)
    }

    const handleClose = () => {
        onOpenChange(false)
        resetForm()
    }

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="max-w-md">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <UsersIcon className="size-5" />
                        New Match
                    </DialogTitle>
                    <DialogDescription>
                        Create a new match between a surrogate and intended parents
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {error && (
                        <Alert variant="destructive">
                            <AlertCircleIcon className="size-4" />
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    )}

                    {/* Case/Surrogate Selector */}
                    <div className="space-y-2">
                        <Label>Surrogate (Pending Match Only)</Label>
                        {casesLoading ? (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2Icon className="size-4 animate-spin" />
                                Loading surrogates...
                            </div>
                        ) : eligibleCases.length === 0 ? (
                            <div className="text-sm text-muted-foreground p-3 border rounded-md bg-muted/30">
                                No surrogates are currently in "Pending Match" status.
                            </div>
                        ) : (
                            <Select value={selectedCaseId} onValueChange={(v) => setSelectedCaseId(v || "")}>
                                <SelectTrigger>
                                    <SelectValue placeholder="Select a surrogate" />
                                </SelectTrigger>
                                <SelectContent className="max-h-[200px]">
                                    {eligibleCases.map((c) => (
                                        <SelectItem key={c.id} value={c.id}>
                                            <span className="font-medium">{c.full_name || "Unknown"}</span>
                                            <span className="text-muted-foreground ml-2">#{c.case_number}</span>
                                            {c.state && <span className="text-muted-foreground ml-2">• {c.state}</span>}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        )}
                    </div>

                    {/* IP Selector */}
                    <div className="space-y-2">
                        <Label>Intended Parents</Label>
                        {ipsLoading ? (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2Icon className="size-4 animate-spin" />
                                Loading intended parents...
                            </div>
                        ) : (
                            <Select value={selectedIpId} onValueChange={(v) => setSelectedIpId(v || "")}>
                                <SelectTrigger>
                                    <SelectValue placeholder="Select intended parents" />
                                </SelectTrigger>
                                <SelectContent className="max-h-[200px]">
                                    {ipsData?.items?.map((ip) => (
                                        <SelectItem key={ip.id} value={ip.id}>
                                            {ip.full_name || ip.email || "Unknown"}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        )}
                    </div>

                    {/* Notes */}
                    <div className="space-y-2">
                        <Label>Notes (optional)</Label>
                        <Textarea
                            placeholder="Add any notes about this match proposal..."
                            value={notes}
                            onChange={(e) => setNotes(e.target.value)}
                            className="min-h-20"
                        />
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={handleClose}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleSubmit}
                        disabled={!selectedCaseId || !selectedIpId || createMatch.isPending}
                    >
                        {createMatch.isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                        Create Match
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

// =============================================================================
// Match Table
// =============================================================================

function MatchTable({ status, search }: { status?: MatchStatus; search?: string }) {
    const { data, isLoading, isError } = useMatches({
        per_page: 50,
        ...(status ? { status } : {}),
        ...(search ? { q: search } : {}),
    })

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2Icon className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (isError) {
        return (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
                Error loading matches
            </div>
        )
    }

    if (!data?.items.length) {
        return (
            <div className="flex flex-col items-center justify-center py-12">
                <UsersIcon className="h-12 w-12 text-muted-foreground/40 mb-3" />
                <p className="text-muted-foreground">No matches found</p>
            </div>
        )
    }

    return (
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead>Surrogate</TableHead>
                    <TableHead>Intended Parent</TableHead>
                    <TableHead>Stage</TableHead>
                    <TableHead>Score</TableHead>
                    <TableHead>Proposed</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {data.items.map((match) => (
                    <MatchRow key={match.id} match={match} />
                ))}
            </TableBody>
        </Table>
    )
}

export default function MatchesPage() {
    const [activeTab, setActiveTab] = useState<string>("proposed")
    const [search, setSearch] = useState("")
    const [debouncedSearch, setDebouncedSearch] = useState("")
    const [newMatchOpen, setNewMatchOpen] = useState(false)

    // Debounce search input
    useEffect(() => {
        const timer = setTimeout(() => setDebouncedSearch(search), 300)
        return () => clearTimeout(timer)
    }, [search])

    const { data: proposedData } = useMatches({ status: 'proposed' })
    const { data: reviewingData } = useMatches({ status: 'reviewing' })
    const { data: acceptedData } = useMatches({ status: 'accepted' })
    const { data: rejectedData } = useMatches({ status: 'rejected' })

    return (
        <div className="flex flex-1 flex-col gap-6 p-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-semibold">Matches</h1>
                    <p className="text-sm text-muted-foreground">
                        Surrogate and intended parent matching
                    </p>
                </div>
                <Button onClick={() => setNewMatchOpen(true)}>
                    <PlusIcon className="size-4 mr-2" />
                    New Match
                </Button>
            </div>

            {/* Stats Cards */}
            <div className="grid gap-4 md:grid-cols-4">
                <Card>
                    <CardContent className="pt-6">
                        <div className="text-2xl font-bold">{proposedData?.total || 0}</div>
                        <p className="text-xs text-muted-foreground">Proposed</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-6">
                        <div className="text-2xl font-bold">{reviewingData?.total || 0}</div>
                        <p className="text-xs text-muted-foreground">Under Review</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-6">
                        <div className="text-2xl font-bold text-green-600">{acceptedData?.total || 0}</div>
                        <p className="text-xs text-muted-foreground">Accepted</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-6">
                        <div className="text-2xl font-bold text-red-600">{rejectedData?.total || 0}</div>
                        <p className="text-xs text-muted-foreground">Rejected</p>
                    </CardContent>
                </Card>
            </div>

            {/* Tabs */}
            <Card>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle>Match Pipeline</CardTitle>
                            <CardDescription>View and manage match proposals</CardDescription>
                        </div>
                        <div className="relative w-full max-w-sm">
                            <SearchIcon className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                            <Input
                                placeholder="Search case or IP name..."
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                className="pl-9"
                            />
                        </div>
                    </div>
                </CardHeader>
                <CardContent>
                    <Tabs value={activeTab} onValueChange={setActiveTab}>
                        <TabsList className="mb-4">
                            <TabsTrigger value="proposed">Proposed</TabsTrigger>
                            <TabsTrigger value="reviewing">Reviewing</TabsTrigger>
                            <TabsTrigger value="accepted">Accepted</TabsTrigger>
                            <TabsTrigger value="rejected">Rejected</TabsTrigger>
                            <TabsTrigger value="all">All</TabsTrigger>
                        </TabsList>

                        <TabsContent value="proposed">
                            <MatchTable status="proposed" search={debouncedSearch} />
                        </TabsContent>
                        <TabsContent value="reviewing">
                            <MatchTable status="reviewing" search={debouncedSearch} />
                        </TabsContent>
                        <TabsContent value="accepted">
                            <MatchTable status="accepted" search={debouncedSearch} />
                        </TabsContent>
                        <TabsContent value="rejected">
                            <MatchTable status="rejected" search={debouncedSearch} />
                        </TabsContent>
                        <TabsContent value="all">
                            <MatchTable search={debouncedSearch} />
                        </TabsContent>
                    </Tabs>
                </CardContent>
            </Card>

            <NewMatchDialog open={newMatchOpen} onOpenChange={setNewMatchOpen} />
        </div>
    )
}
