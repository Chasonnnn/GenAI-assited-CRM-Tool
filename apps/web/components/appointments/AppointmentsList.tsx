"use client"

/**
 * Appointments List - Dashboard for viewing and managing appointments
 * 
 * Features:
 * - Tabs for pending/upcoming/past
 * - Approval workflow for pending
 * - Quick actions (approve, cancel)
 * - Detail side panel
 */

import { startTransition, useEffect, useReducer, useState, type ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import {
    CheckIcon,
    XIcon,
    ClockIcon,
    CalendarIcon,
    PhoneIcon,
    MailIcon,
    VideoIcon,
    MapPinIcon,
    Loader2Icon,
    AlertCircleIcon,
    ChevronRightIcon,
} from "lucide-react"
import {
    useAppointments,
    useAppointment,
    useApproveAppointment,
    useRescheduleSlots,
    useRescheduleAppointment,
    useCancelAppointment,
} from "@/lib/hooks/use-appointments"
import type { Appointment, AppointmentListItem, TimeSlot } from "@/lib/api/appointments"
import { format, parseISO } from "date-fns"

// Status badge colors
const STATUS_STYLES = {
    pending: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
    confirmed: "bg-green-500/10 text-green-600 border-green-500/20",
    completed: "bg-blue-500/10 text-blue-600 border-blue-500/20",
    cancelled: "bg-red-500/10 text-red-600 border-red-500/20",
    no_show: "bg-gray-500/10 text-gray-600 border-gray-500/20",
    expired: "bg-gray-500/10 text-gray-600 border-gray-500/20",
}

const RESCHEDULABLE_STATUSES = new Set(["pending", "confirmed"])

// Meeting mode icons
const MEETING_MODE_ICONS: Record<string, typeof VideoIcon> = {
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
    rescheduleError: string | null
}

type AppointmentDetailDialogAction =
    | { type: "reset"; rescheduleDate: string; showRescheduleForm: boolean }
    | { type: "set-cancel-reason"; value: string }
    | { type: "open-cancel-form" }
    | { type: "close-cancel-form" }
    | { type: "open-reschedule-form"; rescheduleDate: string }
    | { type: "close-reschedule-form" }
    | { type: "set-reschedule-date"; value: string }
    | { type: "select-reschedule-slot"; value: string }
    | { type: "set-reschedule-error"; value: string | null }

const appointmentDetailDialogInitialState: AppointmentDetailDialogState = {
    cancelReason: "",
    showCancelForm: false,
    showRescheduleForm: false,
    rescheduleDate: "",
    selectedSlotStart: null,
    rescheduleError: null,
}

function appointmentDetailDialogReducer(
    state: AppointmentDetailDialogState,
    action: AppointmentDetailDialogAction
): AppointmentDetailDialogState {
    switch (action.type) {
        case "reset":
            return {
                cancelReason: "",
                showCancelForm: false,
                showRescheduleForm: action.showRescheduleForm,
                rescheduleDate: action.rescheduleDate,
                selectedSlotStart: null,
                rescheduleError: null,
            }
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
        case "set-reschedule-error":
            return { ...state, rescheduleError: action.value }
    }
}

// =============================================================================
// Appointment Card
// =============================================================================

function AppointmentCard({
    appointment,
    onSelect,
    trailingActions,
}: {
    appointment: AppointmentListItem
    onSelect: () => void
    trailingActions?: ReactNode
}) {
    const ModeIcon = MEETING_MODE_ICONS[appointment.meeting_mode as keyof typeof MEETING_MODE_ICONS] || VideoIcon
    const initials = appointment.client_name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)

    return (
        <div
            className="flex items-center justify-between rounded-lg border border-border transition-colors hover:bg-muted/50"
        >
            <Button unstyled
                type="button"
                className="flex min-w-0 flex-1 cursor-pointer items-center justify-between gap-4 rounded-lg bg-transparent p-4 text-left outline-none transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50"
                onClick={onSelect}
            >
                <span className="flex min-w-0 items-center gap-4">
                    <Avatar className="size-12">
                        <AvatarFallback className="bg-primary/10 text-primary">
                            {initials}
                        </AvatarFallback>
                    </Avatar>
                    <span className="min-w-0">
                        <span className="flex items-center gap-2">
                            <span className="font-medium">{appointment.client_name}</span>
                            <Badge className={STATUS_STYLES[appointment.status as keyof typeof STATUS_STYLES]}>
                                {appointment.status.replace("_", " ")}
                            </Badge>
                        </span>
                        <span className="mt-1 flex items-center gap-3 text-sm text-muted-foreground">
                            <span className="flex items-center gap-1">
                                <CalendarIcon className="size-3.5" />
                                {format(parseISO(appointment.scheduled_start), "MMM d, yyyy")}
                            </span>
                            <span className="flex items-center gap-1">
                                <ClockIcon className="size-3.5" />
                                {format(parseISO(appointment.scheduled_start), "h:mm a")}
                            </span>
                            <span className="flex items-center gap-1">
                                <ModeIcon className="size-3.5" />
                                {appointment.duration_minutes} min
                            </span>
                        </span>
                        {appointment.appointment_type_name && (
                            <span className="block text-sm text-muted-foreground">
                                {appointment.appointment_type_name}
                            </span>
                        )}
                    </span>
                </span>
                {!trailingActions && (
                    <ChevronRightIcon className="size-5 shrink-0 text-muted-foreground" />
                )}
            </Button>

            {trailingActions && (
                <div className="flex items-center gap-2 pr-4">
                    {trailingActions}
                </div>
            )}
        </div>
    )
}

