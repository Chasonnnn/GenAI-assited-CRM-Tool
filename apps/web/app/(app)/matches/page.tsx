"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Loader2Icon, UsersIcon, CheckCircleIcon, XCircleIcon, ArrowRightIcon, PlusIcon, SearchIcon } from "lucide-react"
import { useMatches, type MatchStatus, type MatchListItem } from "@/lib/hooks/use-matches"
import { formatDistanceToNow } from "date-fns"

const STATUS_CONFIG: Record<MatchStatus, { label: string; color: string; icon?: React.ReactNode }> = {
    proposed: { label: "Proposed", color: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300" },
    reviewing: { label: "Reviewing", color: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300" },
    accepted: { label: "Accepted", color: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300", icon: <CheckCircleIcon className="size-3" /> },
    rejected: { label: "Rejected", color: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300", icon: <XCircleIcon className="size-3" /> },
    cancelled: { label: "Cancelled", color: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300" },
}

function StatusBadge({ status }: { status: string }) {
    const config = STATUS_CONFIG[status as MatchStatus] || STATUS_CONFIG.proposed
    return (
        <Badge variant="outline" className={`gap-1 ${config.color}`}>
            {config.icon}
            {config.label}
        </Badge>
    )
}

function MatchRow({ match }: { match: MatchListItem }) {
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
                <StatusBadge status={match.status} />
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

function MatchTable({ status, search }: { status?: MatchStatus; search?: string }) {
    const { data, isLoading, isError } = useMatches({ status, q: search || undefined, per_page: 50 })

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
                    <h1 className="text-2xl font-bold">Matches</h1>
                    <p className="text-sm text-muted-foreground">
                        Surrogate and intended parent matching
                    </p>
                </div>
                <Button disabled>
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
        </div>
    )
}
