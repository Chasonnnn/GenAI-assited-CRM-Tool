"use client"

import { use, useState, useSyncExternalStore } from "react"
import { useQuery } from "@tanstack/react-query"
import { ApiError } from "@/lib/api"
import {
    addMonths,
    eachDayOfInterval,
    endOfMonth,
    format,
    getDate,
    getDay,
    isSameDay,
    parseISO,
    startOfDay,
    startOfMonth,
} from "date-fns"
import {
    AlertCircleIcon,
    CalendarIcon,
    CheckCircleIcon,
    ChevronLeftIcon,
    ChevronRightIcon,
    ClockIcon,
    GlobeIcon,
    Loader2Icon,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { SchedulingSlotList } from "@/components/appointments/SchedulingTimePicker"
import { formatSchedulingDate, formatSchedulingTime, schedulingDateKey } from "@/lib/scheduling-time"
import type { PublicAppointmentView, TimeSlot } from "@/lib/api/appointments"
import { createSchedulingRequestId } from "@/lib/api/appointments"
import {
    cancelByManageToken,
    getAppointmentForManage,
    getRescheduleSlotsByToken,
    rescheduleByManageToken,
} from "@/lib/api/appointments"

const TIMEZONE_OPTIONS = [
    { value: "America/Los_Angeles", label: "Pacific Time (US)" },
    { value: "America/Phoenix", label: "Arizona (US)" },
    { value: "America/Denver", label: "Mountain Time (US)" },
    { value: "America/Chicago", label: "Central Time (US)" },
    { value: "America/New_York", label: "Eastern Time (US)" },
    { value: "America/Anchorage", label: "Alaska (US)" },
    { value: "Pacific/Honolulu", label: "Hawaii (US)" },
    { value: "America/Vancouver", label: "Vancouver" },
    { value: "America/Toronto", label: "Toronto" },
    { value: "America/Mexico_City", label: "Mexico City" },
    { value: "America/Sao_Paulo", label: "Sao Paulo" },
    { value: "America/Argentina/Buenos_Aires", label: "Buenos Aires" },
    { value: "Europe/London", label: "London" },
    { value: "Europe/Paris", label: "Paris" },
    { value: "Europe/Berlin", label: "Berlin" },
    { value: "Europe/Madrid", label: "Madrid" },
    { value: "Africa/Johannesburg", label: "Johannesburg" },
    { value: "Africa/Lagos", label: "Lagos" },
    { value: "Asia/Dubai", label: "Dubai" },
    { value: "Asia/Karachi", label: "Karachi" },
    { value: "Asia/Kolkata", label: "India (Kolkata)" },
    { value: "Asia/Singapore", label: "Singapore" },
    { value: "Asia/Tokyo", label: "Tokyo" },
    { value: "Australia/Sydney", label: "Sydney" },
    { value: "Pacific/Auckland", label: "Auckland" },
    { value: "UTC", label: "UTC" },
]

const DEFAULT_TIMEZONE = "America/Los_Angeles"
const INVALID_MANAGE_LINK_MESSAGE = "Invalid appointment management link"
const UUID_PATTERN =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
type TimezoneOption = { value: string; label: string }

function isValidOrganizationId(value: string | undefined): value is string {
    return typeof value === "string" && UUID_PATTERN.test(value)
}

function getTimezoneLabel(value: string | null | undefined, options: TimezoneOption[] = TIMEZONE_OPTIONS) {
    if (!value) return "Select timezone"
    return options.find((option) => option.value === value)?.label ?? value
}

type ManageAction = "reschedule" | "cancel"

type SearchParams = {
    action?: string | string[]
}

let todaySnapshot: Date | null = null

function subscribeTodaySnapshot() {
    return () => {}
}

function getTodaySnapshot() {
    todaySnapshot ??= startOfDay(new Date())
    return todaySnapshot
}

function getServerTodaySnapshot() {
    return null
}

function subscribeTimezoneSnapshot() {
    return () => {}
}

function getTimezoneSnapshot() {
    try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || DEFAULT_TIMEZONE
    } catch {
        return DEFAULT_TIMEZONE
    }
}

