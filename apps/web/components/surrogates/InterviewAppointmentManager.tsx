"use client"

import { useEffect, useState } from "react"
import { ApiError } from "@/lib/api"
import type { InterviewAppointment, AppointmentStage } from "@/lib/api/interview-appointment"
import { createSchedulingRequestId } from "@/lib/api/appointments"
import { SchedulingSyncState, schedulingCanCancel, schedulingCanReschedule } from "@/components/appointments/SchedulingSyncState"
import {
    useInterviewAppointment,
    useInterviewSlots,
    useManageInterviewAppointment,
    useRetryInterviewAppointmentGoogleSync,
} from "@/lib/hooks/use-interview-appointment"
import { readableForeground } from "@/lib/stage-colors"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { CalendarClockIcon, Loader2Icon } from "lucide-react"
import { SchedulingTimePicker } from "@/components/appointments/SchedulingTimePicker"
import { formatSchedulingDate, formatSchedulingTime, localDateTimeToIso as parseLocalDateTime, schedulingDateKey, schedulingTimezoneLabel } from "@/lib/scheduling-time"

export type AppointmentBadgeStatus = "Upcoming" | "Ongoing" | "Cancelled" | "Past"

export function appointmentBadgeStatus(appointment: InterviewAppointment, now = new Date()): AppointmentBadgeStatus {
    if (appointment.status.toLowerCase() === "cancelled" || appointment.status.toLowerCase() === "canceled") return "Cancelled"
    if (["completed", "no_show", "expired"].includes(appointment.status) || appointment.meeting_ended_at) return "Past"
    if (appointment.meeting_started_at && !appointment.meeting_ended_at) return "Ongoing"
    if (new Date(appointment.scheduled_end).getTime() <= now.getTime()) return "Past"
    if (new Date(appointment.scheduled_start).getTime() <= now.getTime()) return "Ongoing"
    return "Upcoming"
}

const badgeStyles: Record<AppointmentBadgeStatus, React.CSSProperties> = {
    Upcoming: { backgroundColor: "#E0F2FE", color: "#0369A1", borderColor: "#BAE6FD" },
    Ongoing: { backgroundColor: "#DCFCE7", color: "#166534", borderColor: "#BBF7D0" },
    Cancelled: { backgroundColor: "#FEE2E2", color: "#B91C1C", borderColor: "#FECACA" },
    Past: { backgroundColor: "#F3F4F6", color: "#4B5563", borderColor: "#D1D5DB" },
}

export function AppointmentStatusBadge({ appointment }: { appointment: InterviewAppointment }) {
    const [now, setNow] = useState(() => new Date())
    useEffect(() => {
        const timer = setInterval(() => setNow(new Date()), 30_000)
        return () => clearInterval(timer)
    }, [])
    const status = appointmentBadgeStatus(appointment, now)
    return <Badge variant="outline" style={badgeStyles[status]} aria-label={`Appointment: ${status}`}><CalendarClockIcon className="size-3" />{status}</Badge>
}

function StageBadge({ stage, className }: { stage: AppointmentStage; className?: string }) {
    return <Badge className={className} style={{ backgroundColor: stage.color, color: readableForeground(stage.color) }}>{stage.label}</Badge>
}

function formatAppointment(appointment: InterviewAppointment) {
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
    return `${formatSchedulingDate(appointment.scheduled_start, timezone)} · ${formatSchedulingTime(appointment.scheduled_start, timezone)} ${schedulingTimezoneLabel(timezone)}`
}

function localInputValue(iso: string | undefined) {
    const date = iso ? new Date(iso) : new Date(Date.now() + 24 * 60 * 60 * 1000)
    const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
    return shifted.toISOString().slice(0, 16)
}

export function localDateTimeToIso(value: string): string | null {
    return parseLocalDateTime(value)
}

type View = "manage" | "book" | "cancel"

