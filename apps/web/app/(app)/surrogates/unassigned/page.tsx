"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "@/components/app-link"
import { toast } from "sonner"
import { Loader2Icon, UserPlusIcon } from "lucide-react"

import { useAuth } from "@/lib/auth-context"
import { useUnassignedQueue } from "@/lib/hooks/use-surrogates"
import { useClaimSurrogate } from "@/lib/hooks/use-queues"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { PaginationJump } from "@/components/ui/pagination-jump"

const DEFAULT_PER_PAGE = 20

function parsePageParam(value: string | null): number {
    const parsed = Number(value)
    return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : 1
}

function formatDate(dateString: string | null | undefined): string {
    if (!dateString) return "—"
    const date = new Date(dateString)
    if (Number.isNaN(date.getTime())) return "—"
    return new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "2-digit",
        year: "numeric",
    }).format(date)
}

export default function UnassignedSurrogatesPage() {
    const { user } = useAuth()
    const router = useRouter()
    const searchParams = useSearchParams()

    const authLoaded = !!user?.role
    const canViewUnassignedQueue = user?.role === "intake_specialist" || user?.role === "developer"

    const urlPage = parsePageParam(searchParams.get("page"))
    const page = urlPage

    useEffect(() => {
        if (!authLoaded) return
        if (!canViewUnassignedQueue) {
            router.replace("/surrogates")
        }
    }, [authLoaded, canViewUnassignedQueue, router])

    const { data, isLoading, error, refetch } = useUnassignedQueue(
        {
            page,
            per_page: DEFAULT_PER_PAGE,
        },
        { enabled: canViewUnassignedQueue }
    )
    const claimMutation = useClaimSurrogate()
    const [claimingId, setClaimingId] = useState<string | null>(null)

    const items = data?.items ?? []
    const totalPages = data?.pages ?? 0
    const total = data?.total ?? null

    const pageStart = useMemo(() => (page - 1) * DEFAULT_PER_PAGE + (items.length > 0 ? 1 : 0), [page, items.length])
    const pageEnd = useMemo(() => (page - 1) * DEFAULT_PER_PAGE + items.length, [page, items.length])

    const setPageAndUrl = useCallback((nextPage: number) => {
        const params = new URLSearchParams(searchParams.toString())
        if (nextPage > 1) {
            params.set("page", String(nextPage))
        } else {
            params.delete("page")
        }
        const qs = params.toString()
        router.replace(qs ? `/surrogates/unassigned?${qs}` : "/surrogates/unassigned", { scroll: false })
    }, [router, searchParams])

    const handleClaim = useCallback(async (surrogateId: string) => {
        setClaimingId(surrogateId)
        try {
            await claimMutation.mutateAsync(surrogateId)
            toast.success("Surrogate claimed")
            router.push(`/surrogates/${surrogateId}`)
        } catch (e) {
            const message = e instanceof Error ? e.message : "Failed to claim surrogate"
            toast.error(message)
        } finally {
            setClaimingId(null)
        }
    }, [claimMutation, router])

    if (authLoaded && !canViewUnassignedQueue) return null

    return (
        <div className="space-y-6">
            <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Unassigned Queue</h1>
                    <p className="text-muted-foreground">
                        Claim a surrogate to start working the case.
                    </p>
                </div>
                <Button
                    variant="outline"
                    onClick={() => void refetch()}
                    disabled={isLoading}
                >
                    Refresh
                </Button>
            </div>

            <Card>
                <CardHeader className="pb-3">
                    <div className="flex items-center justify-between gap-4 flex-wrap">
                        <CardTitle className="text-lg">Available Cases</CardTitle>
                        <div className="text-sm text-muted-foreground">
                            {total !== null ? `${total} total` : " "}
                        </div>
                    </div>
                </CardHeader>

                <CardContent className="px-0">
                    {!authLoaded || isLoading ? (
                        <div className="flex items-center justify-center py-12 text-muted-foreground">
                            <Loader2Icon className="mr-2 h-4 w-4 animate-spin" />
                            Loading unassigned cases...
                        </div>
                    ) : error ? (
                        <div className="px-6 py-10">
                            <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-4">
                                <div className="font-medium text-destructive">Failed to load unassigned cases</div>
                                <div className="mt-1 text-sm text-muted-foreground">
                                    {error instanceof Error ? error.message : "Unknown error"}
                                </div>
                            </div>
                        </div>
                    ) : items.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-16 text-center">
                            <div className="text-lg font-medium">No unassigned cases</div>
                            <div className="mt-1 text-sm text-muted-foreground">
                                When new leads arrive, they will show up here for you to claim.
                            </div>
                            <Button className="mt-4" onClick={() => setPageAndUrl(1)}>
                                Back to first page
                            </Button>
                        </div>
                    ) : (
                        <>
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Surrogate</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead>Source</TableHead>
                                        <TableHead>State</TableHead>
                                        <TableHead>Created</TableHead>
                                        <TableHead className="text-right">Action</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {items.map((s) => (
                                        <TableRow key={s.id}>
                                            <TableCell className="font-medium">
                                                <div className="flex flex-col">
                                                    <Link
                                                        href={`/surrogates/${s.id}`}
                                                        className="hover:underline"
                                                    >
                                                        {s.full_name}
                                                    </Link>
                                                    <span className="text-xs text-muted-foreground">
                                                        {s.surrogate_number}
                                                    </span>
                                                </div>
                                            </TableCell>
                                            <TableCell>
                                                <Badge variant="secondary">
                                                    {s.status_label}
                                                </Badge>
                                            </TableCell>
                                            <TableCell>
                                                <Badge variant="outline" className="capitalize">
                                                    {s.source}
                                                </Badge>
                                            </TableCell>
                                            <TableCell>{s.state || "—"}</TableCell>
                                            <TableCell className="text-muted-foreground">
                                                {formatDate(s.created_at)}
                                            </TableCell>
                                            <TableCell className="text-right">
                                                <Button
                                                    size="sm"
                                                    onClick={() => handleClaim(s.id)}
                                                    disabled={claimMutation.isPending}
                                                >
                                                    {claimingId === s.id ? (
                                                        <>
                                                            <Loader2Icon className="mr-2 h-4 w-4 animate-spin" />
                                                            Claiming...
                                                        </>
                                                    ) : (
                                                        <>
                                                            <UserPlusIcon className="mr-2 h-4 w-4" />
                                                            Claim
                                                        </>
                                                    )}
                                                </Button>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>

                            {totalPages > 1 && (
                                <div className="flex items-center justify-between border-t border-border px-6 py-4">
                                    <div className="text-sm text-muted-foreground">
                                        {total !== null ? (
                                            <>Showing {pageStart}-{Math.min(pageEnd, total)} of {total} cases</>
                                        ) : (
                                            <>Showing {pageStart}-{pageEnd} cases</>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-2 flex-wrap">
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            disabled={page <= 1}
                                            onClick={() => setPageAndUrl(Math.max(1, page - 1))}
                                        >
                                            Previous
                                        </Button>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            disabled={page >= totalPages}
                                            onClick={() => setPageAndUrl(Math.min(totalPages, page + 1))}
                                        >
                                            Next
                                        </Button>
                                        <PaginationJump
                                            page={page}
                                            totalPages={totalPages}
                                            onPageChange={setPageAndUrl}
                                        />
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </CardContent>
            </Card>
        </div>
    )
}