function getServerTimezoneSnapshot() {
    return DEFAULT_TIMEZONE
}

type CalendarDay = {
    key: string
    date: Date | null
    isToday: boolean
    isAvailable: boolean
}

function ManageLoadingState() {
    return (
        <div className="min-h-screen flex items-center justify-center bg-background">
            <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
        </div>
    )
}

function ManageErrorState({
    title,
    message,
    centered = true,
    mutedIcon = false,
    onRetry,
}: {
    title: string
    message: string
    centered?: boolean
    mutedIcon?: boolean
    onRetry?: () => void
}) {
    const content = (
        <Card className={centered ? "max-w-md" : undefined}>
            <CardContent className="pt-6 text-center">
                <AlertCircleIcon
                    className={`size-12 mx-auto mb-4 ${mutedIcon ? "text-muted-foreground" : "text-destructive"}`}
                />
                <h2 className="text-xl font-semibold mb-2">{title}</h2>
                <p className="text-muted-foreground">{message}</p>
                {onRetry ? <Button type="button" variant="outline" className="mt-4" onClick={onRetry}>Retry</Button> : null}
            </CardContent>
        </Card>
    )

    if (centered) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                {content}
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-background py-12">
            <div className="max-w-lg mx-auto px-4">{content}</div>
        </div>
    )
}

