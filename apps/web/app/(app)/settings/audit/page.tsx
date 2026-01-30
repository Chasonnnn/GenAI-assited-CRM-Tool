"use client"

import { useEffect, useMemo, useState } from "react"
import { formatDateTime, formatRelativeTime } from "@/lib/formatters"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { DateRangePicker, type DateRangePreset } from "@/components/ui/date-range-picker"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Loader2Icon, ChevronLeft, ChevronRight, FileText, User, Shield, Settings, Download, Upload, Sparkles, AlertTriangle, CheckIcon, XIcon, Trash2 } from "lucide-react"
import { useAIAuditActivity, useAuditExports, useAuditLogs, useCreateAuditExport, useEventTypes } from "@/lib/hooks/use-audit"
import { useAuth } from "@/lib/auth-context"

// Event type icons and labels
const EVENT_CONFIG: Record<string, { icon: React.ElementType; label: string; color: string }> = {
    // Version control events
    pipeline_updated: { icon: Settings, label: "Pipeline Updated", color: "bg-blue-500" },
    pipeline_rolled_back: { icon: Settings, label: "Pipeline Rollback", color: "bg-orange-500" },
    email_template_updated: { icon: FileText, label: "Template Updated", color: "bg-blue-500" },
    email_template_rolled_back: { icon: FileText, label: "Template Rollback", color: "bg-orange-500" },
    // Auth events
    user_login: { icon: User, label: "User Login", color: "bg-green-500" },
    user_logout: { icon: User, label: "User Logout", color: "bg-gray-500" },
    // Security events
    permission_changed: { icon: Shield, label: "Permission Change", color: "bg-red-500" },
    // Task events
    task_deleted: { icon: Trash2, label: "Task Deleted", color: "bg-rose-500" },
    // AI events
    ai_action_approved: { icon: Sparkles, label: "AI Action Approved", color: "bg-emerald-500" },
    ai_action_rejected: { icon: Sparkles, label: "AI Action Rejected", color: "bg-slate-500" },
    ai_action_failed: { icon: AlertTriangle, label: "AI Action Failed", color: "bg-rose-500" },
    ai_action_denied: { icon: AlertTriangle, label: "AI Action Denied", color: "bg-amber-500" },
}

const AI_EVENT_LABELS: Record<string, { label: string; icon: React.ElementType; tone: string }> = {
    ai_action_approved: { label: "Approved", icon: CheckIcon, tone: "text-emerald-600" },
    ai_action_rejected: { label: "Rejected", icon: XIcon, tone: "text-slate-500" },
    ai_action_failed: { label: "Failed", icon: AlertTriangle, tone: "text-rose-600" },
    ai_action_denied: { label: "Denied", icon: AlertTriangle, tone: "text-amber-600" },
}

function getEventConfig(eventType: string) {
    return EVENT_CONFIG[eventType] || {
        icon: FileText,
        label: eventType.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()),
        color: "bg-muted"
    }
}