// =============================================================================
// Appointment Detail Dialog
// =============================================================================

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
    const { data: appointment, isLoading, isError, refetch } = useAppointment(appointmentId || "")
    const approveMutation = useApproveAppointment()
    const rescheduleMutation = useRescheduleAppointment()
    const cancelMutation = useCancelAppointment()
    const [dialogState, dispatchDialogState] = useReducer(
        appointmentDetailDialogReducer,
        appointmentDetailDialogInitialState
    )

    const slotsQuery = useRescheduleSlots(
        appointmentId || "",
        dialogState.rescheduleDate,
        dialogState.rescheduleDate,
        appointment?.client_timezone,
        dialogState.showRescheduleForm && !!dialogState.rescheduleDate,
    )

    useEffect(() => {
        if (!open || !appointment) return
        const canStartInRescheduleMode =
            startInRescheduleMode && RESCHEDULABLE_STATUSES.has(appointment.status)
        const defaultRescheduleDate = format(parseISO(appointment.scheduled_start), "yyyy-MM-dd")

        startTransition(() => {
            dispatchDialogState({
                type: "reset",
                showRescheduleForm: canStartInRescheduleMode,
                rescheduleDate: initialRescheduleDate || defaultRescheduleDate,
            })
        })
    }, [appointment, open, initialRescheduleDate, startInRescheduleMode])

    if (!appointmentId) return null

    const handleApprove = () => {
        approveMutation.mutate(appointmentId, {
            onSuccess: () => onOpenChange(false),
        })
    }

    const handleReschedule = () => {
        if (!dialogState.selectedSlotStart) {
            dispatchDialogState({
                type: "set-reschedule-error",
                value: "Please choose an available time slot.",
            })
            return
        }

        dispatchDialogState({ type: "set-reschedule-error", value: null })
        rescheduleMutation.mutate(
            {
                appointmentId,
                scheduledStart: dialogState.selectedSlotStart,
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
        }
        cancelMutation.mutate(payload, { onSuccess: () => onOpenChange(false) })
    }

    if (isLoading) {
        return (
            <Dialog open={open} onOpenChange={onOpenChange}>
                <DialogContent>
                    <div className="py-12 flex items-center justify-center">
                        <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                    </div>
                </DialogContent>
            </Dialog>
        )
    }

    if (isError) {
        return (
            <Dialog open={open} onOpenChange={onOpenChange}>
                <DialogContent>
                    <div className="py-10 text-center space-y-4">
                        <AlertCircleIcon className="size-10 mx-auto text-muted-foreground/60" />
                        <div>
                            <p className="font-medium">Unable to load appointment details</p>
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

    const isReschedulable = RESCHEDULABLE_STATUSES.has(appointment.status)

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-lg">
                <DialogHeader>
                    <DialogTitle>Appointment Details</DialogTitle>
                    <DialogDescription>
                        {appointment.appointment_type_name || "Appointment"} with {appointment.client_name}
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-6 py-4">
                    <AppointmentStatusSummary appointment={appointment} />
                    <AppointmentTimeSummary appointment={appointment} />
                    <AppointmentFormatSummary appointment={appointment} />
                    <AppointmentClientInfo appointment={appointment} />
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
                            selectedSlotStart={dialogState.selectedSlotStart}
                            rescheduleError={dialogState.rescheduleError}
                            slots={slotsQuery.data?.slots}
                            slotsLoading={slotsQuery.isLoading}
                            slotsError={slotsQuery.isError}
                            onRescheduleDateChange={(value) =>
                                dispatchDialogState({ type: "set-reschedule-date", value })
                            }
                            onSlotSelect={(value) =>
                                dispatchDialogState({ type: "select-reschedule-slot", value })
                            }
                        />
                    )}
                </div>

                <AppointmentDetailActions
                    appointment={appointment}
                    isReschedulable={isReschedulable}
                    showCancelForm={dialogState.showCancelForm}
                    showRescheduleForm={dialogState.showRescheduleForm}
                    selectedSlotStart={dialogState.selectedSlotStart}
                    approvePending={approveMutation.isPending}
                    cancelPending={cancelMutation.isPending}
                    reschedulePending={rescheduleMutation.isPending}
                    onApprove={handleApprove}
                    onCancel={handleCancel}
                    onReschedule={handleReschedule}
                    onCloseCancel={() => dispatchDialogState({ type: "close-cancel-form" })}
                    onCloseReschedule={() => dispatchDialogState({ type: "close-reschedule-form" })}
                    onOpenCancel={() => dispatchDialogState({ type: "open-cancel-form" })}
                    onOpenReschedule={() =>
                        dispatchDialogState({
                            type: "open-reschedule-form",
                            rescheduleDate: format(parseISO(appointment.scheduled_start), "yyyy-MM-dd"),
                        })
                    }
                />
            </DialogContent>
        </Dialog>
    )
}