function ManageSuccessState({ status, appointment, timezone }: { status: "rescheduled" | "cancelled"; appointment: PublicAppointmentView | null; timezone: string }) {
    const title = status === "rescheduled" ? "Appointment Rescheduled" : "Appointment Cancelled"

    return (
        <div className="min-h-screen bg-background py-12">
            <div className="max-w-lg mx-auto px-4">
                <Card>
                    <CardContent className="pt-6 text-center">
                        <div className="size-16 mx-auto rounded-full bg-green-500/10 flex items-center justify-center mb-6">
                            <CheckCircleIcon className="size-8 text-green-600" />
                        </div>
                        <h2 className="text-2xl font-semibold mb-2">{title}</h2>
                        {status === "rescheduled" && appointment ? (
                            <p className="text-muted-foreground">{formatSchedulingDate(appointment.scheduled_start, timezone)} · {formatSchedulingTime(appointment.scheduled_start, timezone)} · {getTimezoneLabel(timezone)}</p>
                        ) : null}
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}

function AppointmentSummary({ appointment, timezone }: { appointment: PublicAppointmentView | null; timezone: string }) {
    if (!appointment) return null

    return (
        <div className="rounded-lg border border-border p-4 space-y-2">
            <p className="font-medium">{appointment.appointment_type_name || "Appointment"}</p>
            {appointment.staff_name ? (
                <p className="text-sm text-muted-foreground">with {appointment.staff_name}</p>
            ) : null}
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <CalendarIcon className="size-4" />
                {formatSchedulingDate(appointment.scheduled_start, timezone)}
            </div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <ClockIcon className="size-4" />
                {formatSchedulingTime(appointment.scheduled_start, timezone)} · {getTimezoneLabel(timezone)} · {appointment.duration_minutes} min
            </div>
        </div>
    )
}

function AppointmentActionToggle({
    action,
    onActionChange,
    canReschedule,
    canCancel,
}: {
    action: ManageAction | null
    onActionChange: (action: ManageAction) => void
    canReschedule: boolean
    canCancel: boolean
}) {
    return (
        <div className="inline-flex rounded-lg border border-border p-1">
            {canReschedule ? <Button
                type="button"
                variant={action === "reschedule" ? "default" : "ghost"}
                onClick={() => onActionChange("reschedule")}
                className="h-8 px-4"
            >
                Reschedule
            </Button> : null}
            {canCancel ? <Button
                type="button"
                variant={action === "cancel" ? "default" : "ghost"}
                onClick={() => onActionChange("cancel")}
                className="h-8 px-4"
            >
                Cancel
            </Button> : null}
        </div>
    )
}

function ReschedulePanel({
    timezone,
    timezoneOptions,
    onTimezoneChange,
    viewMonth,
    onViewMonthChange,
    calendarDays,
    selectedDate,
    onDateSelect,
    isLoadingSlots,
    slotsError,
    slots,
    selectedSlot,
    onSlotSelect,
    onRetrySlots,
    isSubmitting,
    onConfirm,
}: {
    timezone: string
    timezoneOptions: TimezoneOption[]
    onTimezoneChange: (timezone: string) => void
    viewMonth: Date | null
    onViewMonthChange: (month: Date) => void
    calendarDays: CalendarDay[]
    selectedDate: Date | null
    onDateSelect: (date: Date) => void
    isLoadingSlots: boolean
    slotsError: boolean
    slots: TimeSlot[]
    selectedSlot: TimeSlot | null
    onSlotSelect: (slot: TimeSlot) => void
    onRetrySlots: () => void
    isSubmitting: boolean
    onConfirm: () => void
}) {
    return (
        <div className="space-y-5">
            <div className="flex items-center gap-2 text-sm">
                <GlobeIcon className="size-4 text-muted-foreground" />
                <span className="text-muted-foreground">Timezone:</span>
                <Select
                    value={timezone}
                    onValueChange={(value) => {
                        if (value) onTimezoneChange(value)
                    }}
                >
                    <SelectTrigger className="w-auto h-8 text-sm" aria-label="Timezone">
                        <SelectValue>
                            {(value: string | null) => getTimezoneLabel(value, timezoneOptions)}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        {timezoneOptions.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                                {option.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            <div className="space-y-3">
                <p className="font-medium">Select a date</p>
                <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <ManageCalendarGrid
                    viewMonth={viewMonth}
                    calendarDays={calendarDays}
                    selectedDate={selectedDate}
                    onViewMonthChange={onViewMonthChange}
                    onDateSelect={onDateSelect}
                />
                <div className="space-y-2">
                    <p className="font-medium">Select a time</p>
                    {selectedDate ? <SchedulingSlotList
                        slots={slots}
                        timezone={timezone}
                        selectedStart={selectedSlot?.start ?? null}
                        onSelectStart={(start) => { const slot = slots.find((item) => item.start === start); if (slot) onSlotSelect(slot) }}
                        loading={isLoadingSlots}
                        error={slotsError ? "Calendar availability is unavailable." : null}
                        onRetry={onRetrySlots}
                    /> : <p className="py-4 text-sm text-muted-foreground">Choose a date.</p>}
                </div>
                </div>
            </div>

            <Button
                type="button"
                className="w-full"
                size="lg"
                disabled={!selectedSlot || isLoadingSlots || slotsError || isSubmitting}
                onClick={onConfirm}
            >
                {isSubmitting ? <Loader2Icon className="size-4 mr-2 animate-spin" /> : null}
                Confirm Reschedule
            </Button>
        </div>
    )
}

function ManageCalendarGrid({
    viewMonth,
    calendarDays,
    selectedDate,
    onViewMonthChange,
    onDateSelect,
}: {
    viewMonth: Date | null
    calendarDays: CalendarDay[]
    selectedDate: Date | null
    onViewMonthChange: (month: Date) => void
    onDateSelect: (date: Date) => void
}) {
    return (
        <Card>
            <CardContent className="pt-4">
                <div className="flex items-center justify-between mb-4">
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        aria-label="Previous month"
                        disabled={!viewMonth}
                        onClick={() => {
                            if (viewMonth) onViewMonthChange(addMonths(viewMonth, -1))
                        }}
                    >
                        <ChevronLeftIcon className="size-4" />
                    </Button>
                    <span className="font-medium">
                        {viewMonth ? format(viewMonth, "MMMM yyyy") : "Loading calendar"}
                    </span>
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        aria-label="Next month"
                        disabled={!viewMonth}
                        onClick={() => {
                            if (viewMonth) onViewMonthChange(addMonths(viewMonth, 1))
                        }}
                    >
                        <ChevronRightIcon className="size-4" />
                    </Button>
                </div>

                <div className="grid grid-cols-7 text-center text-sm text-muted-foreground mb-2">
                    {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => (
                        <div key={day} className="py-2">
                            {day}
                        </div>
                    ))}
                </div>

                <div className="grid grid-cols-7 gap-1">
                    {calendarDays.map((day) => {
                        if (!day.date) {
                            return <div key={day.key} className="h-10" />
                        }
                        const isSelected = selectedDate ? isSameDay(day.date, selectedDate) : false
                        return (
                            <Button
                                key={day.key}
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                    if (day.isAvailable && day.date) {
                                        onDateSelect(day.date)
                                    }
                                }}
                                disabled={!day.isAvailable}
                                aria-pressed={isSelected}
                                className={`h-10 text-sm font-medium ${
                                    isSelected
                                        ? "bg-primary text-primary-foreground hover:bg-primary/90"
                                        : day.isToday
                                          ? "bg-primary/10 text-primary hover:bg-primary/20"
                                          : day.isAvailable
                                            ? "hover:bg-muted"
                                            : "text-muted-foreground/40"
                                }`}
                            >
                                {getDate(day.date)}
                            </Button>
                        )
                    })}
                </div>
            </CardContent>
        </Card>
    )
}