export default function AuditLogPage() {
    const { user } = useAuth()
    const isDeveloper = user?.role === "developer"

    const [page, setPage] = useState(1)
    const [eventTypeFilter, setEventTypeFilter] = useState<string>("all")
    const perPage = 20
    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

    type ExportFormat = "csv" | "json"
    const isExportFormat = (value: string | null): value is ExportFormat =>
        value === "csv" || value === "json"

    type RedactMode = "redacted" | "full"
    const isRedactMode = (value: string | null): value is RedactMode =>
        value === "redacted" || value === "full"

    const AI_ACTIVITY_HOURS = [24, 168, 720] as const
    type AiActivityHours = (typeof AI_ACTIVITY_HOURS)[number]
    const isAiActivityHours = (value: number): value is AiActivityHours =>
        AI_ACTIVITY_HOURS.includes(value as AiActivityHours)

    const [exportFormat, setExportFormat] = useState<ExportFormat>("csv")
    const [redactMode, setRedactMode] = useState<RedactMode>("redacted")
    const [exportRange, setExportRange] = useState<DateRangePreset>("month")
    const [customRange, setCustomRange] = useState<{ from: Date | undefined; to: Date | undefined }>({
        from: undefined,
        to: undefined,
    })
    const [acknowledgment, setAcknowledgment] = useState("")
    const [aiActivityHours, setAiActivityHours] = useState<AiActivityHours>(24) // 24h, 7d, 30d

    const filters = {
        page,
        per_page: perPage,
        ...(eventTypeFilter !== "all" && { event_type: eventTypeFilter }),
    }

    const { data: auditData, isLoading } = useAuditLogs(filters)
    const { data: eventTypes } = useEventTypes()
    const { data: exportJobs, refetch: refetchExports } = useAuditExports()
    const createExport = useCreateAuditExport()
    const { data: aiActivity, isLoading: aiActivityLoading } = useAIAuditActivity(aiActivityHours)

    const aiActivityLabel = aiActivityHours === 24 ? "24 hours" : aiActivityHours === 168 ? "7 days" : "30 days"

    const totalPages = auditData ? Math.ceil(auditData.total / perPage) : 0

    const visibleExportJobs = useMemo(() => {
        const items = exportJobs?.items ?? []
        if (isDeveloper) return items
        return items.filter(job => job.redact_mode !== "full")
    }, [exportJobs, isDeveloper])

    const hasPendingExports = useMemo(
        () => visibleExportJobs.some(job => ["pending", "processing"].includes(job.status)),
        [visibleExportJobs]
    )

    useEffect(() => {
        if (!hasPendingExports) return
        const timer = setInterval(() => {
            refetchExports()
        }, 8000)
        return () => clearInterval(timer)
    }, [hasPendingExports, refetchExports])

    const getExportDates = () => {
        const now = new Date()
        if (exportRange === "custom" && customRange.from && customRange.to) {
            return { start: customRange.from, end: customRange.to }
        }
        if (exportRange === "today") {
            const start = new Date(now.getFullYear(), now.getMonth(), now.getDate())
            return { start, end: now }
        }
        if (exportRange === "week") {
            const start = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
            return { start, end: now }
        }
        if (exportRange === "month") {
            const start = new Date(now.getFullYear(), now.getMonth(), 1)
            return { start, end: now }
        }
        return { start: new Date(0), end: now }
    }

    const handleExport = async () => {
        const { start, end } = getExportDates()
        if (exportRange === "custom" && (!customRange.from || !customRange.to)) {
            return
        }
        await createExport.mutateAsync({
            start_date: start.toISOString(),
            end_date: end.toISOString(),
            format: exportFormat,
            redact_mode: redactMode,
            ...(redactMode === "full" && acknowledgment.trim()
                ? { acknowledgment: acknowledgment.trim() }
                : {}),
        })
        setAcknowledgment("")
    }

    const handleDownload = (url: string) => {
        window.open(`${API_BASE}${url}`, "_blank", "noopener,noreferrer")
    }

    const handleFilterAIEvents = () => {
        setEventTypeFilter("ai_action_approved")
    }

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center px-6">
                    <h1 className="text-2xl font-semibold">Audit Log</h1>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-6">
                <Card className="mb-6">
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <div>
                                <CardTitle>Export Audit Logs</CardTitle>
                                <CardDescription>Generate compliance-ready CSV or JSON exports</CardDescription>
                            </div>
                            <div className="flex items-center gap-2">
                                <Download className="size-5 text-muted-foreground" />
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="flex flex-wrap gap-4">
                            <div className="flex flex-col gap-2">
                                <Label className="text-sm text-muted-foreground">Date Range</Label>
                                <DateRangePicker
                                    preset={exportRange}
                                    onPresetChange={setExportRange}
                                    customRange={customRange}
                                    onCustomRangeChange={setCustomRange}
                                    ariaLabel="Date range"
                                />
                            </div>
                            <div className="flex flex-col gap-2">
                                <Label htmlFor="export-format" className="text-sm text-muted-foreground">Format</Label>
                                <Select
                                    value={exportFormat}
                                    onValueChange={(value) => {
                                        if (isExportFormat(value)) {
                                            setExportFormat(value)
                                        }
                                    }}
                                >
                                    <SelectTrigger id="export-format" className="w-[160px]">
                                        <SelectValue>
                                            {(value: string | null) => value?.toUpperCase() ?? "CSV"}
                                        </SelectValue>
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="csv">CSV</SelectItem>
                                        <SelectItem value="json">JSON</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="flex flex-col gap-2">
                                <Label htmlFor="export-redaction" className="text-sm text-muted-foreground">Redaction</Label>
                                <Select
                                    value={redactMode}
                                    onValueChange={(value) => {
                                        if (isRedactMode(value)) {
                                            setRedactMode(value)
                                        }
                                    }}
                                    disabled={!isDeveloper}
                                >
                                    <SelectTrigger id="export-redaction" className="w-[180px]">
                                        <SelectValue>
                                            {(value: string | null) => {
                                                return value === "full" ? "Full (Developer)" : "Redacted (default)"
                                            }}
                                        </SelectValue>
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="redacted">Redacted (default)</SelectItem>
                                        <SelectItem value="full">Full (Developer)</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="flex flex-col gap-2">
                                <Label className="text-sm text-muted-foreground">Request Export</Label>
                                <Button
                                    onClick={handleExport}
                                    disabled={createExport.isPending || (redactMode === "full" && !acknowledgment.trim())}
                                >
                                    {createExport.isPending ? (
                                        <Loader2Icon className="size-4 animate-spin motion-reduce:animate-none mr-2" aria-hidden="true" />
                                    ) : (
                                        <Upload className="size-4 mr-2" aria-hidden="true" />
                                    )}
                                    Create Export
                                </Button>
                            </div>
                        </div>

                        {redactMode === "full" && isDeveloper && (
                            <div className="max-w-xl space-y-2">
                                <p className="text-sm text-muted-foreground">
                                    Full exports contain PHI. Type confirmation to proceed.
                                </p>
                                <Input
                                    id="export-confirmation"
                                    name="exportConfirmation"
                                    autoComplete="off"
                                    aria-label="Confirmation phrase"
                                    placeholder="Type confirmation (e.g. I UNDERSTAND)"
                                    value={acknowledgment}
                                    onChange={(e) => setAcknowledgment(e.target.value)}
                                />
                            </div>
                        )}

                        {redactMode === "redacted" && (
                            <div className="max-w-xl rounded-md border border-amber-200 bg-amber-50 dark:border-amber-900/50 dark:bg-amber-950/30 p-3">
                                <p className="text-sm text-amber-800 dark:text-amber-200">
                                    <strong>⚠️ Best-Effort Redaction:</strong> Redacted exports apply automated
                                    pattern matching for PHI (emails, phones, SSNs, etc.). Free-text fields may
                                    contain PHI not detected by automated redaction. Review exports before sharing.
                                </p>
                            </div>
                        )}

                        {visibleExportJobs.length ? (
                            <div className="border rounded-lg">
                                <div className="flex items-center justify-between px-4 py-2 border-b">
                                    <span className="text-sm font-medium">Recent Exports</span>
                                    {hasPendingExports && (
                                        <span className="text-xs text-muted-foreground">Refreshing…</span>
                                    )}
                                </div>
                                <div className="divide-y">
                                    {visibleExportJobs.slice(0, 5).map((job) => (
                                        <div key={job.id} className="flex items-center justify-between px-4 py-3">
                                            <div className="space-y-1">
                                                <div className="flex items-center gap-2">
                                                    <Badge variant="outline">{job.format.toUpperCase()}</Badge>
                                                    <Badge variant={job.redact_mode === "full" ? "destructive" : "secondary"}>
                                                        {job.redact_mode}
                                                    </Badge>
                                                    <Badge variant="outline" className="capitalize">
                                                        {job.status}
                                                    </Badge>
                                                </div>
                                                <p className="text-xs text-muted-foreground">
                                                    Created {formatRelativeTime(job.created_at, "Unknown")}
                                                </p>
                                                {job.error_message && (
                                                    <p className="text-xs text-red-500">{job.error_message}</p>
                                                )}
                                            </div>
                                            <div>
                                                {job.download_url && (
                                                    <Button variant="outline" size="sm" onClick={() => handleDownload(job.download_url!)}>
                                                        Download
                                                    </Button>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <div className="text-sm text-muted-foreground">No export jobs yet.</div>
                        )}
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <div>
                                <CardTitle>Activity Log</CardTitle>
                                <CardDescription>Track all changes and actions in your organization</CardDescription>
                            </div>
                            <div className="flex items-center gap-4">
                                {/* Event Type Filter */}
                                <Select
                                    value={eventTypeFilter}
                                    onValueChange={(value) => setEventTypeFilter(value ?? "all")}
                                >
                                    <SelectTrigger className="w-[200px]">
                                        <SelectValue placeholder="Filter by event type">
                                            {(value: string | null) => {
                                                if (!value || value === "all") return "All Events"
                                                return getEventConfig(value).label
                                            }}
                                        </SelectValue>
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="all">All Events</SelectItem>
                                        {eventTypes?.map((type) => (
                                            <SelectItem key={type} value={type}>
                                                {getEventConfig(type).label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="mb-6 rounded-lg border p-4">
                            <div className="flex flex-wrap items-start justify-between gap-4">
                                <div>
                                    <p className="text-sm font-semibold">AI Activity</p>
                                    <p className="text-xs text-muted-foreground">Last {aiActivityLabel}</p>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Select
                                        value={String(aiActivityHours)}
                                        onValueChange={(value) => {
                                            const parsed = Number(value)
                                            if (isAiActivityHours(parsed)) {
                                                setAiActivityHours(parsed)
                                            }
                                        }}
                                    >
                                        <SelectTrigger className="w-[100px] h-8 text-xs">
                                            <SelectValue>
                                                {(value: string | null) => {
                                                    const labels: Record<string, string> = { "24": "24 hours", "168": "7 days", "720": "30 days" }
                                                    return labels[value ?? "24"] ?? "24 hours"
                                                }}
                                            </SelectValue>
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="24">24 hours</SelectItem>
                                            <SelectItem value="168">7 days</SelectItem>
                                            <SelectItem value="720">30 days</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <Button variant="outline" size="sm" onClick={handleFilterAIEvents}>
                                        Filter AI Events
                                    </Button>
                                </div>
                            </div>
                            <div className="mt-3 grid gap-3 md:grid-cols-2">
                                {Object.entries(AI_EVENT_LABELS).map(([key, meta]) => (
                                    <div key={key} className="flex items-center gap-2 text-sm">
                                        <meta.icon className={`h-4 w-4 ${meta.tone}`} />
                                        <span className="flex-1 text-muted-foreground">{meta.label}</span>
                                        <span className="font-semibold text-foreground">
                                            {aiActivity?.counts?.[key] ?? 0}
                                        </span>
                                    </div>
                                ))}
                            </div>
                            <div className="mt-4 border-t pt-4">
                                <p className="text-xs font-medium text-muted-foreground">Recent AI Events</p>
                                <div className="mt-2 space-y-2">
                                    {aiActivityLoading ? (
                                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                            <Loader2Icon className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                            Loading AI activity…
                                        </div>
                                    ) : aiActivity?.recent?.length ? (
                                        aiActivity.recent.map((entry) => {
                                            const meta = AI_EVENT_LABELS[entry.event_type] || {
                                                label: entry.event_type,
                                                icon: Sparkles,
                                                tone: "text-muted-foreground",
                                            }
                                            return (
                                                <button
                                                    key={entry.id}
                                                    className="flex items-start gap-2 text-xs w-full text-left hover:bg-muted/50 rounded p-1 -m-1 transition-colors"
                                                    onClick={() => setEventTypeFilter(entry.event_type)}
                                                >
                                                    <meta.icon className={`mt-0.5 h-3.5 w-3.5 ${meta.tone}`} />
                                                    <div className="flex-1">
                                                        <div className="font-medium text-foreground">{meta.label}</div>
                                                        <div className="text-[11px] text-muted-foreground">
                                                            {formatRelativeTime(entry.created_at, "Unknown")}
                                                        </div>
                                                    </div>
                                                </button>
                                            )
                                        })
                                    ) : (
                                        <div className="text-xs text-muted-foreground">
                                            No AI activity recorded yet.
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>

                        {isLoading ? (
                            <div className="py-12 flex items-center justify-center">
                                <Loader2Icon className="size-8 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                            </div>
                        ) : auditData?.items.length === 0 ? (
                            <div className="text-center py-12 text-muted-foreground">
                                No audit log entries found
                            </div>
                        ) : (
                            <div className="space-y-4">
                                {/* Audit entries */}
                                {auditData?.items.map((entry) => {
                                    const config = getEventConfig(entry.event_type)
                                    const Icon = config.icon
                                    const actorName = entry.actor_name || "System"
                                    const aiActorText: Record<string, string> = {
                                        ai_action_approved: `AI-generated • Approved by ${actorName}`,
                                        ai_action_rejected: `AI-generated • Rejected by ${actorName}`,
                                        ai_action_denied: `AI-generated • Denied by ${actorName}`,
                                        ai_action_failed: `AI-generated • Failed after approval by ${actorName}`,
                                    }
                                    const aiSummary = aiActorText[entry.event_type]

                                    return (
                                        <div
                                            key={entry.id}
                                            className="flex items-start gap-4 rounded-lg border border-border p-4"
                                        >
                                            <div className={`flex size-10 shrink-0 items-center justify-center rounded-lg ${config.color} text-white`}>
                                                <Icon className="size-5" />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 flex-wrap">
                                                    <Badge variant="outline">{config.label}</Badge>
                                                    {entry.target_type && (
                                                        <span className="text-sm text-muted-foreground">
                                                            {entry.target_type}
                                                        </span>
                                                    )}
                                                </div>
                                                <p className="text-sm text-muted-foreground mt-1">
                                                    {aiSummary ? (
                                                        <span className="font-medium text-foreground">{aiSummary}</span>
                                                    ) : entry.actor_name ? (
                                                        <span className="font-medium text-foreground">{entry.actor_name}</span>
                                                    ) : (
                                                        <span className="italic">System</span>
                                                    )}
                                                    {entry.details && Object.keys(entry.details).length > 0 && (
                                                        <span className="ml-2">
                                                            {JSON.stringify(entry.details).slice(0, 100)}
                                                            {JSON.stringify(entry.details).length > 100 ? "…" : ""}
                                                        </span>
                                                    )}
                                                </p>
                                                <p className="text-xs text-muted-foreground mt-1">
                                                    {formatDateTime(entry.created_at, "Unknown")}
                                                    {entry.ip_address && (
                                                        <span className="ml-2">from {entry.ip_address}</span>
                                                    )}
                                                </p>
                                            </div>
                                        </div>
                                    )
                                })}

                                {/* Pagination */}
                                {totalPages > 1 && (
                                    <div className="flex items-center justify-between pt-4 border-t border-border">
                                        <p className="text-sm text-muted-foreground">
                                            Page {page} of {totalPages} ({auditData?.total} total entries)
                                        </p>
                                        <div className="flex items-center gap-2">
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => setPage(p => Math.max(1, p - 1))}
                                                disabled={page <= 1}
                                            >
                                                <ChevronLeft className="h-4 w-4" />
                                                Previous
                                            </Button>
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                                                disabled={page >= totalPages}
                                            >
                                                Next
                                                <ChevronRight className="h-4 w-4" />
                                            </Button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
