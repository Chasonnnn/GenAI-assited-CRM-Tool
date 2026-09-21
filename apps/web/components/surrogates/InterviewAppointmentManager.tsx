"use client"

import { useEffect, useState } from "react"
import { ApiError } from "@/lib/api"
import type { InterviewAppointment, AppointmentStage } from "@/lib/api/interview-appointment"
import {
    useInterviewAppointment,
    useManageInterviewAppointment,
    useRetryInterviewAppointmentGoogleSync,
} from "@/lib/hooks/use-interview-appointment"
import { readableForeground } from "@/lib/stage-colors"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { CalendarClockIcon, Loader2Icon } from "lucide-react"

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
    return new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium", timeStyle: "short",
    }).format(new Date(appointment.scheduled_start))
}

function localInputValue(iso: string | undefined) {
    const date = iso ? new Date(iso) : new Date(Date.now() + 24 * 60 * 60 * 1000)
    const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
    return shifted.toISOString().slice(0, 16)
}

export function localDateTimeToIso(value: string): string | null {
    if (!value) return null
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime()) || localInputValue(parsed.toISOString()) !== value) return null
    return parsed.toISOString()
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
    const [view, setView] = useState<View>("manage")
    const [dateTime, setDateTime] = useState("")
    const [cancelChoice, setCancelChoice] = useState("move")
    const [validation, setValidation] = useState<string | null>(null)
    const state = query.data
    const appointment = state?.appointment ?? null
    const active = Boolean(appointment && ["pending", "confirmed"].includes(appointment.status))
    const externalSyncStatus = state?.external_sync_status
    const syncUnresolved = ["pending", "failed", "conflict", "unlinked"].includes(externalSyncStatus ?? "")
    const open = controlledOpen ?? uncontrolledOpen
    const setOpen = onOpenChange ?? setUncontrolledOpen

    useEffect(() => {
        if (open) {
            setView("manage")
            setValidation(null)
            setCancelChoice("move")
            setDateTime(localInputValue(active ? appointment?.scheduled_start : undefined))
        }
    }, [open, active, appointment?.scheduled_start])

    if (query.isLoading) return hideTrigger ? null : triggerOnly
        ? <Button size="sm" variant="outline" className="h-7 text-xs" disabled aria-label="Loading interview appointment"><Loader2Icon className="size-3 animate-spin" />Manage</Button>
        : <div className="flex h-10 items-center gap-2 text-sm text-muted-foreground"><Loader2Icon className="size-4 animate-spin" /> Loading appointment</div>
    if (query.isError) return hideTrigger ? null : triggerOnly
        ? <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => void query.refetch()}>Retry appointment</Button>
        : <div className="flex items-center justify-between gap-3 rounded-lg border p-3 text-sm"><span>Appointment unavailable</span><Button size="sm" variant="outline" onClick={() => void query.refetch()}>Retry</Button></div>
    if (!state) return null
    if (stageId !== state.scheduled_stage?.id && stageId !== state.reschedule_stage?.id) return null

    const submit = async (action: "schedule" | "reschedule" | "cancel", moveStage: boolean) => {
        if (syncUnresolved) return
        const scheduledStart = action === "cancel" ? null : localDateTimeToIso(dateTime)
        if (action !== "cancel" && !scheduledStart) { setValidation("Choose a valid date and time."); return }
        if (scheduledStart && new Date(scheduledStart).getTime() <= Date.now()) { setValidation("Choose a future date and time."); return }
        if (action === "reschedule" && scheduledStart && appointment && new Date(scheduledStart).getTime() === new Date(appointment.scheduled_start).getTime()) { setValidation("Choose a different appointment time."); return }
        setValidation(null)
        try {
            const nextState = await mutation.mutateAsync({
                action, ...(scheduledStart ? { scheduled_start: scheduledStart } : {}), move_stage: moveStage,
                expected_stage_id: stageId, expected_appointment_id: appointment?.id ?? null,
                expected_scheduled_start: appointment?.scheduled_start ?? null,
            })
            if (nextState.external_sync_status === "pending" || nextState.external_sync_status === "failed") {
                setView("manage")
            } else {
                setOpen(false)
            }
        } catch (error) {
            setValidation(error instanceof ApiError && error.status === 409
                ? error.message
                : error instanceof ApiError && error.status === 403 ? "You no longer have permission to manage this appointment."
                : error instanceof Error ? error.message : "Unable to save the appointment.")
        }
    }

    const retrySync = async () => {
        if (!appointment) return
        setValidation(null)
        try {
            await retryGoogleSync.mutateAsync(appointment.id)
        } catch (error) {
            setValidation(error instanceof ApiError && error.status === 409
                ? error.message
                : error instanceof Error ? error.message : "Unable to retry the Google Calendar update.")
        }
    }

    const row = <div className="flex min-w-0 items-center gap-2">
        {appointment ? <AppointmentStatusBadge appointment={appointment} /> : null}
        <span className="truncate text-sm text-muted-foreground">{active && appointment ? formatAppointment(appointment) : "No active appointment"}</span>
    </div>

    return <>
        {!hideTrigger && (triggerOnly ? <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => onManage ? onManage() : setOpen(true)} disabled={!state.can_manage}>Manage</Button> : <div className={compact ? "flex items-center justify-between gap-3 rounded-lg border px-3 py-2" : "flex items-center justify-between gap-3"}>
            <div className="min-w-0"><span className="text-sm font-medium">Interview appointment</span>{row}</div>
            <Button size="sm" variant="outline" onClick={() => onManage ? onManage() : setOpen(true)} disabled={!state.can_manage}>Manage</Button>
        </div>)}
        {renderDialog ? <Dialog open={open} onOpenChange={(next) => !mutation.isPending && setOpen(next)}>
            <DialogContent>
                <DialogHeader><DialogTitle>{view === "manage" ? "Manage appointment" : view === "cancel" ? "Cancel appointment?" : active ? "Reschedule interview" : "Schedule interview"}</DialogTitle></DialogHeader>
                {view === "manage" ? <div className="space-y-5">
                    {row}
                    {externalSyncStatus === "pending" ? <p role="status" className="text-sm text-muted-foreground">Interview saved. Updating Google Calendar…</p> : null}
                    {externalSyncStatus === "completed" ? <p role="status" className="text-sm text-muted-foreground">Google Calendar is up to date.</p> : null}
                    {externalSyncStatus === "failed" ? <p role="alert" className="text-sm text-destructive">Interview saved, but Google Calendar could not be updated. Retry the update.</p> : null}
                    {externalSyncStatus === "conflict" ? <p role="alert" className="text-sm text-destructive">Google Calendar changed. This appointment needs manual review before further CRM changes.</p> : null}
                    {externalSyncStatus === "unlinked" ? <p role="alert" className="text-sm text-destructive">Google Calendar event ownership could not be verified. This appointment needs manual review before further CRM changes.</p> : null}
                    {!state.can_manage ? <p className="text-sm text-muted-foreground">You do not have permission to manage this appointment.</p> : null}
                </div> : null}
                {view === "book" ? <div className="space-y-4">
                    <div className="space-y-2"><Label htmlFor="appointment-at">Interview date and time</Label><Input id="appointment-at" type="datetime-local" value={dateTime} onChange={(event) => setDateTime(event.target.value)} /></div>
                    <p className="text-xs text-muted-foreground">Your timezone: {Intl.DateTimeFormat().resolvedOptions().timeZone}</p>
                    {state.scheduled_stage && state.reschedule_stage && stageId === state.reschedule_stage.id ? <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 rounded-lg border bg-muted/30 p-3"><StageBadge stage={state.reschedule_stage} className="w-full min-w-0 whitespace-normal text-center" /><span aria-hidden>→</span><StageBadge stage={state.scheduled_stage} className="w-full min-w-0 whitespace-normal text-center" /></div> : null}
                    {state.scheduled_stage ? <p className="text-sm text-muted-foreground">{stageId === state.reschedule_stage?.id ? `Stage will change to ${state.scheduled_stage.label} when you confirm.` : "Stage will stay unchanged."}</p> : null}
                    {!state.scheduled_stage ? <p role="alert" className="text-sm text-destructive">Interview Scheduled is not configured. Ask an administrator to finish the rollout.</p> : null}
                </div> : null}
                {view === "cancel" ? <div className="space-y-4">
                    {appointment ? <p className="font-medium">{formatAppointment(appointment)}</p> : null}
                    {state.reschedule_stage && stageId !== state.reschedule_stage.id ? <RadioGroup value={cancelChoice} onValueChange={setCancelChoice} aria-label="After cancellation">
                        <Label className="flex items-center gap-3 rounded-lg border p-3"><RadioGroupItem value="move" />Move to <StageBadge stage={state.reschedule_stage} /></Label>
                        <Label className="flex items-center gap-3 rounded-lg border p-3"><RadioGroupItem value="keep" />Keep current stage</Label>
                    </RadioGroup> : null}
                    <p className="text-sm text-muted-foreground">{state.reschedule_stage && stageId !== state.reschedule_stage.id && cancelChoice === "move" ? `Stage will change to ${state.reschedule_stage.label} when you confirm.` : "Stage will stay unchanged."}</p>
                </div> : null}
                {validation ? <p role="alert" className="text-sm text-destructive">{validation}</p> : null}
                <DialogFooter className={view === "manage" ? "flex-row sm:justify-start" : undefined}>
                    {view === "manage" ? <>
                        <Button className="h-auto min-h-9 min-w-0 shrink whitespace-normal" disabled={!state.can_manage || syncUnresolved} onClick={() => setView("book")}>{active ? "Reschedule" : "Schedule appointment"}</Button>
                        {active ? <Button className="h-auto min-h-9 min-w-0 shrink whitespace-normal" variant="outline" disabled={!state.can_manage || syncUnresolved} onClick={() => setView("cancel")}>Cancel appointment</Button> : null}
                        {externalSyncStatus === "failed" && appointment ? <Button variant="outline" disabled={!state.can_manage || retryGoogleSync.isPending} onClick={() => void retrySync()}>{retryGoogleSync.isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}Retry Google update</Button> : null}
                        <Button className="ml-auto" variant="outline" onClick={() => setOpen(false)}>Done</Button>
                    </> : <Button variant="outline" disabled={mutation.isPending} onClick={() => setView("manage")}>Back</Button>}
                    {view === "book" ? <Button disabled={mutation.isPending || !state.can_manage || !state.scheduled_stage || syncUnresolved} onClick={() => void submit(active ? "reschedule" : "schedule", stageId === state.reschedule_stage?.id)}>{mutation.isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}{stageId === state.reschedule_stage?.id ? active ? "Reschedule & update stage" : "Schedule & update stage" : active ? "Reschedule" : "Schedule"}</Button> : null}
                    {view === "cancel" ? <Button variant="destructive" disabled={mutation.isPending || !state.can_manage || syncUnresolved} onClick={() => void submit("cancel", Boolean(state.reschedule_stage) && cancelChoice === "move" && stageId !== state.reschedule_stage?.id)}>Confirm cancellation</Button> : null}
                </DialogFooter>
            </DialogContent>
        </Dialog> : null}
    </>
}

export function AppointmentHeaderBadge({ surrogateId }: { surrogateId: string }) {
    const { data } = useInterviewAppointment(surrogateId)
    return data?.appointment ? <AppointmentStatusBadge appointment={data.appointment} /> : null
}