function CancelPanel({
    reason,
    onReasonChange,
    isSubmitting,
    onCancel,
}: {
    reason: string
    onReasonChange: (reason: string) => void
    isSubmitting: boolean
    onCancel: () => void
}) {
    return (
        <div className="space-y-4">
            <div className="space-y-2">
                <Label htmlFor="cancel-reason">Reason for cancellation (optional)</Label>
                <Textarea
                    id="cancel-reason"
                    value={reason}
                    onChange={(event) => onReasonChange(event.target.value)}
                    placeholder="Let us know why you're cancelling..."
                    rows={3}
                />
            </div>

            <Button
                type="button"
                variant="destructive"
                className="w-full"
                size="lg"
                disabled={isSubmitting}
                onClick={onCancel}
            >
                {isSubmitting ? <Loader2Icon className="size-4 mr-2 animate-spin" /> : null}
                Cancel Appointment
            </Button>
        </div>
    )
}

interface PageProps {
    params: Promise<{ orgId?: string | string[]; token?: string | string[] }>
    searchParams: Promise<SearchParams>
}

export default function ManageAppointmentPage({ params, searchParams }: PageProps) {
    const resolvedParams = use(params)
    const resolvedSearchParams = use(searchParams)

    const rawOrgId = resolvedParams.orgId
    const rawToken = resolvedParams.token
    const orgId = Array.isArray(rawOrgId) ? rawOrgId[0] : rawOrgId
    const token = Array.isArray(rawToken) ? rawToken[0] : rawToken

    const rawAction = Array.isArray(resolvedSearchParams.action)
        ? resolvedSearchParams.action[0]
        : resolvedSearchParams.action
    const initialAction: ManageAction = rawAction === "cancel" ? "cancel" : "reschedule"

    return (
        <ManageAppointmentSession
            key={`${orgId ?? "missing-org"}:${token ?? "missing-token"}`}
            orgId={orgId}
            token={token}
            initialAction={initialAction}
        />
    )
}