export function InterviewAppointmentManager({
    surrogateId,
    stageId,
    compact = false,
    triggerOnly = false,
    hideTrigger = false,
    renderDialog = true,
    open: controlledOpen,
    onOpenChange,
    onManage,
}: {
    surrogateId: string
    stageId: string
    compact?: boolean
    triggerOnly?: boolean
    hideTrigger?: boolean
    renderDialog?: boolean
    open?: boolean
    onOpenChange?: (open: boolean) => void
    onManage?: () => void
}) {
    const query = useInterviewAppointment(surrogateId)
    const mutation = useManageInterviewAppointment(surrogateId)
    const retryGoogleSync = useRetryInterviewAppointmentGoogleSync(surrogateId)
    const [uncontrolledOpen, setUncontrolledOpen] = useState(false)
    const [form, setForm] = useState({ view: "manage" as View, date: "", selectedStart: null as string | null, dateTime: "", cancelChoice: "move", overrideAvailability: false, overrideReason: "", validation: null as string | null })
    const { view, date, selectedStart, dateTime, cancelChoice, overrideAvailability, overrideReason, validation } = form
    const updateForm = (next: Partial<typeof form>) => setForm((current) => ({ ...current, ...next }))
    const state = query.data
    const appointment = state?.appointment ?? null
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
    const slotsQuery = useInterviewSlots(surrogateId, date, timezone, view === "book" && Boolean(state?.can_manage))
    const active = Boolean(appointment && ["pending", "confirmed"].includes(appointment.status))
    const externalSyncStatus = appointment?.scheduling?.google_sync.state ?? state?.external_sync_status
    const legacySyncUnresolved = !appointment?.scheduling && ["pending", "failed", "conflict", "unlinked"].includes(externalSyncStatus ?? "")
    const canStartNewAppointment = !active
        && state?.can_manage === true
        && Boolean(state?.scheduled_stage)
        && !legacySyncUnresolved
        && (!appointment?.scheduling || appointment.scheduling.google_sync.state === "completed")
    const canOpenBooking = active
        ? state?.can_manage === true && !legacySyncUnresolved && schedulingCanReschedule(appointment?.scheduling)
        : canStartNewAppointment
    const open = controlledOpen ?? uncontrolledOpen
    const setOpen = onOpenChange ?? setUncontrolledOpen

    const resetForm = () => setForm({ view: "manage", validation: null, cancelChoice: "move", overrideAvailability: false, overrideReason: "", date: "", selectedStart: null, dateTime: "" })
    const setDialogOpen = (next: boolean) => {
        if (mutation.isPending) return
        if (!next) resetForm()
        setOpen(next)
    }
    const openManager = () => {
        resetForm()
        if (onManage) onManage()
        else setOpen(true)
    }

    if (query.isLoading) return hideTrigger ? null : triggerOnly
        ? <Button size="sm" variant="outline" className="h-7 text-xs" disabled aria-label="Loading interview appointment"><Loader2Icon className="size-3 animate-spin" />Manage</Button>
        : <div className="flex h-10 items-center gap-2 text-sm text-muted-foreground"><Loader2Icon className="size-4 animate-spin" /> Loading appointment</div>
    if (query.isError) return hideTrigger ? null : triggerOnly
        ? <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => void query.refetch()}>Retry appointment</Button>
        : <div className="flex items-center justify-between gap-3 rounded-lg border p-3 text-sm"><span>Appointment unavailable</span><Button size="sm" variant="outline" onClick={() => void query.refetch()}>Retry</Button></div>
    if (!state) return null
    if (stageId !== state.scheduled_stage?.id && stageId !== state.reschedule_stage?.id) return null

    const submit = async (action: "schedule" | "reschedule" | "cancel", moveStage: boolean) => {
        if (legacySyncUnresolved) return
        const scheduledStart = action === "cancel" ? null : overrideAvailability ? localDateTimeToIso(dateTime) : selectedStart
        if (action !== "cancel" && !scheduledStart) { updateForm({ validation: "Choose a valid date and time." }); return }
        if (action !== "cancel" && overrideAvailability && !overrideReason.trim()) { updateForm({ validation: "Enter a reason for the availability override." }); return }
        if (scheduledStart && new Date(scheduledStart).getTime() <= Date.now()) { updateForm({ validation: "Choose a future date and time." }); return }
        if (action === "reschedule" && scheduledStart && appointment && new Date(scheduledStart).getTime() === new Date(appointment.scheduled_start).getTime()) { updateForm({ validation: "Choose a different appointment time." }); return }
        updateForm({ validation: null })
        try {
            const nextState = await mutation.mutateAsync({
                action, ...(scheduledStart ? { scheduled_start: scheduledStart } : {}), move_stage: moveStage,
                expected_stage_id: stageId, expected_appointment_id: appointment?.id ?? null,
                expected_scheduled_start: appointment?.scheduled_start ?? null,
                ...(appointment?.scheduling ? { expected_revision: appointment.scheduling.revision, request_id: createSchedulingRequestId() } : {}),
                ...(action !== "cancel" && overrideAvailability ? { override_availability: true, override_reason: overrideReason.trim() } : {}),
            })
            if (nextState.external_sync_status === "pending" || nextState.external_sync_status === "failed") {
                updateForm({ view: "manage" })
            } else {
                setDialogOpen(false)
            }
        } catch (error) {
            if (error instanceof ApiError && error.status === 409) void slotsQuery.refetch()
            updateForm({ validation: error instanceof ApiError && error.status === 409
                ? error.message
                : error instanceof ApiError && error.status === 403 ? "You no longer have permission to manage this appointment."
                : error instanceof Error ? error.message : "Unable to save the appointment." })
        }
    }

    const retrySync = async () => {
        if (!appointment) return
        updateForm({ validation: null })
        try {
            await retryGoogleSync.mutateAsync(appointment.id)
        } catch (error) {
            updateForm({ validation: error instanceof ApiError && error.status === 409
                ? error.message
                : error instanceof Error ? error.message : "Unable to retry the Google Calendar update." })
        }
    }

    const row = <div className="flex min-w-0 items-center gap-2">
        {appointment ? <AppointmentStatusBadge appointment={appointment} /> : null}
        <span className="truncate text-sm text-muted-foreground">{active && appointment ? formatAppointment(appointment) : "No active appointment"}</span>
    </div>

    return <>
        {!hideTrigger && (triggerOnly ? <Button size="sm" variant="outline" className="h-7 text-xs" onClick={openManager} disabled={!state.can_manage}>Manage</Button> : <div className={compact ? "flex items-center justify-between gap-3 rounded-lg border px-3 py-2" : "flex items-center justify-between gap-3"}>
            <div className="min-w-0"><span className="text-sm font-medium">Interview appointment</span>{row}</div>
            <Button size="sm" variant="outline" onClick={openManager} disabled={!state.can_manage}>Manage</Button>
        </div>)}
        {renderDialog ? <Dialog open={open} onOpenChange={setDialogOpen}>
            <DialogContent className={`flex max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-2xl p-0 ${view === "book" ? "sm:max-w-2xl" : "sm:max-w-lg"}`}>
                <DialogHeader className="shrink-0 border-b px-5 py-4 pr-12"><DialogTitle>{view === "manage" ? "Manage appointment" : view === "cancel" ? "Cancel appointment?" : active ? "Reschedule interview" : "Schedule interview"}</DialogTitle></DialogHeader>
                <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
                {view === "manage" ? <div className="space-y-5">
                    {row}
                    {appointment?.scheduling ? <SchedulingSyncState appointment={appointment} onUpdated={() => void query.refetch()} /> : <>
                        {externalSyncStatus === "pending" ? <p role="status" className="text-sm text-muted-foreground">Interview saved. Updating Google Calendar…</p> : null}
                        {externalSyncStatus === "completed" ? <p role="status" className="text-sm text-muted-foreground">Google Calendar is up to date.</p> : null}
                        {externalSyncStatus === "failed" ? <p role="alert" className="text-sm text-destructive">Interview saved, but Google Calendar could not be updated. Retry the update.</p> : null}
                        {externalSyncStatus === "conflict" ? <p role="alert" className="text-sm text-destructive">Google Calendar changed. This appointment needs manual review before further CRM changes.</p> : null}
                        {externalSyncStatus === "unlinked" ? <p role="alert" className="text-sm text-destructive">Google Calendar event ownership could not be verified. This appointment needs manual review before further CRM changes.</p> : null}
                    </>}
                    {!state.can_manage ? <p className="text-sm text-muted-foreground">You do not have permission to manage this appointment.</p> : null}
                </div> : null}
                {view === "book" ? <div className="space-y-4">
                    <SchedulingTimePicker
                        idPrefix="interview-appointment"
                        date={date}
                        onDateChange={(next) => updateForm({ date: next, selectedStart: null })}
                        timezone={timezone}
                        slots={slotsQuery.data?.slots}
                        selectedStart={selectedStart}
                        onSelectStart={(start) => updateForm({ selectedStart: start })}
                        loading={slotsQuery.isLoading || slotsQuery.isFetching}
                        error={slotsQuery.isError ? "Available times could not be loaded." : undefined}
                        onRetry={() => void slotsQuery.refetch()}
                        override={{ enabled: overrideAvailability, onEnabledChange: (enabled) => updateForm({ overrideAvailability: enabled }), dateTime, onDateTimeChange: (next) => updateForm({ dateTime: next }), reason: overrideReason, onReasonChange: (next) => updateForm({ overrideReason: next }) }}
                    />
                    {!state.scheduled_stage ? <p role="alert" className="text-sm text-destructive">Interview Scheduled is not configured. Ask an administrator to finish the rollout.</p> : null}
                </div> : null}
                {view === "cancel" ? <div className="space-y-4">
                    {appointment ? <p className="font-medium">{formatAppointment(appointment)}</p> : null}
                    {state.reschedule_stage && stageId !== state.reschedule_stage.id ? <RadioGroup value={cancelChoice} onValueChange={(value) => updateForm({ cancelChoice: value })} aria-label="After cancellation">
                        <Label className="flex items-center gap-3 rounded-lg border p-3"><RadioGroupItem value="move" />Move to <StageBadge stage={state.reschedule_stage} /></Label>
                        <Label className="flex items-center gap-3 rounded-lg border p-3"><RadioGroupItem value="keep" />Keep current stage</Label>
                    </RadioGroup> : null}
                </div> : null}
                {validation ? <p role="alert" className="text-sm text-destructive">{validation}</p> : null}
                </div>
                <DialogFooter className={view === "manage" ? "shrink-0 border-t px-5 py-4 flex-row sm:justify-start" : "shrink-0 border-t px-5 py-4"}>
                    {view === "manage" ? <>
                        <Button className="h-auto min-h-9 min-w-0 shrink whitespace-normal" disabled={!canOpenBooking} onClick={() => updateForm({ view: "book", date: schedulingDateKey(active && appointment ? appointment.scheduled_start : new Date().toISOString(), timezone), selectedStart: null, dateTime: localInputValue(active ? appointment?.scheduled_start : undefined), overrideAvailability: false, overrideReason: "" })}>{active ? "Reschedule" : "Schedule appointment"}</Button>
                        {active ? <Button className="h-auto min-h-9 min-w-0 shrink whitespace-normal" variant="outline" disabled={!state.can_manage || legacySyncUnresolved || !schedulingCanCancel(appointment?.scheduling)} onClick={() => updateForm({ view: "cancel" })}>Cancel appointment</Button> : null}
                        {!appointment?.scheduling && externalSyncStatus === "failed" && appointment ? <Button variant="outline" disabled={!state.can_manage || retryGoogleSync.isPending} onClick={() => void retrySync()}>{retryGoogleSync.isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}Retry Google update</Button> : null}
                        <Button className="ml-auto" variant="outline" onClick={() => setDialogOpen(false)}>Done</Button>
                    </> : <Button variant="outline" disabled={mutation.isPending} onClick={() => updateForm({ view: "manage" })}>Back</Button>}
                    {view === "book" ? <Button disabled={mutation.isPending || !canOpenBooking || (overrideAvailability && !overrideReason.trim())} onClick={() => void submit(active ? "reschedule" : "schedule", stageId === state.reschedule_stage?.id)}>{mutation.isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}{stageId === state.reschedule_stage?.id ? active ? "Reschedule & update stage" : "Schedule & update stage" : active ? "Reschedule" : "Schedule"}</Button> : null}
                    {view === "cancel" ? <Button variant="destructive" disabled={mutation.isPending || !state.can_manage || legacySyncUnresolved || !schedulingCanCancel(appointment?.scheduling)} onClick={() => void submit("cancel", Boolean(state.reschedule_stage) && cancelChoice === "move" && stageId !== state.reschedule_stage?.id)}>Cancel appointment</Button> : null}
                </DialogFooter>
            </DialogContent>
        </Dialog> : null}
    </>
}

export function AppointmentHeaderBadge({ surrogateId }: { surrogateId: string }) {
    const { data } = useInterviewAppointment(surrogateId)
    return data?.appointment ? <AppointmentStatusBadge appointment={data.appointment} /> : null
}
