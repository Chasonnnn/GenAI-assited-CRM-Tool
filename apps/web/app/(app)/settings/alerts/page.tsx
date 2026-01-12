"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
    AlertTriangleIcon,
    AlertCircleIcon,
    XCircleIcon,
    CheckCircleIcon,
    ClockIcon,
    BellOffIcon,
    Loader2Icon,
    RefreshCwIcon,
} from "lucide-react"
import { useAlerts, useAlertsSummary, useResolveAlert, useAcknowledgeAlert, useSnoozeAlert } from "@/lib/hooks/use-ops"
import { formatDistanceToNow } from "date-fns"

const severityConfig = {
    critical: { icon: XCircleIcon, color: "text-red-600 bg-red-100 dark:bg-red-900/30", badge: "destructive" },
    error: { icon: AlertCircleIcon, color: "text-orange-600 bg-orange-100 dark:bg-orange-900/30", badge: "destructive" },
    warn: { icon: AlertTriangleIcon, color: "text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30", badge: "warning" },
} as const

const isSeverityKey = (value: string): value is keyof typeof severityConfig =>
    Object.prototype.hasOwnProperty.call(severityConfig, value)

const alertTypeLabels: Record<string, string> = {
    meta_fetch_failed: "Meta Lead Fetch Failed",
    meta_convert_failed: "Meta Lead Conversion Failed",
    meta_token_expiring: "Meta Token Expiring",
    meta_token_expired: "Meta Token Expired",
    worker_job_failed: "Worker Job Failed",
    api_error: "API Error",
}