function AppointmentStatusSummary({ appointment }: { appointment: Appointment }) {
    return (
        <div className="flex items-center gap-2">
            <Badge className={`${STATUS_STYLES[appointment.status]} text-sm px-3 py-1`}>
                {appointment.status.replace("_", " ").toUpperCase()}
            </Badge>
            {appointment.status === "pending" && appointment.pending_expires_at && (
                <span className="text-sm text-muted-foreground">
                    Expires {format(parseISO(appointment.pending_expires_at), "h:mm a")}
                </span>
            )}
        </div>
    )
}

function AppointmentTimeSummary({ appointment }: { appointment: Appointment }) {
    return (
        <div className="flex items-start gap-3">
            <CalendarIcon className="size-5 text-muted-foreground mt-0.5" />
            <div>
                <p className="font-medium">
                    {format(parseISO(appointment.scheduled_start), "EEEE, MMMM d, yyyy")}
                </p>
                <p className="text-sm text-muted-foreground">
                    {format(parseISO(appointment.scheduled_start), "h:mm a")} –{" "}
                    {format(parseISO(appointment.scheduled_end), "h:mm a")}
                    <span className="ml-2">({appointment.duration_minutes} min)</span>
                </p>
            </div>
        </div>
    )
}

function AppointmentFormatSummary({ appointment }: { appointment: Appointment }) {
    const ModeIcon = MEETING_MODE_ICONS[appointment.meeting_mode as keyof typeof MEETING_MODE_ICONS] || VideoIcon

    return (
        <>
            <div className="flex items-center gap-3">
                <ModeIcon className="size-5 text-muted-foreground" />
                <p className="font-medium capitalize">{appointment.meeting_mode.replace("_", " ")}</p>
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
                    <MapPinIcon className="size-5 text-muted-foreground" />
                    <p className="font-medium">{appointment.meeting_location}</p>
                </div>
            )}
            {appointment.dial_in_number && (
                <div className="flex items-center gap-3">
                    <PhoneIcon className="size-5 text-muted-foreground" />
                    <p className="font-medium">{appointment.dial_in_number}</p>
                </div>
            )}
        </>
    )
}

