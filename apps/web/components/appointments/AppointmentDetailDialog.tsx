"use client"

/**
 * Appointment detail dialog shared by the Appointments list, the unified calendar and record
 * appointment cards: status, time, format, client, linked records, and the approve, cancel and
 * reschedule flows.
 */

import { useReducer } from "react"
import { AlertCircleIcon, CalendarIcon, Loader2Icon, MailIcon, MapPinIcon, PhoneIcon, VideoIcon } from "lucide-react"
import { format, parseISO } from "date-fns"

import { AppointmentLinkSection } from "@/components/appointments/AppointmentLinkSection"
import { SchedulingSyncBadge, SchedulingSyncState, schedulingCanCancel, schedulingCanReschedule } from "@/components/appointments/SchedulingSyncState"
import { SchedulingTimePicker } from "@/components/appointments/SchedulingTimePicker"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogBody,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import type { Appointment, TimeSlot } from "@/lib/api/appointments"
import { createSchedulingRequestId } from "@/lib/api/appointments"
import { getMeetingModeLabel } from "@/lib/appointment-meeting-mode-labels"
import { getAppointmentStatusLabel } from "@/lib/appointment-status-labels"
import {
    useAppointment,
    useApproveAppointment,
    useCancelAppointment,
    useRescheduleAppointment,
    useRescheduleSlots,
} from "@/lib/hooks/use-appointments"
import { formatSchedulingDate, formatSchedulingTime, localDateTimeToIso, schedulingDateKey, schedulingTimezoneLabel } from "@/lib/scheduling-time"

// Status badge colors
export const APPOINTMENT_STATUS_STYLES = {
    pending: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
    confirmed: "bg-green-500/10 text-green-600 border-green-500/20",
    completed: "bg-blue-500/10 text-blue-600 border-blue-500/20",
    cancelled: "bg-red-500/10 text-red-600 border-red-500/20",
    no_show: "bg-gray-500/10 text-gray-600 border-gray-500/20",
    expired: "bg-gray-500/10 text-gray-600 border-gray-500/20",
}

const RESCHEDULABLE_STATUSES = new Set(["pending", "confirmed"])

export const MEETING_MODE_ICONS: Record<string, typeof VideoIcon> = {
    zoom: VideoIcon,
    google_meet: VideoIcon,
    phone: PhoneIcon,
    in_person: MapPinIcon,
}

type AppointmentDetailDialogState = {
    cancelReason: string
    showCancelForm: boolean
    showRescheduleForm: boolean
    rescheduleDate: string
    selectedSlotStart: string | null
    overrideStart: string
    rescheduleError: string | null
    overrideAvailability: boolean
    overrideReason: string
}

type AppointmentDetailDialogAction =
    | { type: "set-cancel-reason"; value: string }
    | { type: "open-cancel-form" }
    | { type: "close-cancel-form" }
    | { type: "open-reschedule-form"; rescheduleDate: string }
    | { type: "close-reschedule-form" }
    | { type: "set-reschedule-date"; value: string }
    | { type: "select-reschedule-slot"; value: string }
    | { type: "set-override-start"; value: string }
    | { type: "set-reschedule-error"; value: string | null }
    | { type: "set-override-availability"; value: boolean }
    | { type: "set-override-reason"; value: string }

const appointmentDetailDialogInitialState: AppointmentDetailDialogState = {
    cancelReason: "",
    showCancelForm: false,
    showRescheduleForm: false,
    rescheduleDate: "",
    selectedSlotStart: null,
    overrideStart: "",
    rescheduleError: null,
    overrideAvailability: false,
    overrideReason: "",
}

