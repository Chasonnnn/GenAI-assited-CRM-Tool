"use client"

import { useState } from "react"
import { Loader2Icon } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import Link from "@/components/app-link"
import type { Appointment, AppointmentScheduling } from "@/lib/api/appointments"
import { createSchedulingRequestId } from "@/lib/api/appointments"
import { formatSchedulingDate, formatSchedulingTime, schedulingTimezoneLabel } from "@/lib/scheduling-time"
import {
    useResolveAppointmentGoogleConflict,
    useRetryAppointmentGoogleSync,
} from "@/lib/hooks/use-appointments"

type Interval = { start?: unknown; end?: unknown }

function snapshotStatus(value: unknown) {
    if (!value || typeof value !== "object") return null
    return (value as Record<string, unknown>).status === "cancelled" ? "cancelled" : null
}

function intervalLabel(value: unknown, timezone: string) {
    if (!value || typeof value !== "object") return null
    const { start, end } = value as Interval
    if (typeof start !== "string" || typeof end !== "string") return null
    const startDate = new Date(start)
    const endDate = new Date(end)
    if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) return null
    return `${formatSchedulingDate(start, timezone)} · ${formatSchedulingTime(start, timezone)}–${formatSchedulingTime(end, timezone)} ${schedulingTimezoneLabel(timezone)}`
}

function conflictEtag(conflict: Record<string, unknown> | null) {
    if (!conflict) return null
    for (const value of [conflict.expected_etag, conflict.etag, (conflict.remote as Record<string, unknown> | undefined)?.etag]) {
        if (typeof value === "string" && value) return value
    }
    return null
}

export function schedulingCanReschedule(scheduling: AppointmentScheduling | null | undefined) {
    return scheduling ? scheduling.capabilities.can_reschedule : true
}

export function schedulingCanCancel(scheduling: AppointmentScheduling | null | undefined) {
    return scheduling ? scheduling.capabilities.can_cancel : true
}

export function SchedulingSyncBadge({ scheduling }: { scheduling: AppointmentScheduling | null | undefined }) {
    const state = scheduling?.google_sync.state
    if (!state) return null
    if (state === "completed") return <Badge variant="outline" className="text-muted-foreground">Google Calendar synced</Badge>
    const label = state === "pending" ? "Google updating" : state === "failed" ? "Google update failed" : state === "conflict" ? "Google conflict" : "Google setup needed"
    const className = state === "pending"
        ? "text-muted-foreground"
        : state === "conflict"
            ? "border-amber-500/40 text-amber-800 dark:text-amber-200"
            : "border-destructive/30 text-destructive"
    return <Badge variant="outline" className={className}>
        {state === "pending" ? <Loader2Icon aria-hidden="true" className="animate-spin motion-reduce:animate-none" /> : null}
        {label}
    </Badge>
}