function AppointmentClientInfo({ appointment }: { appointment: Appointment }) {
    return (
        <div className="border-t border-border pt-4">
            <h4 className="text-sm font-medium text-muted-foreground mb-3">Client Information</h4>
            <div className="space-y-2">
                <p className="font-medium">{appointment.client_name}</p>
                <p className="text-sm flex items-center gap-2">
                    <MailIcon className="size-4 text-muted-foreground" />
                    <a href={`mailto:${appointment.client_email}`} className="text-primary hover:underline">
                        {appointment.client_email}
                    </a>
                </p>
                <p className="text-sm flex items-center gap-2">
                    <PhoneIcon className="size-4 text-muted-foreground" />
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
            <Label className="mb-2">Cancellation Reason (optional)</Label>
            <Textarea
                value={cancelReason}
                onChange={(event) => onCancelReasonChange(event.target.value)}
                placeholder="Enter reason for cancellation…"
                rows={3}
            />
        </div>
    )
}

function AppointmentRescheduleForm({
    rescheduleDate,
    selectedSlotStart,
    rescheduleError,
    slots,
    slotsLoading,
    slotsError,
    onRescheduleDateChange,
    onSlotSelect,
}: {
    rescheduleDate: string
    selectedSlotStart: string | null
    rescheduleError: string | null
    slots: TimeSlot[] | undefined
    slotsLoading: boolean
    slotsError: boolean
    onRescheduleDateChange: (value: string) => void
    onSlotSelect: (value: string) => void
}) {
    return (
        <div className="border-t border-border pt-4 space-y-4">
            <div className="space-y-2">
                <Label htmlFor="reschedule-date">New Date</Label>
                <Input
                    id="reschedule-date"
                    type="date"
                    value={rescheduleDate}
                    onChange={(event) => onRescheduleDateChange(event.target.value)}
                />
            </div>

            <div className="space-y-2">
                <Label>Available Times</Label>
                {slotsLoading ? (
                    <div className="py-2 flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2Icon className="size-4 animate-spin" />
                        Loading available slots…
                    </div>
                ) : slots?.length ? (
                    <div className="grid grid-cols-3 gap-2 max-h-44 overflow-y-auto">
                        {slots.map((slot) => {
                            const selected = selectedSlotStart === slot.start
                            return (
                                <Button
                                    key={slot.start}
                                    variant={selected ? "default" : "outline"}
                                    size="sm"
                                    aria-label={`Reschedule slot ${slot.start}`}
                                    onClick={() => onSlotSelect(slot.start)}
                                    className="h-auto py-2"
                                >
                                    {format(parseISO(slot.start), "h:mm a")}
                                </Button>
                            )
                        })}
                    </div>
                ) : (
                    <p className="text-sm text-muted-foreground">
                        No available times for this date.
                    </p>
                )}
            </div>

            <p className="text-xs text-muted-foreground">
                Times shown in your local timezone.
            </p>
            {slotsError && (
                <p className="text-sm text-destructive">
                    Failed to load availability. Try a different date.
                </p>
            )}
            {rescheduleError && (
                <p role="alert" className="text-sm text-destructive">
                    {rescheduleError}
                </p>
            )}
        </div>
    )
}