function appointmentDetailDialogReducer(
    state: AppointmentDetailDialogState,
    action: AppointmentDetailDialogAction
): AppointmentDetailDialogState {
    switch (action.type) {
        case "set-cancel-reason":
            return { ...state, cancelReason: action.value }
        case "open-cancel-form":
            return { ...state, showCancelForm: true, showRescheduleForm: false }
        case "close-cancel-form":
            return { ...state, showCancelForm: false }
        case "open-reschedule-form":
            return {
                ...state,
                showCancelForm: false,
                showRescheduleForm: true,
                rescheduleDate: action.rescheduleDate,
                selectedSlotStart: null,
                overrideStart: "",
                rescheduleError: null,
            }
        case "close-reschedule-form":
            return { ...state, showRescheduleForm: false, rescheduleError: null }
        case "set-reschedule-date":
            return {
                ...state,
                rescheduleDate: action.value,
                selectedSlotStart: null,
                rescheduleError: null,
            }
        case "select-reschedule-slot":
            return { ...state, selectedSlotStart: action.value, rescheduleError: null }
        case "set-override-start":
            return { ...state, overrideStart: action.value, rescheduleError: null }
        case "set-reschedule-error":
            return { ...state, rescheduleError: action.value }
        case "set-override-availability":
            return { ...state, overrideAvailability: action.value }
        case "set-override-reason":
            return { ...state, overrideReason: action.value }
    }
}

export function AppointmentDetailDialog({
    appointmentId,
    open,
    onOpenChange,
    initialRescheduleDate = null,
    startInRescheduleMode = false,
}: {
    appointmentId: string | null
    open: boolean
    onOpenChange: (open: boolean) => void
    initialRescheduleDate?: string | null
    startInRescheduleMode?: boolean
}) {
    if (!appointmentId || !open) return null

    return (
        <OpenAppointmentDetailDialog
            appointmentId={appointmentId}
            onOpenChange={onOpenChange}
            initialRescheduleDate={initialRescheduleDate}
            startInRescheduleMode={startInRescheduleMode}
        />
    )
}

function OpenAppointmentDetailDialog({
    appointmentId,
    onOpenChange,
    initialRescheduleDate,
    startInRescheduleMode,
}: {
    appointmentId: string
    onOpenChange: (open: boolean) => void
    initialRescheduleDate: string | null
    startInRescheduleMode: boolean
}) {
    const { data: appointment, isLoading, isError, refetch } = useAppointment(appointmentId)

    if (isLoading) {
        return (
            <Dialog open onOpenChange={onOpenChange}>
                <DialogContent size="lg">
                    <DialogTitle className="sr-only">Appointment</DialogTitle>
                    <div className="py-12 flex items-center justify-center">
                        <Loader2Icon className="size-8 animate-spin text-muted-foreground" aria-label="Loading appointment" />
                    </div>
                </DialogContent>
            </Dialog>
        )
    }

    if (isError) {
        return (
            <Dialog open onOpenChange={onOpenChange}>
                <DialogContent size="lg">
                    <div className="py-10 text-center space-y-4">
                        <AlertCircleIcon className="size-10 mx-auto text-muted-foreground/60" aria-hidden="true" />
                        <div>
                            <DialogTitle className="font-medium">Unable to load appointment details</DialogTitle>
                            <p className="text-sm text-muted-foreground">Please retry in a moment.</p>
                        </div>
                        <Button variant="outline" onClick={() => refetch()}>
                            Retry
                        </Button>
                    </div>
                </DialogContent>
            </Dialog>
        )
    }

    if (!appointment) return null

    return (
        <LoadedAppointmentDetailDialog
            key={appointment.id}
            appointment={appointment}
            appointmentId={appointmentId}
            onOpenChange={onOpenChange}
            initialRescheduleDate={initialRescheduleDate}
            startInRescheduleMode={startInRescheduleMode}
        />
    )
}