export default function AlertsPage() {
    const [statusFilter, setStatusFilter] = useState<string>("open")

    const { data: summary, isLoading: summaryLoading, refetch: refetchSummary } = useAlertsSummary()
    const { data: alertsData, isLoading: alertsLoading, refetch: refetchAlerts } = useAlerts(
        statusFilter !== "all" ? { status: statusFilter } : {}
    )

    const resolveAlert = useResolveAlert()
    const acknowledgeAlert = useAcknowledgeAlert()
    const snoozeAlert = useSnoozeAlert()

    const handleRefresh = () => {
        refetchSummary()
        refetchAlerts()
    }

    const totalOpen = (summary?.warn ?? 0) + (summary?.error ?? 0) + (summary?.critical ?? 0)

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <div className="flex items-center gap-3">
                        <h1 className="text-2xl font-semibold">System Alerts</h1>
                        {totalOpen > 0 && (
                            <Badge variant="destructive">{totalOpen} open</Badge>
                        )}
                    </div>
                    <Button variant="outline" size="sm" onClick={handleRefresh}>
                        <RefreshCwIcon className="mr-2 size-4" />
                        Refresh
                    </Button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 space-y-6 p-6">
                {/* Summary Cards */}
                <div className="grid gap-4 md:grid-cols-3">
                    <Card className={summary?.critical && summary.critical > 0 ? "border-red-500" : ""}>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Critical</CardTitle>
                            <XCircleIcon className="size-4 text-red-600" />
                        </CardHeader>
                        <CardContent>
                            {summaryLoading ? (
                                <Loader2Icon className="size-6 animate-spin" />
                            ) : (
                                <div className="text-2xl font-bold text-red-600">{summary?.critical ?? 0}</div>
                            )}
                        </CardContent>
                    </Card>

                    <Card className={summary?.error && summary.error > 0 ? "border-orange-500" : ""}>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Errors</CardTitle>
                            <AlertCircleIcon className="size-4 text-orange-600" />
                        </CardHeader>
                        <CardContent>
                            {summaryLoading ? (
                                <Loader2Icon className="size-6 animate-spin" />
                            ) : (
                                <div className="text-2xl font-bold text-orange-600">{summary?.error ?? 0}</div>
                            )}
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Warnings</CardTitle>
                            <AlertTriangleIcon className="size-4 text-yellow-600" />
                        </CardHeader>
                        <CardContent>
                            {summaryLoading ? (
                                <Loader2Icon className="size-6 animate-spin" />
                            ) : (
                                <div className="text-2xl font-bold text-yellow-600">{summary?.warn ?? 0}</div>
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* Alerts List */}
                <Card>
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <CardTitle>Alerts</CardTitle>
                            <Select value={statusFilter} onValueChange={(v) => v && setStatusFilter(v)}>
                                <SelectTrigger className="w-40">
                                    <SelectValue>
                                        {(value: string | null) => {
                                            const labels: Record<string, string> = {
                                                open: "Open",
                                                acknowledged: "Acknowledged",
                                                resolved: "Resolved",
                                                snoozed: "Snoozed",
                                                all: "All",
                                            }
                                            return labels[value ?? "open"] ?? "Select status"
                                        }}
                                    </SelectValue>
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="open">Open</SelectItem>
                                    <SelectItem value="acknowledged">Acknowledged</SelectItem>
                                    <SelectItem value="resolved">Resolved</SelectItem>
                                    <SelectItem value="snoozed">Snoozed</SelectItem>
                                    <SelectItem value="all">All</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </CardHeader>
                    <CardContent>
                        {alertsLoading ? (
                            <div className="flex items-center justify-center py-12">
                                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                            </div>
                        ) : (alertsData?.items?.length ?? 0) === 0 ? (
                            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                                <CheckCircleIcon className="mb-2 size-12 text-green-500" />
                                <p className="text-lg font-medium">No {statusFilter === "all" ? "" : statusFilter} alerts</p>
                                <p className="text-sm">All systems operating normally</p>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                {alertsData?.items?.map((alert) => {
                                    const config = isSeverityKey(alert.severity)
                                        ? severityConfig[alert.severity]
                                        : severityConfig.warn
                                    const Icon = config.icon

                                    return (
                                        <div
                                            key={alert.id}
                                            className={`flex items-start gap-4 rounded-lg border p-4 ${config.color}`}
                                        >
                                            <Icon className="mt-0.5 size-5 flex-shrink-0" />
                                            <div className="flex-1 space-y-1">
                                                <div className="flex items-start justify-between gap-2">
                                                    <div>
                                                        <p className="font-medium">{alert.title}</p>
                                                        <p className="text-sm opacity-80">
                                                            {alertTypeLabels[alert.alert_type] || alert.alert_type}
                                                        </p>
                                                    </div>
                                                    <Badge variant={alert.status === "open" ? "destructive" : "secondary"}>
                                                        {alert.status}
                                                    </Badge>
                                                </div>
                                                {alert.message && (
                                                    <p className="text-sm opacity-70">{alert.message}</p>
                                                )}
                                                <div className="flex items-center gap-4 text-xs opacity-60">
                                                    <span>
                                                        First seen: {formatDistanceToNow(new Date(alert.first_seen_at), { addSuffix: true })}
                                                    </span>
                                                    {alert.occurrence_count > 1 && (
                                                        <span>Occurred {alert.occurrence_count} times</span>
                                                    )}
                                                </div>

                                                {/* Actions */}
                                                {alert.status === "open" && (
                                                    <div className="flex gap-2 pt-2">
                                                        <Button
                                                            size="sm"
                                                            variant="secondary"
                                                            onClick={() => acknowledgeAlert.mutate(alert.id)}
                                                            disabled={acknowledgeAlert.isPending}
                                                        >
                                                            <BellOffIcon className="mr-1 size-3" />
                                                            Acknowledge
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="secondary"
                                                            onClick={() => snoozeAlert.mutate({ alertId: alert.id, hours: 24 })}
                                                            disabled={snoozeAlert.isPending}
                                                        >
                                                            <ClockIcon className="mr-1 size-3" />
                                                            Snooze 24h
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="default"
                                                            onClick={() => resolveAlert.mutate(alert.id)}
                                                            disabled={resolveAlert.isPending}
                                                        >
                                                            <CheckCircleIcon className="mr-1 size-3" />
                                                            Resolve
                                                        </Button>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    )
                                })}
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