export function SchedulingSyncState({
    appointment,
    onUpdated,
}: {
    appointment: { id: string; client_timezone?: string; scheduling?: AppointmentScheduling | null }
    onUpdated?: (appointment: Appointment) => void
}) {
    const scheduling = appointment.scheduling
    const retry = useRetryAppointmentGoogleSync()
    const resolve = useResolveAppointmentGoogleConflict()
    const sync = scheduling?.google_sync
    const [selection, setSelection] = useState<{ key: string; resolution: "crm" | "google" } | null>(null)
    const timezone = appointment.client_timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone
    const conflictKey = `${appointment.id}:${scheduling?.revision ?? ""}:${conflictEtag(scheduling?.google_sync.conflict ?? null) ?? ""}`
    const selectedResolution = selection?.key === conflictKey ? selection.resolution : null
    if (!scheduling || !sync?.state) return null

    const pending = retry.isPending || resolve.isPending
    const complete = (updated: Appointment) => onUpdated?.(updated)
    const local = intervalLabel(sync.conflict?.local, timezone)
    const remote = intervalLabel(sync.conflict?.remote, timezone)
    const etag = conflictEtag(sync.conflict)

    if (sync.state === "completed") {
        return <p role="status" className="text-sm text-muted-foreground">Google Calendar synced</p>
    }
    if (sync.state === "pending") {
        return <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2Icon className="size-3 animate-spin" />Updating Google Calendar…</p>
    }
    if (sync.state === "unlinked") {
        return <div className="flex flex-wrap items-center gap-2">
            <p role="alert" className="text-sm text-destructive">Google Calendar needs setup.</p>
            <Button size="sm" variant="outline" render={<Link href="/settings/integrations" />}>Calendar settings</Button>
            {retry.isError ? <p role="alert" className="text-sm text-destructive">Google Calendar update could not be queued.</p> : null}
            {scheduling.capabilities.can_retry_google_sync ? <Button
                size="sm"
                variant="outline"
                disabled={pending}
                onClick={() => retry.mutate({
                    appointmentId: appointment.id,
                    expectedRevision: scheduling.revision,
                    requestId: createSchedulingRequestId(),
                }, { onSuccess: complete })}
            >
                {retry.isPending ? <Loader2Icon className="mr-2 size-3 animate-spin" /> : null}
                Retry Google update
            </Button> : null}
        </div>
    }
    if (sync.state === "failed") {
        return <div className="flex flex-wrap items-center gap-2">
            <p role="alert" className="text-sm text-destructive">Google Calendar update failed.</p>
            {retry.isError ? <p role="alert" className="text-sm text-destructive">Google Calendar update could not be queued.</p> : null}
            {scheduling.capabilities.can_retry_google_sync ? <Button
                size="sm"
                variant="outline"
                disabled={pending}
                onClick={() => retry.mutate({
                    appointmentId: appointment.id,
                    expectedRevision: scheduling.revision,
                    requestId: createSchedulingRequestId(),
                }, { onSuccess: complete })}
            >
                {retry.isPending ? <Loader2Icon className="mr-2 size-3 animate-spin" /> : null}
                Retry Google update
            </Button> : null}
        </div>
    }
    if (sync.state !== "conflict") return null

    const localCancelled = snapshotStatus(sync.conflict?.local) === "cancelled"
    const remoteCancelled = snapshotStatus(sync.conflict?.remote) === "cancelled"
    const localLabel = localCancelled ? "Cancelled" : local ?? "Current CRM schedule"
    const remoteLabel = remoteCancelled ? "Cancelled" : remote ?? "Google event is unavailable"

    return <div className="space-y-3 rounded-md border border-amber-500/40 bg-amber-50/40 p-3 dark:bg-amber-950/10">
        <p role="alert" className="text-sm text-amber-800 dark:text-amber-200">Google Calendar changed. Choose which schedule to keep.</p>
        <RadioGroup
            value={selectedResolution ?? ""}
            onValueChange={(resolution) => setSelection({ key: conflictKey, resolution: resolution as "crm" | "google" })}
            className="gap-2 text-sm"
        >
            <Label className="flex cursor-pointer items-start gap-2 rounded-md border p-2">
                <RadioGroupItem value="crm" disabled={!scheduling.capabilities.can_resolve_google_conflict || !etag || pending} />
                <span><span className="font-medium">CRM schedule</span><span className="block text-muted-foreground">{localLabel}</span></span>
            </Label>
            <Label className="flex cursor-pointer items-start gap-2 rounded-md border p-2">
                <RadioGroupItem value="google" disabled={!scheduling.capabilities.can_resolve_google_conflict || !etag || pending} />
                <span><span className="font-medium">Google Calendar</span><span className="block text-muted-foreground">{remoteLabel}</span></span>
            </Label>
        </RadioGroup>
        {resolve.isError ? <p role="alert" className="text-sm text-destructive">Selected schedule could not be applied.</p> : null}
        {scheduling.capabilities.can_resolve_google_conflict && etag ? <Button size="sm" disabled={!selectedResolution || pending} onClick={() => selectedResolution && resolve.mutate({ appointmentId: appointment.id, expectedRevision: scheduling.revision, expectedEtag: etag, resolution: selectedResolution, requestId: createSchedulingRequestId() }, { onSuccess: complete })}>{resolve.isPending ? <Loader2Icon className="mr-2 size-3 animate-spin" /> : null}Apply selected schedule</Button> : <Badge variant="outline">Manual review required</Badge>}
    </div>
}
