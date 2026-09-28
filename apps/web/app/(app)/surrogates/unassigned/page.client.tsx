"use client"

import { useState } from "react"
import { redirect, useRouter } from "next/navigation"
import Link from "@/components/app-link"
import { toast } from "@/components/ui/toast"
import { InboxIcon, Loader2Icon, UserPlusIcon } from "lucide-react"

import { useAuth } from "@/lib/auth-context"
import { useUnassignedQueue } from "@/lib/hooks/use-surrogates"
import { useClaimSurrogate } from "@/lib/hooks/use-queues"
import { useDefaultPipeline } from "@/lib/hooks/use-pipelines"
import { useTrackUnassignedQueueView } from "@/lib/hooks/use-track-unassigned-queue-view"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"
import { readableForeground } from "@/lib/stage-colors"
import { getSurrogateSourceLabel } from "@/lib/surrogate-source-labels"

import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { EmptyValue } from "@/components/ui/empty-value"
import { PaginationJump } from "@/components/ui/pagination-jump"
import { PageHeader } from "@/components/page-header"
import { EmptyState } from "@/components/empty-state"
import { QueryErrorState } from "@/components/error-state"

const DEFAULT_PER_PAGE = 20
// Same fallback grey the /surrogates list uses when a stage has no colour.
const DEFAULT_STAGE_COLOR = "#6B7280"

function parsePageParam(value: string | null): number {
    const parsed = Number(value)
    return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : 1
}

const unassignedDateFormatter = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
})

function formatDate(dateString: string | null | undefined): string {
    if (!dateString) return "—"
    const date = new Date(dateString)
    if (Number.isNaN(date.getTime())) return "—"
    return unassignedDateFormatter.format(date)
}

type UnassignedSurrogatesPageProps = {
    initialPageParam: string | null
    initialSearchParams: string
}

export default function UnassignedSurrogatesPage({
    initialPageParam,
    initialSearchParams,
}: UnassignedSurrogatesPageProps) {
    const { user } = useAuth()
    const authLoaded = !!user?.role
    const canViewUnassignedQueue = user?.role === "admin" || user?.role === "developer"

    if (authLoaded && !canViewUnassignedQueue) {
        redirect("/surrogates")
        return null
    }

    return (
        <UnassignedSurrogatesContent
            initialPageParam={initialPageParam}
            initialSearchParams={initialSearchParams}
            authLoaded={authLoaded}
            canViewUnassignedQueue={canViewUnassignedQueue}
        />
    )
}

