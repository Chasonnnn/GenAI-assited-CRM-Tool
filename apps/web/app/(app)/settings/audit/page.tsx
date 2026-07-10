"use client"

import { useEffect, useState } from "react"
import {
    AlertTriangle,
    CheckIcon,
    ChevronLeft,
    ChevronRight,
    Download,
    FileText,
    Loader2Icon,
    Settings,
    Shield,
    Sparkles,
    Trash2,
    Upload,
    User,
    XIcon,
} from "lucide-react"

import { Badge as StatusBadge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { DateRangePicker, type DateRangePreset } from "@/components/ui/date-range-picker"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { useAuth } from "@/lib/auth-context"
import type { AIAuditActivity, AuditExportJob, AuditLogEntry } from "@/lib/api/audit"
import {
    useAIAuditActivity,
    useAuditExports,
    useAuditLogs,
    useCreateAuditExport,
    useEventTypes,
} from "@/lib/hooks/use-audit"
import { formatDateTime, formatRelativeTime } from "@/lib/formatters"

const EVENT_CONFIG: Record<string, { icon: React.ElementType; label: string; color: string }> = {
    pipeline_updated: { icon: Settings, label: "Pipeline Updated", color: "bg-blue-500" },
    pipeline_rolled_back: { icon: Settings, label: "Pipeline Rollback", color: "bg-orange-500" },
    email_template_updated: { icon: FileText, label: "Template Updated", color: "bg-blue-500" },
    email_template_rolled_back: { icon: FileText, label: "Template Rollback", color: "bg-orange-500" },
    user_login: { icon: User, label: "User Login", color: "bg-green-500" },
    user_logout: { icon: User, label: "User Logout", color: "bg-gray-500" },
    permission_changed: { icon: Shield, label: "Permission Change", color: "bg-red-500" },
    task_deleted: { icon: Trash2, label: "Task Deleted", color: "bg-rose-500" },
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

type ExportFormat = "csv" | "json"

function isExportFormat(value: string | null): value is ExportFormat {
    return value === "csv" || value === "json"
}

type RedactMode = "redacted" | "full"

function isRedactMode(value: string | null): value is RedactMode {
    return value === "redacted" || value === "full"
}

const AI_ACTIVITY_HOURS = [24, 168, 720] as const
type AiActivityHours = (typeof AI_ACTIVITY_HOURS)[number]

function isAiActivityHours(value: number): value is AiActivityHours {
    return AI_ACTIVITY_HOURS.includes(value as AiActivityHours)
}

type AuditDateRange = { from: Date | undefined; to: Date | undefined }

function getEventConfig(eventType: string) {
    return EVENT_CONFIG[eventType] || {
        icon: FileText,
        label: eventType.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase()),
        color: "bg-muted",
    }
}

function getAiActivityLabel(hours: AiActivityHours) {
    if (hours === 24) return "24 hours"
    if (hours === 168) return "7 days"
    return "30 days"
}

function getExportDates(exportRange: DateRangePreset, customRange: AuditDateRange) {
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

function AuditPageHeader() {
    return (
        <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="flex h-16 items-center px-6">
                <h1 className="text-2xl font-semibold">Audit Log</h1>
            </div>
        </div>
    )
}

function AuditExportCard({
    exportRange,
    onExportRangeChange,
    customRange,
    onCustomRangeChange,
    exportFormat,
    onExportFormatChange,
    redactMode,
    onRedactModeChange,
    isDeveloper,
    acknowledgment,
    onAcknowledgmentChange,
    isCreatingExport,
    visibleExportJobs,
    hasPendingExports,
    onExport,
    onDownload,
}: {
    exportRange: DateRangePreset
    onExportRangeChange: (value: DateRangePreset) => void
    customRange: AuditDateRange
    onCustomRangeChange: (value: AuditDateRange) => void
    exportFormat: ExportFormat
    onExportFormatChange: (value: ExportFormat) => void
    redactMode: RedactMode
    onRedactModeChange: (value: RedactMode) => void
    isDeveloper: boolean
    acknowledgment: string
    onAcknowledgmentChange: (value: string) => void
    isCreatingExport: boolean
    visibleExportJobs: AuditExportJob[]
    hasPendingExports: boolean
    onExport: () => void
    onDownload: (url: string) => void
}) {
    return (
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
                            onPresetChange={onExportRangeChange}
                            customRange={customRange}
                            onCustomRangeChange={onCustomRangeChange}
                            ariaLabel="Date range"
                        />
                    </div>
                    <div className="flex flex-col gap-2">
                        <Label htmlFor="export-format" className="text-sm text-muted-foreground">
                            Format
                        </Label>
                        <Select
                            value={exportFormat}
                            onValueChange={(value) => {
                                if (isExportFormat(value)) {
                                    onExportFormatChange(value)
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
                        <Label htmlFor="export-redaction" className="text-sm text-muted-foreground">
                            Redaction
                        </Label>
                        <Select
                            value={redactMode}
                            onValueChange={(value) => {
                                if (isRedactMode(value)) {
                                    onRedactModeChange(value)
                                }
                            }}
                            disabled={!isDeveloper}
                        >
                            <SelectTrigger id="export-redaction" className="w-[180px]">
                                <SelectValue>
                                    {(value: string | null) =>
                                        value === "full" ? "Full (Developer)" : "Redacted (default)"
                                    }
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
                            onClick={onExport}
                            disabled={
                                isCreatingExport || (redactMode === "full" && !acknowledgment.trim())
                            }
                        >
                            {isCreatingExport ? (
                                <Loader2Icon
                                    className="mr-2 size-4 animate-spin motion-reduce:animate-none"
                                    aria-hidden="true"
                                />
                            ) : (
                                <Upload className="mr-2 size-4" aria-hidden="true" />
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
                            onChange={(event) => onAcknowledgmentChange(event.target.value)}
                        />
                    </div>
                )}

                {redactMode === "redacted" && (
                    <div className="max-w-xl rounded-md border border-amber-200 bg-amber-50 p-3 dark:border-amber-900/50 dark:bg-amber-950/30">
                        <p className="text-sm text-amber-800 dark:text-amber-200">
                            <strong>⚠️ Best-Effort Redaction:</strong> Redacted exports apply
                            automated pattern matching for PHI (emails, phones, SSNs, etc.).
                            Free-text fields may contain PHI not detected by automated redaction.
                            Review exports before sharing.
                        </p>
                    </div>
                )}

                <AuditExportJobsList
                    visibleExportJobs={visibleExportJobs}
                    hasPendingExports={hasPendingExports}
                    onDownload={onDownload}
                />
            </CardContent>
        </Card>
    )
}

function AuditExportJobsList({
    visibleExportJobs,
    hasPendingExports,
    onDownload,
}: {
    visibleExportJobs: AuditExportJob[]
    hasPendingExports: boolean
    onDownload: (url: string) => void
}) {
    if (!visibleExportJobs.length) {
        return <div className="text-sm text-muted-foreground">No export jobs yet.</div>
    }

    return (
        <div className="rounded-lg border">
            <div className="flex items-center justify-between border-b px-4 py-2">
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
                                <StatusBadge variant="outline">{job.format.toUpperCase()}</StatusBadge>
                                <StatusBadge
                                    variant={job.redact_mode === "full" ? "destructive" : "secondary"}
                                >
                                    {job.redact_mode}
                                </StatusBadge>
                                <StatusBadge variant="outline" className="capitalize">
                                    {job.status}
                                </StatusBadge>
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
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => onDownload(job.download_url as string)}
                                >
                                    Download
                                </Button>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    )
}

function AuditActivityCard({
    eventTypeFilter,
    onEventTypeFilterChange,
    eventTypes,
    aiActivityHours,
    onAiActivityHoursChange,
    aiActivity,
    aiActivityLoading,
    auditEntries,
    auditTotal,
    isLoading,
    page,
    totalPages,
    onPageChange,
}: {
    eventTypeFilter: string
    onEventTypeFilterChange: (value: string) => void
    eventTypes: string[] | undefined
    aiActivityHours: AiActivityHours
    onAiActivityHoursChange: (value: AiActivityHours) => void
    aiActivity: AIAuditActivity | undefined
    aiActivityLoading: boolean
    auditEntries: AuditLogEntry[]
    auditTotal: number
    isLoading: boolean
    page: number
    totalPages: number
    onPageChange: (updater: (page: number) => number) => void
}) {
    return (
        <Card>
            <CardHeader>
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle>Activity Log</CardTitle>
                        <CardDescription>
                            Track all changes and actions in your organization
                        </CardDescription>
                    </div>
                    <div className="flex items-center gap-4">
                        <Select
                            value={eventTypeFilter}
                            onValueChange={(value) => onEventTypeFilterChange(value ?? "all")}
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
                <AuditAiActivityPanel
                    aiActivityHours={aiActivityHours}
                    onAiActivityHoursChange={onAiActivityHoursChange}
                    aiActivity={aiActivity}
                    aiActivityLoading={aiActivityLoading}
                    onEventTypeFilterChange={onEventTypeFilterChange}
                />

                <AuditLogEntriesList entries={auditEntries} isLoading={isLoading} />

                <AuditPagination
                    page={page}
                    totalPages={totalPages}
                    auditTotal={auditTotal}
                    onPageChange={onPageChange}
                />
            </CardContent>
        </Card>
    )
}

function AuditAiActivityPanel({
    aiActivityHours,
    onAiActivityHoursChange,
    aiActivity,
    aiActivityLoading,
    onEventTypeFilterChange,
}: {
    aiActivityHours: AiActivityHours
    onAiActivityHoursChange: (value: AiActivityHours) => void
    aiActivity: AIAuditActivity | undefined
    aiActivityLoading: boolean
    onEventTypeFilterChange: (value: string) => void
}) {
    return (
        <div className="mb-6 rounded-lg border p-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <p className="text-sm font-semibold">AI Activity</p>
                    <p className="text-xs text-muted-foreground">
                        Last {getAiActivityLabel(aiActivityHours)}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Select
                        value={String(aiActivityHours)}
                        onValueChange={(value) => {
                            const parsed = Number(value)
                            if (isAiActivityHours(parsed)) {
                                onAiActivityHoursChange(parsed)
                            }
                        }}
                    >
                        <SelectTrigger className="h-8 w-[100px] text-xs">
                            <SelectValue>
                                {(value: string | null) => {
                                    const labels: Record<string, string> = {
                                        "24": "24 hours",
                                        "168": "7 days",
                                        "720": "30 days",
                                    }
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
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onEventTypeFilterChange("ai_action_approved")}
                    >
                        Filter AI Events
                    </Button>
                </div>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
                {Object.entries(AI_EVENT_LABELS).map(([key, meta]) => (
                    <div key={key} className="flex items-center gap-2 text-sm">
                        <meta.icon className={`size-4 ${meta.tone}`} />
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
                            <Loader2Icon
                                className="size-3.5 animate-spin motion-reduce:animate-none"
                                aria-hidden="true"
                            />
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
                                <Button unstyled
                                    type="button"
                                    key={entry.id}
                                    className="-m-1 flex w-full items-start gap-2 rounded p-1 text-left text-xs transition-colors hover:bg-muted/50"
                                    onClick={() => onEventTypeFilterChange(entry.event_type)}
                                >
                                    <meta.icon className={`mt-0.5 size-3.5 ${meta.tone}`} />
                                    <div className="flex-1">
                                        <div className="font-medium text-foreground">
                                            {meta.label}
                                        </div>
                                        <div className="text-[11px] text-muted-foreground">
                                            {formatRelativeTime(entry.created_at, "Unknown")}
                                        </div>
                                    </div>
                                </Button>
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
    )
}

function AuditLogEntriesList({
    entries,
    isLoading,
}: {
    entries: AuditLogEntry[]
    isLoading: boolean
}) {
    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2Icon
                    className="size-8 animate-spin text-muted-foreground motion-reduce:animate-none"
                    aria-hidden="true"
                />
            </div>
        )
    }

    if (entries.length === 0) {
        return (
            <div className="py-12 text-center text-muted-foreground">
                No audit log entries found
            </div>
        )
    }

    return (
        <div className="space-y-4">
            {entries.map((entry) => (
                <AuditLogEntryCard key={entry.id} entry={entry} />
            ))}
        </div>
    )
}

function AuditLogEntryCard({ entry }: { entry: AuditLogEntry }) {
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
    const detailsJson = entry.details ? JSON.stringify(entry.details) : ""

    return (
        <div className="flex items-start gap-4 rounded-lg border border-border p-4">
            <div
                className={`flex size-10 shrink-0 items-center justify-center rounded-lg ${config.color} text-white`}
            >
                <Icon className="size-5" aria-hidden="true" />
            </div>
            <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge variant="outline">{config.label}</StatusBadge>
                    {entry.target_type && (
                        <span className="text-sm text-muted-foreground">{entry.target_type}</span>
                    )}
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                    {aiSummary ? (
                        <span className="font-medium text-foreground">{aiSummary}</span>
                    ) : entry.actor_name ? (
                        <span className="font-medium text-foreground">{entry.actor_name}</span>
                    ) : (
                        <span className="italic">System</span>
                    )}
                    {detailsJson && (
                        <span className="ml-2">
                            {detailsJson.slice(0, 100)}
                            {detailsJson.length > 100 ? "…" : ""}
                        </span>
                    )}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                    {formatDateTime(entry.created_at, "Unknown")}
                    {entry.ip_address && <span className="ml-2">from {entry.ip_address}</span>}
                </p>
            </div>
        </div>
    )
}

function AuditPagination({
    page,
    totalPages,
    auditTotal,
    onPageChange,
}: {
    page: number
    totalPages: number
    auditTotal: number
    onPageChange: (updater: (page: number) => number) => void
}) {
    if (totalPages <= 1) return null

    return (
        <div className="flex items-center justify-between border-t border-border pt-4">
            <p className="text-sm text-muted-foreground">
                Page {page} of {totalPages} ({auditTotal} total entries)
            </p>
            <div className="flex items-center gap-2">
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onPageChange((currentPage) => Math.max(1, currentPage - 1))}
                    disabled={page <= 1}
                >
                    <ChevronLeft className="size-4" />
                    Previous
                </Button>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onPageChange((currentPage) => Math.min(totalPages, currentPage + 1))}
                    disabled={page >= totalPages}
                >
                    Next
                    <ChevronRight className="size-4" />
                </Button>
            </div>
        </div>
    )
}

export default function AuditLogPage() {
    const { user } = useAuth()
    const isDeveloper = user?.role === "developer"

    const [page, setPage] = useState(1)
    const [eventTypeFilter, setEventTypeFilter] = useState<string>("all")
    const perPage = 20
    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

    const [exportFormat, setExportFormat] = useState<ExportFormat>("csv")
    const [redactMode, setRedactMode] = useState<RedactMode>("redacted")
    const [exportRange, setExportRange] = useState<DateRangePreset>("month")
    const [customRange, setCustomRange] = useState<AuditDateRange>({
        from: undefined,
        to: undefined,
    })
    const [acknowledgment, setAcknowledgment] = useState("")
    const [aiActivityHours, setAiActivityHours] = useState<AiActivityHours>(24)

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

    const totalPages = auditData ? Math.ceil(auditData.total / perPage) : 0
    const auditEntries = auditData?.items ?? []
    const auditTotal = auditData?.total ?? 0

    const exportJobItems = exportJobs?.items ?? []
    const visibleExportJobs = isDeveloper
        ? exportJobItems
        : exportJobItems.filter((job) => job.redact_mode !== "full")
    const hasPendingExports = visibleExportJobs.some((job) =>
        ["pending", "processing"].includes(job.status)
    )

    useEffect(() => {
        if (!hasPendingExports) return
        const timer = setInterval(() => {
            void refetchExports()
        }, 8000)
        return () => clearInterval(timer)
    }, [hasPendingExports, refetchExports])

    const handleExport = async () => {
        const { start, end } = getExportDates(exportRange, customRange)
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

    return (
        <div className="flex min-h-screen flex-col">
            <AuditPageHeader />

            <div className="flex-1 p-6">
                <AuditExportCard
                    exportRange={exportRange}
                    onExportRangeChange={setExportRange}
                    customRange={customRange}
                    onCustomRangeChange={setCustomRange}
                    exportFormat={exportFormat}
                    onExportFormatChange={setExportFormat}
                    redactMode={redactMode}
                    onRedactModeChange={setRedactMode}
                    isDeveloper={isDeveloper}
                    acknowledgment={acknowledgment}
                    onAcknowledgmentChange={setAcknowledgment}
                    isCreatingExport={createExport.isPending}
                    visibleExportJobs={visibleExportJobs}
                    hasPendingExports={hasPendingExports}
                    onExport={handleExport}
                    onDownload={handleDownload}
                />

                <AuditActivityCard
                    eventTypeFilter={eventTypeFilter}
                    onEventTypeFilterChange={setEventTypeFilter}
                    eventTypes={eventTypes}
                    aiActivityHours={aiActivityHours}
                    onAiActivityHoursChange={setAiActivityHours}
                    aiActivity={aiActivity}
                    aiActivityLoading={aiActivityLoading}
                    auditEntries={auditEntries}
                    auditTotal={auditTotal}
                    isLoading={isLoading}
                    page={page}
                    totalPages={totalPages}
                    onPageChange={setPage}
                />
            </div>
        </div>
    )
}