function AppointmentDetailActions({
    appointment,
    isReschedulable,
    showCancelForm,
    showRescheduleForm,
    selectedSlotStart,
    approvePending,
    cancelPending,
    reschedulePending,
    onApprove,
    onCancel,
    onReschedule,
    onCloseCancel,
    onCloseReschedule,
    onOpenCancel,
    onOpenReschedule,
}: {
    appointment: Appointment
    isReschedulable: boolean
    showCancelForm: boolean
    showRescheduleForm: boolean
    selectedSlotStart: string | null
    approvePending: boolean
    cancelPending: boolean
    reschedulePending: boolean
    onApprove: () => void
    onCancel: () => void
    onReschedule: () => void
    onCloseCancel: () => void
    onCloseReschedule: () => void
    onOpenCancel: () => void
    onOpenReschedule: () => void
}) {
    if (appointment.status !== "pending" && appointment.status !== "confirmed") {
        return null
    }

    return (
        <div className="flex flex-wrap justify-end gap-2 pt-4 border-t border-border">
            {showRescheduleForm ? (
                <>
                    <Button
                        variant="outline"
                        onClick={onCloseReschedule}
                        disabled={reschedulePending}
                    >
                        Back
                    </Button>
                    <Button
                        onClick={onReschedule}
                        disabled={reschedulePending || !selectedSlotStart}
                    >
                        {reschedulePending && (
                            <Loader2Icon className="size-4 mr-2 animate-spin" />
                        )}
                        Confirm Reschedule
                    </Button>
                </>
            ) : showCancelForm ? (
                <>
                    <Button
                        variant="outline"
                        onClick={onCloseCancel}
                        disabled={cancelPending}
                    >
                        Back
                    </Button>
                    <Button
                        variant="destructive"
                        onClick={onCancel}
                        disabled={cancelPending}
                    >
                        {cancelPending && <Loader2Icon className="size-4 mr-2 animate-spin" />}
                        Confirm Cancel
                    </Button>
                </>
            ) : (
                <>
                    {isReschedulable && (
                        <Button
                            variant="outline"
                            onClick={onOpenReschedule}
                        >
                            Reschedule Appointment
                        </Button>
                    )}
                    <Button
                        variant="outline"
                        onClick={onOpenCancel}
                        className="text-destructive"
                    >
                        {appointment.status === "pending" ? "Decline" : "Cancel Appointment"}
                    </Button>
                    {appointment.status === "pending" && (
                        <Button
                            onClick={onApprove}
                            disabled={approvePending}
                            className="bg-green-600 hover:bg-green-700"
                        >
                            {approvePending && <Loader2Icon className="size-4 mr-2 animate-spin" />}
                            Approve
                        </Button>
                    )}
                </>
            )}
        </div>
    )
}

// =============================================================================
// Empty State
// =============================================================================

function EmptyState({ message }: { message: string }) {
    return (
        <div className="text-center py-12">
            <AlertCircleIcon className="size-12 mx-auto mb-4 text-muted-foreground/50" />
            <p className="text-muted-foreground">{message}</p>
        </div>
    )
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
    return (
        <div className="text-center py-12 space-y-4">
            <AlertCircleIcon className="size-12 mx-auto text-muted-foreground/50" />
            <div className="space-y-1">
                <p className="font-medium">{message}</p>
                <p className="text-sm text-muted-foreground">Please try again.</p>
            </div>
            <Button variant="outline" onClick={onRetry}>
                Retry
            </Button>
        </div>
    )
}

// =============================================================================
// Appointments List Tab Content
// =============================================================================

