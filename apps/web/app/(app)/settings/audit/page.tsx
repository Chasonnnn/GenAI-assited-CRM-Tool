"use client"

import { useState } from "react"
import { format } from "date-fns"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { LoaderIcon, ChevronLeft, ChevronRight, FileText, User, Shield, Settings } from "lucide-react"
import { useAuditLogs, useEventTypes } from "@/lib/hooks/use-audit"

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
}

function getEventConfig(eventType: string) {
    return EVENT_CONFIG[eventType] || {
        icon: FileText,
        label: eventType.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()),
        color: "bg-muted"
    }
}

export default function AuditLogPage() {
    const [page, setPage] = useState(1)
    const [eventTypeFilter, setEventTypeFilter] = useState<string>("all")
    const perPage = 20

    const filters = {
        page,
        per_page: perPage,
        ...(eventTypeFilter !== "all" && { event_type: eventTypeFilter }),
    }

    const { data: auditData, isLoading } = useAuditLogs(filters)
    const { data: eventTypes } = useEventTypes()

    const totalPages = auditData ? Math.ceil(auditData.total / perPage) : 0

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
                <Card>
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <div>
                                <CardTitle>Activity Log</CardTitle>
                                <CardDescription>Track all changes and actions in your organization</CardDescription>
                            </div>
                            <div className="flex items-center gap-4">
                                {/* Event Type Filter */}
                                <Select value={eventTypeFilter} onValueChange={setEventTypeFilter}>
                                    <SelectTrigger className="w-[200px]">
                                        <SelectValue placeholder="Filter by event type" />
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
                        {isLoading ? (
                            <div className="py-12 flex items-center justify-center">
                                <LoaderIcon className="size-8 animate-spin text-muted-foreground" />
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
                                                    {entry.actor_name ? (
                                                        <span className="font-medium text-foreground">{entry.actor_name}</span>
                                                    ) : (
                                                        <span className="italic">System</span>
                                                    )}
                                                    {entry.details && Object.keys(entry.details).length > 0 && (
                                                        <span className="ml-2">
                                                            {JSON.stringify(entry.details).slice(0, 100)}
                                                            {JSON.stringify(entry.details).length > 100 ? "..." : ""}
                                                        </span>
                                                    )}
                                                </p>
                                                <p className="text-xs text-muted-foreground mt-1">
                                                    {format(new Date(entry.created_at), "MMM d, yyyy 'at' h:mm a")}
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
