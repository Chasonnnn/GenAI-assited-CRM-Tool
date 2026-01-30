"use client"

import { Fragment, useEffect, useState } from "react"
import Link from "@/components/app-link"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
    CheckCircle2Icon,
    XCircleIcon,
    AlertCircleIcon,
    MinusCircleIcon,
    ChevronDownIcon,
    ChevronRightIcon,
    ActivityIcon,
    TrendingUpIcon,
    ClockIcon,
    Loader2Icon,
} from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import api from "@/lib/api"
import { parseDateInput } from "@/lib/utils/date"

// Types for executions
interface ExecutionAction {
    success: boolean
    action_type?: string
    description?: string
    duration_ms?: number
    error?: string
}

interface Execution {
    id: string
    status: "success" | "failed" | "partial" | "skipped" | "paused" | "canceled" | "expired"
    workflow_id: string
    workflow_name: string
    entity_type: string
    entity_id: string
    action_count: number
    duration_ms: number
    executed_at: string
    trigger_event: Record<string, unknown>
    actions_executed: ExecutionAction[]
    error_message?: string
    skip_reason?: string
}

interface ExecutionStats {
    total_24h: number
    success_rate: number
    failed_24h: number
    avg_duration_ms: number
}

const statusConfig = {
    success: {
        label: "Success",
        color: "bg-green-500/10 text-green-500 border-green-500/20",
        icon: CheckCircle2Icon,
    },
    failed: {
        label: "Failed",
        color: "bg-red-500/10 text-red-500 border-red-500/20",
        icon: XCircleIcon,
    },
    partial: {
        label: "Partial",
        color: "bg-orange-500/10 text-orange-500 border-orange-500/20",
        icon: AlertCircleIcon,
    },
    skipped: {
        label: "Skipped",
        color: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
        icon: MinusCircleIcon,
    },
    paused: {
        label: "Paused",
        color: "bg-blue-500/10 text-blue-500 border-blue-500/20",
        icon: AlertCircleIcon,
    },
    canceled: {
        label: "Canceled",
        color: "bg-gray-500/10 text-gray-500 border-gray-500/20",
        icon: MinusCircleIcon,
    },
    expired: {
        label: "Expired",
        color: "bg-orange-500/10 text-orange-500 border-orange-500/20",
        icon: AlertCircleIcon,
    },
}

const isStatusKey = (value: string): value is keyof typeof statusConfig =>
    Object.prototype.hasOwnProperty.call(statusConfig, value)