function AppointmentsTabContent({
    status,
    emptyMessage,
}: {
    status: string
    emptyMessage: string
}) {
    const { data, isLoading, isError, refetch } = useAppointments({ status, per_page: 50 })
    const approveMutation = useApproveAppointment()
    const cancelMutation = useCancelAppointment()
    const [selectedId, setSelectedId] = useState<string | null>(null)
    const [dialogOpen, setDialogOpen] = useState(false)

    if (isLoading) {
        return (
            <div className="py-12 flex items-center justify-center">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (isError) {
        return <ErrorState message="Unable to load appointments" onRetry={() => refetch()} />
    }

    if (!data?.items.length) {
        return <EmptyState message={emptyMessage} />
    }

    return (
        <>
            <div className="space-y-3">
                {data.items.map((appt) => {
                    const isApproving = approveMutation.isPending && approveMutation.variables === appt.id
                    const isCancelling =
                        cancelMutation.isPending &&
                        cancelMutation.variables?.appointmentId === appt.id
                    const trailingActions = status === "pending" ? (
                        <>
                            <Button
                                size="sm"
                                onClick={() => approveMutation.mutate(appt.id)}
                                disabled={isApproving}
                                className="bg-green-600 hover:bg-green-700"
                            >
                                {isApproving ? (
                                    <Loader2Icon className="size-4 animate-spin" />
                                ) : (
                                    <CheckIcon className="size-4" />
                                )}
                                <span className="ml-1.5">Approve</span>
                            </Button>
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={() => cancelMutation.mutate({ appointmentId: appt.id })}
                                disabled={isCancelling}
                                className="text-destructive border-destructive/30 hover:bg-destructive/10"
                            >
                                {isCancelling ? (
                                    <Loader2Icon className="size-4 animate-spin" />
                                ) : (
                                    <XIcon className="size-4" />
                                )}
                                <span className="ml-1.5">Decline</span>
                            </Button>
                        </>
                    ) : null
                    return (
                        <AppointmentCard
                            appointment={appt}
                            onSelect={() => {
                                setSelectedId(appt.id)
                                setDialogOpen(true)
                            }}
                            {...(trailingActions ? { trailingActions } : {})}
                            key={appt.id}
                        />
                    )
                })}
            </div>

            <AppointmentDetailDialog
                appointmentId={selectedId}
                open={dialogOpen}
                onOpenChange={setDialogOpen}
            />
        </>
    )
}

// =============================================================================
// Main Export
// =============================================================================

export function AppointmentsList() {
    return (
        <Tabs defaultValue="confirmed" className="w-full">
            <TabsList>
                <TabsTrigger value="confirmed">Upcoming</TabsTrigger>
                <TabsTrigger value="pending">Pending</TabsTrigger>
                <TabsTrigger value="completed">Past</TabsTrigger>
                <TabsTrigger value="cancelled">Cancelled</TabsTrigger>
                <TabsTrigger value="expired">Expired</TabsTrigger>
            </TabsList>

            <TabsContent value="confirmed" className="mt-4">
                <AppointmentsTabContent
                    status="confirmed"
                    emptyMessage="No upcoming appointments."
                />
            </TabsContent>

            <TabsContent value="pending" className="mt-4">
                <AppointmentsTabContent
                    status="pending"
                    emptyMessage="No pending requests. New booking requests will appear here."
                />
            </TabsContent>

            <TabsContent value="completed" className="mt-4">
                <AppointmentsTabContent
                    status="completed"
                    emptyMessage="No past appointments."
                />
            </TabsContent>

            <TabsContent value="cancelled" className="mt-4">
                <AppointmentsTabContent
                    status="cancelled"
                    emptyMessage="No cancelled appointments."
                />
            </TabsContent>

            <TabsContent value="expired" className="mt-4">
                <AppointmentsTabContent
                    status="expired"
                    emptyMessage="No expired requests."
                />
            </TabsContent>
        </Tabs>
    )
}