function UnassignedSurrogatesContent({
    initialPageParam,
    initialSearchParams,
    authLoaded,
    canViewUnassignedQueue,
}: UnassignedSurrogatesPageProps & {
    authLoaded: boolean
    canViewUnassignedQueue: boolean
}) {
    const { push, replace } = useRouter()
    const urlPage = parsePageParam(initialPageParam)
    const page = urlPage

    useTrackUnassignedQueueView(authLoaded && canViewUnassignedQueue)

    const { data, isLoading, isRefetching, error, refetch } = useUnassignedQueue(
        {
            page,
            per_page: DEFAULT_PER_PAGE,
        },
        { enabled: canViewUnassignedQueue }
    )
    const { data: defaultPipeline } = useDefaultPipeline()
    const stageById = new Map((defaultPipeline?.stages ?? []).map((stage) => [stage.id, stage]))
    const claimMutation = useClaimSurrogate()
    const [claimingId, setClaimingId] = useState<string | null>(null)

    const items = data?.items ?? []
    const totalPages = data?.pages ?? 0
    const total = data?.total ?? null

    const pageStart = (page - 1) * DEFAULT_PER_PAGE + (items.length > 0 ? 1 : 0)
    const pageEnd = (page - 1) * DEFAULT_PER_PAGE + items.length

    const setPageAndUrl = (nextPage: number) => {
        const params = new URLSearchParams(initialSearchParams)
        if (nextPage > 1) {
            params.set("page", String(nextPage))
        } else {
            params.delete("page")
        }
        const qs = params.toString()
        replace(qs ? `/surrogates/unassigned?${qs}` : "/surrogates/unassigned", { scroll: false })
    }

    const handleClaim = async (surrogateId: string) => {
        setClaimingId(surrogateId)
        const result = await claimMutation.mutateAsync(surrogateId).then(() => ({
            status: "success" as const,
        })).catch((error: unknown) => ({
            status: "error" as const,
            message: getActionErrorMessage(error, "Couldn't claim surrogate. Try again."),
        }))

        if (result.status === "success") {
            toast.success("Surrogate claimed")
            push(`/surrogates/${surrogateId}`)
        } else if (result.message) {
            toast.error(result.message)
        }
        setClaimingId(null)
    }

    return (
        <div className="flex h-full flex-col overflow-hidden">
            <PageHeader
                title="Unassigned Queue"
                count={total}
                countLabel="surrogates"
                actions={
                    <Button
                        variant="outline"
                        onClick={() => void refetch()}
                        disabled={isLoading || isRefetching}
                    >
                        Refresh
                    </Button>
                }
            />

            <div className="flex-1 overflow-auto p-6">
                {!authLoaded || isLoading ? (
                    <Card className="flex items-center justify-center p-12" aria-busy="true">
                        <Loader2Icon className="size-8 animate-spin text-muted-foreground" aria-hidden="true" />
                        <span className="sr-only">Loading unassigned surrogates</span>
                    </Card>
                ) : error ? (
                    <Card>
                        <QueryErrorState
                            error={error}
                            onRetry={() => void refetch()}
                            isRetrying={isRefetching}
                            title="Couldn't load unassigned surrogates"
                        />
                    </Card>
                ) : items.length === 0 ? (
                    <Card>
                        <EmptyState
                            icon={InboxIcon}
                            title="No unassigned surrogates"
                            action={
                                page > 1 ? (
                                    <Button variant="outline" onClick={() => setPageAndUrl(1)}>
                                        First page
                                    </Button>
                                ) : undefined
                            }
                        />
                    </Card>
                ) : (
                    <Card className="overflow-hidden py-0">
                            <Table className="[&_td:first-child]:pl-6 [&_td:last-child]:pr-6 [&_th:first-child]:pl-6 [&_th:last-child]:pr-6">
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
                                    {items.map((s) => {
                                        const stage = stageById.get(s.stage_id)
                                        const stageColor = stage?.color || DEFAULT_STAGE_COLOR
                                        return (
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
                                                        #{s.surrogate_number}
                                                    </span>
                                                </div>
                                            </TableCell>
                                            <TableCell>
                                                <Badge
                                                    style={{
                                                        backgroundColor: stageColor,
                                                        color: readableForeground(stageColor),
                                                    }}
                                                >
                                                    {s.status_label || stage?.label || "Unknown stage"}
                                                </Badge>
                                            </TableCell>
                                            <TableCell>
                                                <Badge variant="outline">
                                                    {getSurrogateSourceLabel(s.source)}
                                                </Badge>
                                            </TableCell>
                                            <TableCell>{s.state || <EmptyValue />}</TableCell>
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
                                                            <Loader2Icon className="mr-2 size-4 animate-spin" />
                                                            Claiming…
                                                        </>
                                                    ) : (
                                                        <>
                                                            <UserPlusIcon className="mr-2 size-4" />
                                                            Claim
                                                        </>
                                                    )}
                                                </Button>
                                            </TableCell>
                                        </TableRow>
                                        )
                                    })}
                                </TableBody>
                            </Table>

                            {totalPages > 1 && (
                                <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-6 py-4">
                                    <div className="text-sm text-muted-foreground">
                                        {total !== null ? (
                                            <>Showing {pageStart}-{Math.min(pageEnd, total)} of {total} surrogates</>
                                        ) : (
                                            <>Showing {pageStart}-{pageEnd} surrogates</>
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
                    </Card>
                )}
            </div>
        </div>
    )
}
