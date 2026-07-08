"use client"

import { use, useEffect, useState, useSyncExternalStore } from "react"
import {
    addMonths,
    eachDayOfInterval,
    endOfMonth,
    format,
    getDate,
    getDay,
    isBefore,
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import type { PublicAppointmentView, TimeSlot } from "@/lib/api/appointments"
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
type TimezoneOption = { value: string; label: string }

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
}: {
    title: string
    message: string
    centered?: boolean
    mutedIcon?: boolean
}) {
    const content = (
        <Card className={centered ? "max-w-md" : undefined}>
            <CardContent className="pt-6 text-center">
                <AlertCircleIcon
                    className={`size-12 mx-auto mb-4 ${mutedIcon ? "text-muted-foreground" : "text-destructive"}`}
                />
                <h2 className="text-xl font-semibold mb-2">{title}</h2>
                <p className="text-muted-foreground">{message}</p>
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

function ManageSuccessState({ status }: { status: "rescheduled" | "cancelled" }) {
    const title = status === "rescheduled" ? "Appointment Rescheduled" : "Appointment Cancelled"
    const message =
        status === "rescheduled"
            ? "Your appointment has been updated. You will receive a confirmation email shortly."
            : "Your appointment has been cancelled. You will receive a confirmation email shortly."

    return (
        <div className="min-h-screen bg-background py-12">
            <div className="max-w-lg mx-auto px-4">
                <Card>
                    <CardContent className="pt-6 text-center">
                        <div className="size-16 mx-auto rounded-full bg-green-500/10 flex items-center justify-center mb-6">
                            <CheckCircleIcon className="size-8 text-green-600" />
                        </div>
                        <h2 className="text-2xl font-semibold mb-2">{title}</h2>
                        <p className="text-muted-foreground">{message}</p>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}

function AppointmentSummary({ appointment }: { appointment: PublicAppointmentView | null }) {
    if (!appointment) return null

    return (
        <div className="rounded-lg border border-border p-4 space-y-2">
            <p className="font-medium">{appointment.appointment_type_name || "Appointment"}</p>
            {appointment.staff_name ? (
                <p className="text-sm text-muted-foreground">with {appointment.staff_name}</p>
            ) : null}
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <CalendarIcon className="size-4" />
                {format(parseISO(appointment.scheduled_start), "EEEE, MMMM d, yyyy")}
            </div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <ClockIcon className="size-4" />
                {format(parseISO(appointment.scheduled_start), "h:mm a")} (
                {appointment.duration_minutes} min)
            </div>
        </div>
    )
}

function AppointmentActionToggle({
    action,
    onActionChange,
}: {
    action: ManageAction
    onActionChange: (action: ManageAction) => void
}) {
    return (
        <div className="inline-flex rounded-lg border border-border p-1">
            <Button
                type="button"
                variant={action === "reschedule" ? "default" : "ghost"}
                onClick={() => onActionChange("reschedule")}
                className="h-8 px-4"
            >
                Reschedule
            </Button>
            <Button
                type="button"
                variant={action === "cancel" ? "default" : "ghost"}
                onClick={() => onActionChange("cancel")}
                className="h-8 px-4"
            >
                Cancel
            </Button>
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
    slots,
    selectedSlot,
    onSlotSelect,
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
    slots: TimeSlot[]
    selectedSlot: TimeSlot | null
    onSlotSelect: (slot: TimeSlot) => void
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
                    <SelectTrigger className="w-auto h-8 text-sm">
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
                <p className="font-medium">Select New Date</p>
                <ManageCalendarGrid
                    viewMonth={viewMonth}
                    calendarDays={calendarDays}
                    selectedDate={selectedDate}
                    onViewMonthChange={onViewMonthChange}
                    onDateSelect={onDateSelect}
                />
            </div>

            <ManageSlotsGrid
                selectedDate={selectedDate}
                isLoadingSlots={isLoadingSlots}
                slots={slots}
                selectedSlot={selectedSlot}
                onSlotSelect={onSlotSelect}
            />

            <Button
                type="button"
                className="w-full"
                size="lg"
                disabled={!selectedSlot || isSubmitting}
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

function ManageSlotsGrid({
    selectedDate,
    isLoadingSlots,
    slots,
    selectedSlot,
    onSlotSelect,
}: {
    selectedDate: Date | null
    isLoadingSlots: boolean
    slots: TimeSlot[]
    selectedSlot: TimeSlot | null
    onSlotSelect: (slot: TimeSlot) => void
}) {
    if (!selectedDate) return null

    return (
        <div className="space-y-3">
            <p className="font-medium">Select New Time</p>
            {isLoadingSlots ? (
                <div className="py-8 flex items-center justify-center">
                    <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                </div>
            ) : slots.length === 0 ? (
                <p className="text-muted-foreground text-center py-4">
                    No available times for this date
                </p>
            ) : (
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 max-h-64 overflow-y-auto">
                    {slots.map((slot) => {
                        const timeLabel = format(parseISO(slot.start), "h:mm a")
                        const isSelected = selectedSlot?.start === slot.start
                        return (
                            <Button
                                key={slot.start}
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={() => onSlotSelect(slot)}
                                className={`py-2 px-3 h-auto text-sm font-medium ${
                                    isSelected
                                        ? "border-primary bg-primary text-primary-foreground hover:bg-primary/90"
                                        : "hover:border-primary/50"
                                }`}
                            >
                                {timeLabel}
                            </Button>
                        )
                    })}
                </div>
            )}
        </div>
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

    const [loadState, setLoadState] = useState<{
        appointment: PublicAppointmentView | null
        isLoading: boolean
        error: string | null
    }>({
        appointment: null,
        isLoading: true,
        error: null,
    })

    const [action, setAction] = useState<ManageAction>(() => initialAction)
    const hasManageLink = Boolean(orgId && token)
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
    const [slots, setSlots] = useState<TimeSlot[]>([])
    const [isLoadingSlots, setIsLoadingSlots] = useState(false)

    const [reason, setReason] = useState("")
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [successState, setSuccessState] = useState<"rescheduled" | "cancelled" | null>(null)
    const appointment = hasManageLink ? loadState.appointment : null
    const isLoading = hasManageLink ? loadState.isLoading : false
    const error = hasManageLink ? loadState.error : INVALID_MANAGE_LINK_MESSAGE
    const appointmentTimezone = appointment?.client_timezone ?? null
    const timezone = timezoneOverride ?? appointmentTimezone ?? detectedTimezone

    useEffect(() => {
        if (!orgId || !token) {
            return
        }

        const orgIdForCall = orgId
        const tokenForCall = token

        async function load() {
            try {
                const data = await getAppointmentForManage(orgIdForCall, tokenForCall)
                setLoadState({
                    appointment: data,
                    isLoading: false,
                    error: null,
                })
            } catch (err: unknown) {
                setLoadState({
                    appointment: null,
                    isLoading: false,
                    error: err instanceof Error ? err.message : "Appointment not found",
                })
            }
        }

        void load()
    }, [orgId, token])

    const timezoneOptions = TIMEZONE_OPTIONS.some((opt) => opt.value === timezone)
        ? TIMEZONE_OPTIONS
        : [...TIMEZONE_OPTIONS, { value: timezone, label: timezone }]

    const appointmentMonth = appointment?.scheduled_start
        ? startOfMonth(parseISO(appointment.scheduled_start))
        : null
    const viewMonth = viewMonthOverride ?? appointmentMonth

    const calendarDays: CalendarDay[] = []
    if (viewMonth && today) {
        const monthStart = startOfMonth(viewMonth)
        const startDay = getDay(monthStart)
        for (let i = 0; i < startDay; i++) {
            calendarDays.push({
                key: `empty-${format(monthStart, "yyyy-MM")}-${i + 1}`,
                date: null,
                isToday: false,
                isAvailable: false,
            })
        }

        for (const date of eachDayOfInterval({ start: monthStart, end: endOfMonth(viewMonth) })) {
            const weekday = getDay(date)
            const isWeekday = weekday >= 1 && weekday <= 5
            calendarDays.push({
                key: `date-${format(date, "yyyy-MM-dd")}`,
                date,
                isToday: isSameDay(date, today),
                isAvailable: isWeekday && !isBefore(date, today),
            })
        }
    }

    const loadSlotsForDate = async (date: Date) => {
        setSelectedDate(date)
        setSelectedSlot(null)
        setIsLoadingSlots(true)

        try {
            if (!orgId || !token) {
                throw new Error("Invalid appointment management link")
            }
            const dateString = format(date, "yyyy-MM-dd")
            const response = await getRescheduleSlotsByToken(
                orgId,
                token,
                dateString,
                dateString,
                timezone
            )
            setSlots(response.slots)
        } catch {
            setSlots([])
        } finally {
            setIsLoadingSlots(false)
        }
    }

    const handleReschedule = async () => {
        if (!selectedSlot || !orgId || !token) return
        setIsSubmitting(true)
        setLoadState((prev) => ({ ...prev, error: null }))
        try {
            await rescheduleByManageToken(orgId, token, selectedSlot.start)
            setSuccessState("rescheduled")
        } catch (err: unknown) {
            setLoadState((prev) => ({
                ...prev,
                error: err instanceof Error ? err.message : "Failed to reschedule appointment",
            }))
        } finally {
            setIsSubmitting(false)
        }
    }

    const handleCancel = async () => {
        if (!orgId || !token) return
        setIsSubmitting(true)
        setLoadState((prev) => ({ ...prev, error: null }))
        try {
            await cancelByManageToken(orgId, token, reason || undefined)
            setSuccessState("cancelled")
        } catch (err: unknown) {
            setLoadState((prev) => ({
                ...prev,
                error: err instanceof Error ? err.message : "Failed to cancel appointment",
            }))
        } finally {
            setIsSubmitting(false)
        }
    }

    if (isLoading) {
        return <ManageLoadingState />
    }

    if (error && !appointment) {
        return (
            <ManageErrorState
                title="Unable to Manage Appointment"
                message={error}
            />
        )
    }

    if (successState) {
        return <ManageSuccessState status={successState} />
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
                    <CardHeader>
                        <CardTitle>Manage Appointment</CardTitle>
                        <CardDescription>
                            Reschedule to a new time or cancel this appointment.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <AppointmentSummary appointment={appointment} />

                        <AppointmentActionToggle action={action} onActionChange={setAction} />

                        {action === "reschedule" ? (
                            <ReschedulePanel
                                timezone={timezone}
                                timezoneOptions={timezoneOptions}
                                onTimezoneChange={setTimezoneOverride}
                                viewMonth={viewMonth}
                                onViewMonthChange={setViewMonthOverride}
                                calendarDays={calendarDays}
                                selectedDate={selectedDate}
                                onDateSelect={(date) => void loadSlotsForDate(date)}
                                isLoadingSlots={isLoadingSlots}
                                slots={slots}
                                selectedSlot={selectedSlot}
                                onSlotSelect={setSelectedSlot}
                                isSubmitting={isSubmitting}
                                onConfirm={() => void handleReschedule()}
                            />
                        ) : (
                            <CancelPanel
                                reason={reason}
                                onReasonChange={setReason}
                                isSubmitting={isSubmitting}
                                onCancel={() => void handleCancel()}
                            />
                        )}

                        {error ? (
                            <p className="text-sm text-destructive text-center">{error}</p>
                        ) : null}
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