function ManageAppointmentSession({
    orgId,
    token,
    initialAction,
}: {
    orgId: string | undefined
    token: string | undefined
    initialAction: ManageAction
}) {
    const [action, setAction] = useState<ManageAction>(() => initialAction)
    const hasManageLink = isValidOrganizationId(orgId) && Boolean(token)
    const appointmentQuery = useQuery({
        queryKey: ["public", "manage-appointment", orgId ?? null, token ?? null],
        queryFn: () => {
            if (!orgId || !token) throw new Error(INVALID_MANAGE_LINK_MESSAGE)
            return getAppointmentForManage(orgId, token)
        },
        enabled: hasManageLink,
        retry: false,
    })
    const detectedTimezone = useSyncExternalStore(
        subscribeTimezoneSnapshot,
        getTimezoneSnapshot,
        getServerTimezoneSnapshot
    )
    const [timezoneOverride, setTimezoneOverride] = useState<string | null>(null)
    const [viewMonthOverride, setViewMonthOverride] = useState<Date | null>(null)
    const today = useSyncExternalStore(subscribeTodaySnapshot, getTodaySnapshot, getServerTodaySnapshot)
    const [selectedDate, setSelectedDate] = useState<Date | null>(null)
    const [selectedSlot, setSelectedSlot] = useState<TimeSlot | null>(null)
    const [reason, setReason] = useState("")
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [submissionError, setSubmissionError] = useState<string | null>(null)
    const [successState, setSuccessState] = useState<"rescheduled" | "cancelled" | null>(null)
    const [updatedAppointment, setUpdatedAppointment] = useState<PublicAppointmentView | null>(null)
    const appointment = hasManageLink ? appointmentQuery.data ?? null : null
    const isLoading = hasManageLink ? appointmentQuery.isLoading : false
    const queryError = hasManageLink
        ? appointmentQuery.error instanceof Error
            ? appointmentQuery.error.message
            : appointmentQuery.isError
                ? "Appointment not found"
                : null
        : INVALID_MANAGE_LINK_MESSAGE
    const invalidTokenError = appointmentQuery.error instanceof ApiError
        ? [400, 401, 403, 404, 410, 422].includes(appointmentQuery.error.status)
        : appointmentQuery.error instanceof Error && /not found|invalid|expired/i.test(appointmentQuery.error.message)
    const canRetryAppointmentLoad = hasManageLink && appointmentQuery.isError && !invalidTokenError
    const error = submissionError ?? queryError
    const appointmentTimezone = appointment?.client_timezone ?? null
    const canReschedule = appointment?.manage_actions?.can_reschedule ?? appointment?.scheduling?.capabilities.can_reschedule ?? true
    const canCancel = appointment?.manage_actions?.can_cancel ?? appointment?.scheduling?.capabilities.can_cancel ?? true
    const selectedAction: ManageAction | null = !canReschedule && !canCancel
        ? null
        : action === "reschedule" && !canReschedule ? "cancel"
        : action === "cancel" && !canCancel ? "reschedule" : action
    const timezone = timezoneOverride ?? appointmentTimezone ?? detectedTimezone

    const timezoneOptions = TIMEZONE_OPTIONS.some((opt) => opt.value === timezone)
        ? TIMEZONE_OPTIONS
        : [...TIMEZONE_OPTIONS, { value: timezone, label: timezone }]

    const appointmentMonth = appointment?.scheduled_start
        ? startOfMonth(parseISO(schedulingDateKey(appointment.scheduled_start, timezone)))
        : null
    const viewMonth = viewMonthOverride ?? appointmentMonth
    const selectedDateKey = selectedDate ? format(selectedDate, "yyyy-MM-dd") : null
    const slotsQuery = useQuery({
        queryKey: ["public", "manage-slots", orgId ?? null, token ?? null, selectedDateKey, timezone],
        queryFn: () => getRescheduleSlotsByToken(orgId!, token!, selectedDateKey!, selectedDateKey!, timezone),
        enabled: Boolean(hasManageLink && selectedAction === "reschedule" && selectedDateKey),
        retry: false,
    })
    const slots = (slotsQuery.data?.slots ?? []).filter(
        (slot) => schedulingDateKey(slot.start, timezone) === selectedDateKey,
    )
    const isLoadingSlots = Boolean(selectedDateKey && slotsQuery.isLoading)
    const slotsError = Boolean(selectedDateKey && slotsQuery.isError)
    const validSelectedSlot = selectedSlot && !isLoadingSlots && !slotsError && slots.some((slot) => slot.start === selectedSlot.start)

    const calendarDays: CalendarDay[] = []
    if (viewMonth && today) {
        const monthStart = startOfMonth(viewMonth)
        const startDay = getDay(monthStart)
        const todayKey = schedulingDateKey(new Date(), timezone)
        for (let i = 0; i < startDay; i++) {
            calendarDays.push({
                key: `empty-${format(monthStart, "yyyy-MM")}-${i + 1}`,
                date: null,
                isToday: false,
                isAvailable: false,
            })
        }

        for (const date of eachDayOfInterval({ start: monthStart, end: endOfMonth(viewMonth) })) {
            const dateKey = format(date, "yyyy-MM-dd")
            calendarDays.push({
                key: `date-${format(date, "yyyy-MM-dd")}`,
                date,
                isToday: dateKey === todayKey,
                isAvailable: dateKey >= todayKey,
            })
        }
    }

    const selectDate = (date: Date) => {
        setSelectedDate(date)
        setSelectedSlot(null)
    }

    const handleReschedule = async () => {
        if (!validSelectedSlot || !selectedSlot || !orgId || !token) return
        setIsSubmitting(true)
        setSubmissionError(null)
        try {
            const updated = await rescheduleByManageToken(orgId, token, selectedSlot.start, {
                ...(appointment?.scheduling ? { expectedRevision: appointment.scheduling.revision, requestId: createSchedulingRequestId() } : {}),
            })
            setUpdatedAppointment(updated)
            setSuccessState("rescheduled")
        } catch (err: unknown) {
            setSubmissionError(
                err instanceof Error ? err.message : "Failed to reschedule appointment"
            )
        }
        setIsSubmitting(false)
    }

    const handleCancel = async () => {
        if (!orgId || !token) return
        setIsSubmitting(true)
        setSubmissionError(null)
        try {
            await cancelByManageToken(orgId, token, reason || undefined, {
                ...(appointment?.scheduling ? { expectedRevision: appointment.scheduling.revision, requestId: createSchedulingRequestId() } : {}),
            })
            setSuccessState("cancelled")
        } catch (err: unknown) {
            setSubmissionError(
                err instanceof Error ? err.message : "Failed to cancel appointment"
            )
        }
        setIsSubmitting(false)
    }

    if (isLoading) {
        return <ManageLoadingState />
    }

    if (error && !appointment) {
        return (
            <ManageErrorState
                title="Unable to Manage Appointment"
                message={canRetryAppointmentLoad ? "Unable to load this appointment. Please try again." : error}
                {...(canRetryAppointmentLoad ? { onRetry: () => { void appointmentQuery.refetch() } } : {})}
            />
        )
    }

    if (successState) {
        return <ManageSuccessState status={successState} appointment={updatedAppointment} timezone={timezone} />
    }

    if (appointment?.status === "cancelled") {
        return (
            <ManageErrorState
                title="Already Cancelled"
                message="This appointment has already been cancelled."
                centered={false}
                mutedIcon
            />
        )
    }

    return (
        <div className="min-h-screen bg-background py-12">
            <div className="max-w-2xl mx-auto px-4 space-y-6">
                <Card>
                    <CardHeader><CardTitle>Manage Appointment</CardTitle></CardHeader>
                    <CardContent className="space-y-4">
                        <AppointmentSummary appointment={appointment} timezone={timezone} />

                        <AppointmentActionToggle action={selectedAction} onActionChange={setAction} canReschedule={canReschedule} canCancel={canCancel} />

                        {selectedAction === "reschedule" && canReschedule ? (
                            <ReschedulePanel
                                timezone={timezone}
                                timezoneOptions={timezoneOptions}
                                onTimezoneChange={(value) => { setTimezoneOverride(value); setSelectedDate(null); setSelectedSlot(null); setViewMonthOverride(null) }}
                                viewMonth={viewMonth}
                                onViewMonthChange={setViewMonthOverride}
                                calendarDays={calendarDays}
                                selectedDate={selectedDate}
                                onDateSelect={selectDate}
                                isLoadingSlots={isLoadingSlots}
                                slotsError={slotsError}
                                slots={slots}
                                selectedSlot={selectedSlot}
                                onSlotSelect={setSelectedSlot}
                                onRetrySlots={() => void slotsQuery.refetch()}
                                isSubmitting={isSubmitting}
                                onConfirm={() => void handleReschedule()}
                            />
                        ) : selectedAction === "cancel" && canCancel ? (
                            <CancelPanel
                                reason={reason}
                                onReasonChange={setReason}
                                isSubmitting={isSubmitting}
                                onCancel={() => void handleCancel()}
                            />
                        ) : <p role="alert" className="text-sm text-destructive">This appointment can no longer be changed.</p>}

                        {error ? (
                            <p className="text-sm text-destructive text-center">{error}</p>
                        ) : null}
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