function LoadedAppointmentDetailDialog({
    appointment,
    appointmentId,
    onOpenChange,
    initialRescheduleDate,
    startInRescheduleMode,
}: {
    appointment: Appointment
    appointmentId: string
    onOpenChange: (open: boolean) => void
    initialRescheduleDate: string | null
    startInRescheduleMode: boolean
}) {
    const approveMutation = useApproveAppointment()
    const rescheduleMutation = useRescheduleAppointment()
    const cancelMutation = useCancelAppointment()
    const [dialogState, dispatchDialogState] = useReducer(
        appointmentDetailDialogReducer,
        appointmentDetailDialogInitialState,
        (initialState) => ({
            ...initialState,
            showRescheduleForm:
                startInRescheduleMode && RESCHEDULABLE_STATUSES.has(appointment.status),
            rescheduleDate:
                initialRescheduleDate ||
                schedulingDateKey(appointment.scheduled_start, appointment.client_timezone),
        })
    )

    const slotsQuery = useRescheduleSlots(
        appointmentId || "",
        dialogState.rescheduleDate,
        dialogState.rescheduleDate,
        appointment?.client_timezone,
        dialogState.showRescheduleForm && !!dialogState.rescheduleDate && !dialogState.overrideAvailability,
    )

    const handleApprove = () => {
        approveMutation.mutate({
            appointmentId,
            ...(appointment.scheduling ? { expectedRevision: appointment.scheduling.revision, requestId: createSchedulingRequestId() } : {}),
        }, {
            onSuccess: () => onOpenChange(false),
        })
    }

    const handleReschedule = () => {
        const scheduledStart = dialogState.overrideAvailability
            ? localDateTimeToIso(dialogState.overrideStart)
            : dialogState.selectedSlotStart
        if (!scheduledStart) {
            dispatchDialogState({
                type: "set-reschedule-error",
                value: dialogState.overrideAvailability ? "Choose a valid override date and time." : "Please choose an available time slot.",
            })
            return
        }

        dispatchDialogState({ type: "set-reschedule-error", value: null })
        rescheduleMutation.mutate(
            {
                appointmentId,
                scheduledStart,
                ...(appointment.scheduling ? { expectedRevision: appointment.scheduling.revision, requestId: createSchedulingRequestId() } : {}),
                overrideAvailability: dialogState.overrideAvailability,
                ...(dialogState.overrideReason.trim() ? { overrideReason: dialogState.overrideReason.trim() } : {}),
            },
            {
                onSuccess: () => onOpenChange(false),
                onError: (error) => {
                    const message =
                        error instanceof Error && error.message
                            ? error.message
                            : "Failed to reschedule appointment. Please try another time."
                    dispatchDialogState({ type: "set-reschedule-error", value: message })
                },
            }
        )
    }

    const handleCancel = () => {
        const payload = {
            appointmentId,
            ...(dialogState.cancelReason.trim() ? { reason: dialogState.cancelReason.trim() } : {}),
            ...(appointment.scheduling ? { expectedRevision: appointment.scheduling.revision, requestId: createSchedulingRequestId() } : {}),
        }
        cancelMutation.mutate(payload, { onSuccess: () => onOpenChange(false) })
    }

    const isReschedulable = RESCHEDULABLE_STATUSES.has(appointment.status)
    const actionMode = dialogState.showRescheduleForm ? "reschedule" : dialogState.showCancelForm ? "cancel" : null
    const hasDetailActions = appointment.status === "pending" || appointment.status === "confirmed"
    const syncNeedsAttention = ["failed", "unlinked", "conflict"].includes(appointment.scheduling?.google_sync.state ?? "")

    return (
        <Dialog open onOpenChange={onOpenChange}>
            <DialogContent layout="sectioned" size={actionMode === "reschedule" ? "2xl" : "lg"}>
                <DialogHeader>
                    <DialogTitle>{actionMode === "reschedule" ? "Reschedule appointment" : actionMode === "cancel" ? "Cancel appointment?" : appointment.appointment_type_name || "Appointment"}</DialogTitle>
                    <DialogDescription>{actionMode ? appointment.appointment_type_name || "Appointment" : appointment.client_name}</DialogDescription>
                    {!actionMode && <AppointmentStatusSummary appointment={appointment} />}
                </DialogHeader>

                <DialogBody className="gap-4">
                    {actionMode ? <AppointmentActionSummary appointment={appointment} /> : <>
                        {syncNeedsAttention ? <SchedulingSyncState appointment={appointment} /> : null}
                        <AppointmentTimeSummary appointment={appointment} />
                        <AppointmentFormatSummary appointment={appointment} />
                        <AppointmentClientInfo appointment={appointment} />
                        <AppointmentLinkSection appointment={appointment} />
                    </>}
                    {dialogState.showCancelForm && (
                        <AppointmentCancelForm
                            cancelReason={dialogState.cancelReason}
                            onCancelReasonChange={(value) =>
                                dispatchDialogState({ type: "set-cancel-reason", value })
                            }
                        />
                    )}
                    {dialogState.showRescheduleForm && (
                        <AppointmentRescheduleForm
                            rescheduleDate={dialogState.rescheduleDate}
                            timezone={appointment.client_timezone}
                            selectedSlotStart={dialogState.selectedSlotStart}
                            rescheduleError={dialogState.rescheduleError}
                            slots={slotsQuery.data?.slots}
                            slotsLoading={slotsQuery.isLoading}
                            slotsError={slotsQuery.isError}
                            onRetrySlots={() => void slotsQuery.refetch()}
                            onRescheduleDateChange={(value) =>
                                dispatchDialogState({ type: "set-reschedule-date", value })
                            }
                            onSlotSelect={(value) =>
                                dispatchDialogState({ type: "select-reschedule-slot", value })
                            }
                            overrideAvailability={dialogState.overrideAvailability}
                            overrideReason={dialogState.overrideReason}
                            overrideStart={dialogState.overrideStart}
                            onOverrideAvailabilityChange={(value) => dispatchDialogState({ type: "set-override-availability", value })}
                            onOverrideReasonChange={(value) => dispatchDialogState({ type: "set-override-reason", value })}
                            onOverrideStartChange={(value) => dispatchDialogState({ type: "set-override-start", value })}
                        />
                    )}
                </DialogBody>

                {hasDetailActions ? <AppointmentDetailActions
                    appointment={appointment}
                    state={{
                        isReschedulable,
                        forms: { cancel: dialogState.showCancelForm, reschedule: dialogState.showRescheduleForm, selectedSlotStart: dialogState.overrideAvailability ? localDateTimeToIso(dialogState.overrideStart) : dialogState.selectedSlotStart, overrideReady: !dialogState.overrideAvailability || Boolean(dialogState.overrideReason.trim()) },
                        capabilities: { reschedule: schedulingCanReschedule(appointment.scheduling), cancel: schedulingCanCancel(appointment.scheduling) },
                        pending: { approve: approveMutation.isPending, cancel: cancelMutation.isPending, reschedule: rescheduleMutation.isPending },
                    }}
                    handlers={{
                        approve: handleApprove,
                        cancel: handleCancel,
                        reschedule: handleReschedule,
                        closeCancel: () => dispatchDialogState({ type: "close-cancel-form" }),
                        closeReschedule: () => dispatchDialogState({ type: "close-reschedule-form" }),
                        openCancel: () => dispatchDialogState({ type: "open-cancel-form" }),
                        openReschedule: () => dispatchDialogState({ type: "open-reschedule-form", rescheduleDate: schedulingDateKey(appointment.scheduled_start, appointment.client_timezone) }),
                    }}
                /> : null}
            </DialogContent>
        </Dialog>
    )
}