// Helper to format duration
function formatDuration(ms: number): string {
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(1)}s`
}

// Helper to format relative time
function formatRelativeTime(dateString: string): string {
    const date = parseDateInput(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return "Just now"
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays === 1) return "Yesterday"
    return `${diffDays}d ago`
}

// API fetch functions
async function fetchExecutions(params: {
    status?: string
    workflow_id?: string
    page?: number
}): Promise<{ items: Execution[]; total: number }> {
    const searchParams = new URLSearchParams()
    if (params.status && params.status !== "all") searchParams.set("status", params.status)
    if (params.workflow_id && params.workflow_id !== "all") searchParams.set("workflow_id", params.workflow_id)
    if (params.page) searchParams.set("page", String(params.page))

    const query = searchParams.toString()
    return api.get<{ items: Execution[]; total: number }>(`/workflows/executions${query ? `?${query}` : ""}`)
}

async function fetchExecutionStats(): Promise<ExecutionStats> {
    return api.get<ExecutionStats>("/workflows/executions/stats")
}

async function fetchWorkflows(): Promise<{ id: string; name: string }[]> {
    return api.get<{ id: string; name: string }[]>("/workflows")
}

function getEntityLink(entityType: string, entityId: string): string | null {
    switch (entityType.toLowerCase()) {
        case "surrogate":
            return `/surrogates/${entityId}`
        case "intended_parent":
            return `/intended-parents/${entityId}`
        case "match":
            return `/intended-parents/matches/${entityId}`
        default:
            return null
    }
}

export default function WorkflowExecutionsPage() {
    const [statusFilter, setStatusFilter] = useState("all")
    const [workflowFilter, setWorkflowFilter] = useState("all")
    const [page, setPage] = useState(1)
    const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())

    useEffect(() => {
        setPage(1)
    }, [statusFilter, workflowFilter])

    // Fetch data
    const { data: executionsData, isLoading: executionsLoading } = useQuery({
        queryKey: ["workflow-executions", statusFilter, workflowFilter, page],
        queryFn: () => fetchExecutions({ status: statusFilter, workflow_id: workflowFilter, page }),
    })

    const { data: stats, isLoading: statsLoading } = useQuery({
        queryKey: ["workflow-execution-stats"],
        queryFn: fetchExecutionStats,
    })

    const { data: workflows } = useQuery({
        queryKey: ["workflows-list"],
        queryFn: fetchWorkflows,
    })

    const toggleRow = (id: string) => {
        setExpandedRows((prev) => {
            const next = new Set(prev)
            if (next.has(id)) {
                next.delete(id)
            } else {
                next.add(id)
            }
            return next
        })
    }

    const executions = executionsData?.items || []
    const totalExecutions = executionsData?.total || 0
    const totalPages = Math.ceil(totalExecutions / 20)

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <div>
                        <h1 className="text-2xl font-semibold">Workflow Executions</h1>
                        <p className="text-xs text-muted-foreground">
                            {totalExecutions.toLocaleString()} executions in last 24 hours
                        </p>
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 space-y-6 p-6">

            {/* Stats Cards */}
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
                <Card>
                    <CardContent className="pt-6">
                        <div className="flex items-center gap-3">
                            <div className="flex size-10 items-center justify-center rounded-lg bg-teal-500/10">
                                <ActivityIcon className="size-5 text-teal-500" />
                            </div>
                            <div>
                                <p className="text-sm text-muted-foreground">Total 24h</p>
                                {statsLoading ? (
                                    <Loader2Icon className="h-5 w-5 animate-spin text-muted-foreground" />
                                ) : (
                                    <p className="text-2xl font-bold">{stats?.total_24h || 0}</p>
                                )}
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="pt-6">
                        <div className="flex items-center gap-3">
                            <div className="flex size-10 items-center justify-center rounded-lg bg-green-500/10">
                                <TrendingUpIcon className="size-5 text-green-500" />
                            </div>
                            <div>
                                <p className="text-sm text-muted-foreground">Success Rate</p>
                                {statsLoading ? (
                                    <Loader2Icon className="h-5 w-5 animate-spin text-muted-foreground" />
                                ) : (
                                    <p className="text-2xl font-bold">{stats?.success_rate?.toFixed(1) || 0}%</p>
                                )}
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="pt-6">
                        <div className="flex items-center gap-3">
                            <div className="flex size-10 items-center justify-center rounded-lg bg-red-500/10">
                                <XCircleIcon className="size-5 text-red-500" />
                            </div>
                            <div>
                                <p className="text-sm text-muted-foreground">Failed 24h</p>
                                {statsLoading ? (
                                    <Loader2Icon className="h-5 w-5 animate-spin text-muted-foreground" />
                                ) : (
                                    <p className="text-2xl font-bold">{stats?.failed_24h || 0}</p>
                                )}
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="pt-6">
                        <div className="flex items-center gap-3">
                            <div className="flex size-10 items-center justify-center rounded-lg bg-blue-500/10">
                                <ClockIcon className="size-5 text-blue-500" />
                            </div>
                            <div>
                                <p className="text-sm text-muted-foreground">Avg Duration</p>
                                {statsLoading ? (
                                    <Loader2Icon className="h-5 w-5 animate-spin text-muted-foreground" />
                                ) : (
                                    <p className="text-2xl font-bold">{formatDuration(stats?.avg_duration_ms || 0)}</p>
                                )}
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Filters */}
            <div className="flex flex-wrap items-center gap-3">
                <Select value={statusFilter} onValueChange={(v) => v && setStatusFilter(v)}>
                    <SelectTrigger className="w-[180px]">
                        <SelectValue placeholder="All Statuses">
                            {(value: string | null) => {
                                if (!value || value === "all") return "All Statuses"
                                if (value && isStatusKey(value)) {
                                    return statusConfig[value].label
                                }
                                return value
                            }}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Statuses</SelectItem>
                        <SelectItem value="success">Success</SelectItem>
                        <SelectItem value="failed">Failed</SelectItem>
                        <SelectItem value="skipped">Skipped</SelectItem>
                        <SelectItem value="partial">Partial</SelectItem>
                    </SelectContent>
                </Select>

                <Select value={workflowFilter} onValueChange={(v) => v && setWorkflowFilter(v)}>
                    <SelectTrigger className="w-[220px]">
                        <SelectValue placeholder="All Workflows">
                            {(value: string | null) => {
                                if (!value || value === "all") return "All Workflows"
                                const workflow = workflows?.find(w => w.id === value)
                                return workflow?.name ?? value
                            }}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Workflows</SelectItem>
                        {workflows?.map((wf) => (
                            <SelectItem key={wf.id} value={wf.id}>
                                {wf.name}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {/* Table */}
            <Card className="py-0">
                <div className="overflow-x-auto">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead className="w-[50px]"></TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Workflow</TableHead>
                                <TableHead>Entity</TableHead>
                                <TableHead>Actions</TableHead>
                                <TableHead>Duration</TableHead>
                                <TableHead>Executed At</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {executionsLoading ? (
                                <TableRow>
                                    <TableCell colSpan={7} className="py-12 text-center">
                                        <Loader2Icon className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
                                        <p className="mt-2 text-sm text-muted-foreground">Loading executions...</p>
                                    </TableCell>
                                </TableRow>
                            ) : executions.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={7} className="py-12 text-center">
                                        <ActivityIcon className="mx-auto h-8 w-8 text-muted-foreground/50" />
                                        <p className="mt-2 text-sm text-muted-foreground">No executions found</p>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                executions.map((execution) => {
                                    const StatusIcon = statusConfig[execution.status]?.icon || AlertCircleIcon
                                    const isExpanded = expandedRows.has(execution.id)
                                    const entityLink = getEntityLink(execution.entity_type, execution.entity_id)

                                    return (
                                        <Fragment key={execution.id}>
                                            <TableRow
                                                className="cursor-pointer hover:bg-muted/50"
                                                onClick={() => toggleRow(execution.id)}
                                            >
                                                <TableCell>
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        className="size-8 p-0"
                                                        aria-label={isExpanded ? "Collapse row" : "Expand row"}
                                                    >
                                                        {isExpanded ? (
                                                            <ChevronDownIcon className="size-4" />
                                                        ) : (
                                                            <ChevronRightIcon className="size-4" />
                                                        )}
                                                    </Button>
                                                </TableCell>
                                                <TableCell>
                                                    <Badge
                                                        variant="secondary"
                                                        className={statusConfig[execution.status]?.color || ""}
                                                    >
                                                        <StatusIcon className="mr-1 size-3" />
                                                        {statusConfig[execution.status]?.label || execution.status}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell className="font-medium">{execution.workflow_name}</TableCell>
                                                <TableCell>
                                                    {execution.entity_type === "System" ? (
                                                        <span className="text-muted-foreground">System</span>
                                                    ) : entityLink ? (
                                                        <Link
                                                            href={entityLink}
                                                            className="text-primary hover:underline"
                                                            onClick={(e) => e.stopPropagation()}
                                                        >
                                                            {execution.entity_type} #{execution.entity_id.slice(0, 8)}
                                                        </Link>
                                                    ) : (
                                                        <span className="text-muted-foreground">
                                                            {execution.entity_type} #{execution.entity_id.slice(0, 8)}
                                                        </span>
                                                    )}
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant="secondary">{execution.action_count} actions</Badge>
                                                </TableCell>
                                                <TableCell className="text-muted-foreground">
                                                    {formatDuration(execution.duration_ms)}
                                                </TableCell>
                                                <TableCell className="text-muted-foreground">
                                                    {formatRelativeTime(execution.executed_at)}
                                                </TableCell>
                                            </TableRow>

                                            {/* Expandable Row Details */}
                                            {isExpanded && (
                                                <TableRow key={`${execution.id}-details`}>
                                                    <TableCell colSpan={7} className="bg-muted/30 p-6">
                                                        <div className="space-y-6">
                                                            {/* Actions Timeline */}
                                                            {execution.actions_executed && execution.actions_executed.length > 0 && (
                                                                <div>
                                                                    <h4 className="mb-3 font-semibold">Actions Executed</h4>
                                                                    <div className="space-y-3">
                                                                        {execution.actions_executed.map((action, index) => {
                                                                            const status = action.success ? "success" : "failed"
                                                                            const name =
                                                                                action.description ||
                                                                                action.action_type ||
                                                                                "Action"
                                                                            const duration = action.duration_ms
                                                                                ? formatDuration(action.duration_ms)
                                                                                : "—"
                                                                            return (
                                                                            <div key={index} className="flex items-start gap-3">
                                                                                <div
                                                                                    className={`mt-1 flex size-6 shrink-0 items-center justify-center rounded-full ${status === "success" ? "bg-green-500/20" : "bg-red-500/20"
                                                                                        }`}
                                                                                >
                                                                                    {status === "success" ? (
                                                                                        <CheckCircle2Icon className="size-3 text-green-500" />
                                                                                    ) : (
                                                                                        <XCircleIcon className="size-3 text-red-500" />
                                                                                    )}
                                                                                </div>
                                                                                <div className="flex-1">
                                                                                    <div className="flex items-center justify-between">
                                                                                        <p className="font-medium">{name}</p>
                                                                                        <span className="text-xs text-muted-foreground">
                                                                                            {duration}
                                                                                        </span>
                                                                                    </div>
                                                                                    {action.error && (
                                                                                        <p className="mt-1 text-sm text-red-500">{action.error}</p>
                                                                                    )}
                                                                                </div>
                                                                            </div>
                                                                            )
                                                                        })}
                                                                    </div>
                                                                </div>
                                                            )}

                                                            {/* Skip Reason */}
                                                            {execution.skip_reason && (
                                                                <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-4">
                                                                    <p className="text-sm">
                                                                        <span className="font-semibold text-yellow-600">Skipped: </span>
                                                                        {execution.skip_reason}
                                                                    </p>
                                                                </div>
                                                            )}

                                                            {/* Error Message */}
                                                            {execution.error_message && (
                                                                <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-4">
                                                                    <div className="flex items-start gap-2">
                                                                        <AlertCircleIcon className="mt-0.5 size-4 shrink-0 text-red-500" />
                                                                        <div>
                                                                            <p className="font-semibold text-red-600">Error</p>
                                                                            <p className="mt-1 text-sm text-red-600">{execution.error_message}</p>
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                            )}

                                                            {/* Trigger Event Info */}
                                                            <div>
                                                                <h4 className="mb-3 font-semibold">Trigger Event</h4>
                                                                <div className="rounded-lg border bg-card p-4">
                                                                    <div className="space-y-2 text-sm">
                                                                        {Object.entries(execution.trigger_event || {}).map(([key, value]) => (
                                                                            <div key={key} className="flex justify-between">
                                                                                <span className="text-muted-foreground">{key}:</span>
                                                                                <code className="rounded bg-muted px-2 py-0.5 font-mono text-xs">
                                                                                    {typeof value === "object" ? JSON.stringify(value) : String(value)}
                                                                                </code>
                                                                            </div>
                                                                        ))}
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </TableCell>
                                                </TableRow>
                                            )}
                                        </Fragment>
                                    )
                                })
                            )}
                        </TableBody>
                    </Table>
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                    <div className="flex items-center justify-between border-t border-border px-6 py-4">
                        <div className="text-sm text-muted-foreground">
                            Page {page} of {totalPages} ({totalExecutions.toLocaleString()} executions)
                        </div>
                        <div className="flex items-center gap-2">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setPage((p) => Math.max(1, p - 1))}
                                disabled={page === 1}
                            >
                                Previous
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                                disabled={page >= totalPages}
                            >
                                Next
                            </Button>
                        </div>
                    </div>
                )}
            </Card>
            </div>
        </div>
    )
}