function AppointmentStatusSummary({ appointment }: { appointment: Appointment }) {
    const syncState = appointment.scheduling?.google_sync.state
    return (
        <div role="status" className="flex flex-wrap items-center gap-2">
            <Badge className={APPOINTMENT_STATUS_STYLES[appointment.status]}>
                {getAppointmentStatusLabel(appointment.status)}
            </Badge>
            {(syncState === "pending" || syncState === "completed") && (
                <SchedulingSyncBadge scheduling={appointment.scheduling} />
            )}
            {appointment.status === "pending" && appointment.pending_expires_at && (
                <span className="text-sm text-muted-foreground">
                    Expires {format(parseISO(appointment.pending_expires_at), "h:mm a")}
                </span>
            )}
        </div>
    )
}

function AppointmentActionSummary({ appointment }: { appointment: Appointment }) {
    return <div className="rounded-lg border bg-muted/30 px-3 py-2 text-sm">
        <p className="font-medium">{appointment.client_name}</p>
        <p className="text-muted-foreground">
            {formatSchedulingDate(appointment.scheduled_start, appointment.client_timezone)} · {formatSchedulingTime(appointment.scheduled_start, appointment.client_timezone)} · {appointment.duration_minutes} min · {schedulingTimezoneLabel(appointment.client_timezone)}
        </p>
    </div>
}

function AppointmentTimeSummary({ appointment }: { appointment: Appointment }) {
    return (
        <div className="flex items-start gap-3">
            <CalendarIcon className="size-5 text-muted-foreground mt-0.5" aria-hidden="true" />
            <div>
                <p className="font-medium">
                    {formatSchedulingDate(appointment.scheduled_start, appointment.client_timezone)}
                </p>
                <p className="text-sm text-muted-foreground">
                    {formatSchedulingTime(appointment.scheduled_start, appointment.client_timezone)} –{" "}
                    {formatSchedulingTime(appointment.scheduled_end, appointment.client_timezone)}
                    <span className="ml-2">{schedulingTimezoneLabel(appointment.client_timezone)} · {appointment.duration_minutes} min</span>
                </p>
            </div>
        </div>
    )
}

function AppointmentFormatSummary({ appointment }: { appointment: Appointment }) {
    const ModeIcon = MEETING_MODE_ICONS[appointment.meeting_mode as keyof typeof MEETING_MODE_ICONS] || VideoIcon

    return (
        <>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <ModeIcon className="size-5 text-muted-foreground" aria-hidden="true" />
                <p className="font-medium">{getMeetingModeLabel(appointment.meeting_mode)}</p>
                {appointment.zoom_join_url && (
                    <a
                        href={appointment.zoom_join_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary underline text-sm"
                    >
                        Join Zoom
                    </a>
                )}
                {appointment.google_meet_url && (
                    <a
                        href={appointment.google_meet_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary underline text-sm"
                    >
                        Join Google Meet
                    </a>
                )}
            </div>
            {appointment.meeting_location && (
                <div className="flex items-center gap-3">
                    <MapPinIcon className="size-5 text-muted-foreground" aria-hidden="true" />
                    <p className="font-medium">{appointment.meeting_location}</p>
                </div>
            )}
            {appointment.dial_in_number && (
                <div className="flex items-center gap-3">
                    <PhoneIcon className="size-5 text-muted-foreground" aria-hidden="true" />
                    <p className="font-medium">{appointment.dial_in_number}</p>
                </div>
            )}
        </>
    )
}

function AppointmentClientInfo({ appointment }: { appointment: Appointment }) {
    return (
        <div className="border-t border-border pt-3">
            <div className="space-y-2">
                <p className="text-sm flex items-center gap-2">
                    <MailIcon className="size-4 text-muted-foreground" aria-hidden="true" />
                    <a href={`mailto:${appointment.client_email}`} className="text-primary hover:underline">
                        {appointment.client_email}
                    </a>
                </p>
                <p className="text-sm flex items-center gap-2">
                    <PhoneIcon className="size-4 text-muted-foreground" aria-hidden="true" />
                    <a href={`tel:${appointment.client_phone}`} className="text-primary hover:underline">
                        {appointment.client_phone}
                    </a>
                </p>
                {appointment.client_notes && (
                    <div className="mt-3 p-3 rounded-lg bg-muted">
                        <p className="text-sm text-muted-foreground font-medium mb-1">Notes</p>
                        <p className="text-sm">{appointment.client_notes}</p>
                    </div>
                )}
            </div>
        </div>
    )
}

function AppointmentCancelForm({
    cancelReason,
    onCancelReasonChange,
}: {
    cancelReason: string
    onCancelReasonChange: (value: string) => void
}) {
    return (
        <div className="border-t border-border pt-4">
            <Label className="mb-2" htmlFor="cancellation-reason">Reason (optional)</Label>
            <Textarea
                id="cancellation-reason"
                value={cancelReason}
                onChange={(event) => onCancelReasonChange(event.target.value)}
                rows={2}
            />
        </div>
    )
}

function AppointmentRescheduleForm({
    rescheduleDate,
    timezone,
    selectedSlotStart,
    rescheduleError,
    slots,
    slotsLoading,
    slotsError,
    onRetrySlots,
    onRescheduleDateChange,
    onSlotSelect,
    overrideAvailability,
    overrideReason,
    overrideStart,
    onOverrideAvailabilityChange,
    onOverrideReasonChange,
    onOverrideStartChange,
}: {
    rescheduleDate: string
    timezone: string
    selectedSlotStart: string | null
    rescheduleError: string | null
    slots: TimeSlot[] | undefined
    slotsLoading: boolean
    slotsError: boolean
    onRetrySlots: () => void
    onRescheduleDateChange: (value: string) => void
    onSlotSelect: (value: string) => void
    overrideAvailability: boolean
    overrideReason: string
    overrideStart: string
    onOverrideAvailabilityChange: (value: boolean) => void
    onOverrideReasonChange: (value: string) => void
    onOverrideStartChange: (value: string) => void
}) {
    return (
        <div className="border-t border-border pt-4 space-y-4">
            <SchedulingTimePicker
                idPrefix="reschedule"
                date={rescheduleDate}
                onDateChange={onRescheduleDateChange}
                timezone={overrideAvailability ? Intl.DateTimeFormat().resolvedOptions().timeZone : timezone}
                slots={slots}
                selectedStart={selectedSlotStart}
                onSelectStart={onSlotSelect}
                loading={slotsLoading}
                error={slotsError ? "Calendar availability could not be loaded." : null}
                onRetry={onRetrySlots}
                override={{ enabled: overrideAvailability, onEnabledChange: onOverrideAvailabilityChange, dateTime: overrideStart, onDateTimeChange: onOverrideStartChange, reason: overrideReason, onReasonChange: onOverrideReasonChange }}
            />
            {rescheduleError && (
                <p role="alert" className="text-sm text-destructive">
                    {rescheduleError}
                </p>
            )}
        </div>
    )
}

function AppointmentDetailActions({ appointment, state, handlers }: {
    appointment: Appointment
    state: { isReschedulable: boolean; forms: { cancel: boolean; reschedule: boolean; selectedSlotStart: string | null; overrideReady: boolean }; capabilities: { reschedule: boolean; cancel: boolean }; pending: { approve: boolean; cancel: boolean; reschedule: boolean } }
    handlers: { approve: () => void; cancel: () => void; reschedule: () => void; closeCancel: () => void; closeReschedule: () => void; openCancel: () => void; openReschedule: () => void }
}) {
    if (state.forms.reschedule) {
        return (
            <DialogFooter>
                <Button
                    variant="outline"
                    onClick={handlers.closeReschedule}
                    disabled={state.pending.reschedule}
                >
                    Back
                </Button>
                <Button
                    onClick={handlers.reschedule}
                    disabled={state.pending.reschedule || !state.forms.selectedSlotStart || !state.forms.overrideReady || !state.capabilities.reschedule}
                >
                    {state.pending.reschedule && (
                        <Loader2Icon className="size-4 mr-2 animate-spin" />
                    )}
                    Save new time
                </Button>
            </DialogFooter>
        )
    }

    if (state.forms.cancel) {
        return (
            <DialogFooter>
                <Button
                    variant="outline"
                    onClick={handlers.closeCancel}
                    disabled={state.pending.cancel}
                >
                    Back
                </Button>
                <Button
                    variant="destructive"
                    onClick={handlers.cancel}
                    disabled={state.pending.cancel || !state.capabilities.cancel}
                >
                    {state.pending.cancel && <Loader2Icon className="size-4 mr-2 animate-spin" />}
                    Cancel appointment
                </Button>
            </DialogFooter>
        )
    }

    return (
        <DialogFooter
            start={state.capabilities.cancel ? (
                <Button variant="destructive-ghost" onClick={handlers.openCancel}>
                    {appointment.status === "pending" ? "Decline" : "Cancel appointment"}
                </Button>
            ) : undefined}
        >
            {state.isReschedulable && state.capabilities.reschedule && (
                <Button
                    variant="outline"
                    onClick={handlers.openReschedule}
                >
                    Reschedule appointment
                </Button>
            )}
            {appointment.status === "pending" && (
                <Button
                    variant="success"
                    onClick={handlers.approve}
                    disabled={state.pending.approve}
                >
                    {state.pending.approve && <Loader2Icon className="size-4 mr-2 animate-spin" />}
                    Approve
                </Button>
            )}
        </DialogFooter>
    )
}
