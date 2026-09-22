"use client"

/**
 * Public Booking Page - Client-facing booking form
 * 
 * Features:
 * - Staff info display
 * - Appointment type selector
 * - Calendar date picker
 * - Time slot selector
 * - Booking form with validation
 * - Timezone detection and switching
 * - Confirmation view
 */

import { useReducer, useState, useSyncExternalStore } from "react"
import Link from "next/link"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { SchedulingSlotList } from "@/components/appointments/SchedulingTimePicker"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    CalendarIcon,
    ClockIcon,
    ChevronLeftIcon,
    ChevronRightIcon,
    VideoIcon,
    PhoneIcon,
    MapPinIcon,
    CheckCircleIcon,
    Loader2Icon,
    GlobeIcon,
} from "lucide-react"
import {
    usePublicBookingPage,
    useAvailableSlots,
    useCreateBooking,
    useBookingPreviewPage,
    useBookingPreviewSlots,
} from "@/lib/hooks/use-appointments"
import type {
    AppointmentType,
    TimeSlot,
    BookingCreate,
    PublicAppointmentView,
    MeetingMode,
} from "@/lib/api/appointments"
import { createSchedulingRequestId } from "@/lib/api/appointments"
import { ApiError } from "@/lib/api"
import { formatSchedulingDate, formatSchedulingTime, schedulingDateKey } from "@/lib/scheduling-time"
import { format, addDays } from "date-fns"
import { toast } from "@/components/ui/toast"
import {
    formatPlainDateKey,
    getTodayDateKeyInTimeZone,
    isPastDateKey,
} from "@/lib/utils/date-keys"

const DEFAULT_TIMEZONE = "America/Los_Angeles"

// Timezone options
const TIMEZONE_OPTIONS = [
    { value: DEFAULT_TIMEZONE, label: "Pacific Time (US)" },
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
    { value: "Europe/Dublin", label: "Dublin" },
    { value: "Europe/Paris", label: "Paris" },
    { value: "Europe/Berlin", label: "Berlin" },
    { value: "Europe/Rome", label: "Rome" },
    { value: "Europe/Madrid", label: "Madrid" },
    { value: "Europe/Amsterdam", label: "Amsterdam" },
    { value: "Africa/Johannesburg", label: "Johannesburg" },
    { value: "Africa/Lagos", label: "Lagos" },
    { value: "Africa/Cairo", label: "Cairo" },
    { value: "Asia/Dubai", label: "Dubai" },
    { value: "Asia/Riyadh", label: "Riyadh" },
    { value: "Asia/Karachi", label: "Karachi" },
    { value: "Asia/Kolkata", label: "India (Kolkata)" },
    { value: "Asia/Bangkok", label: "Bangkok" },
    { value: "Asia/Singapore", label: "Singapore" },
    { value: "Asia/Hong_Kong", label: "Hong Kong" },
    { value: "Asia/Shanghai", label: "Shanghai" },
    { value: "Asia/Tokyo", label: "Tokyo" },
    { value: "Asia/Seoul", label: "Seoul" },
    { value: "Australia/Perth", label: "Perth" },
    { value: "Australia/Sydney", label: "Sydney" },
    { value: "Australia/Melbourne", label: "Melbourne" },
    { value: "Pacific/Auckland", label: "Auckland" },
    { value: "UTC", label: "UTC" },
]

// Appointment format display
const MEETING_MODES: Record<MeetingMode, { icon: typeof VideoIcon; label: string }> = {
    zoom: { icon: VideoIcon, label: "Zoom Video Call" },
    google_meet: { icon: VideoIcon, label: "Google Meet" },
    phone: { icon: PhoneIcon, label: "Phone Call" },
    in_person: { icon: MapPinIcon, label: "In-Person Appointment" },
}

function getMeetingModeLabel(mode?: MeetingMode | null) {
    if (!mode) return "Appointment"
    return MEETING_MODES[mode]?.label || mode.replace(/_/g, " ")
}

function getMeetingModeIcon(mode?: MeetingMode | null) {
    return MEETING_MODES[mode ?? "zoom"]?.icon || VideoIcon
}

function getMeetingModes(type: AppointmentType | null | undefined): MeetingMode[] {
    if (!type) return []
    if (type.meeting_modes && type.meeting_modes.length > 0) {
        return type.meeting_modes
    }
    return type.meeting_mode ? [type.meeting_mode] : []
}

type BookingSelectionState = {
    selectedTypeId: string | null
    selectedDate: Date | null
    selectedSlot: TimeSlot | null
    selectedMeetingMode: MeetingMode | null
    showForm: boolean
}

type BookingSelectionAction =
    | { type: "selectType"; typeId: string; meetingModes: MeetingMode[] }
    | { type: "selectMeetingMode"; mode: MeetingMode }
    | { type: "selectDate"; date: Date | null }
    | { type: "selectSlot"; slot: TimeSlot }
    | { type: "showForm" }
    | { type: "hideForm" }

const initialBookingSelectionState: BookingSelectionState = {
    selectedTypeId: null,
    selectedDate: null,
    selectedSlot: null,
    selectedMeetingMode: null,
    showForm: false,
}

function getInitialSelectedMeetingMode(meetingModes: MeetingMode[]): MeetingMode | null {
    return meetingModes.length === 1 ? meetingModes[0] ?? null : null
}

function bookingSelectionReducer(
    state: BookingSelectionState,
    action: BookingSelectionAction,
): BookingSelectionState {
    switch (action.type) {
        case "selectType":
            return {
                ...initialBookingSelectionState,
                selectedTypeId: action.typeId,
                selectedMeetingMode: getInitialSelectedMeetingMode(action.meetingModes),
            }
        case "selectMeetingMode":
            return { ...state, selectedMeetingMode: action.mode, showForm: false }
        case "selectDate":
            return { ...state, selectedDate: action.date, selectedSlot: null, showForm: false }
        case "selectSlot":
            return { ...state, selectedSlot: action.slot, showForm: false }
        case "showForm":
            return { ...state, showForm: true }
        case "hideForm":
            return { ...state, showForm: false }
        default:
            return state
    }
}

type BookingCalendarDay = {
    cellKey: string
    date: Date | null
    dateKey: string | null
    isToday: boolean
    hasSlots: boolean
}

function buildCalendarDays(
    viewMonth: Date,
    availableDates: Set<string>,
    timezone: string
): BookingCalendarDay[] {
    const start = new Date(viewMonth.getFullYear(), viewMonth.getMonth(), 1)
    const startDay = start.getDay() // 0 = Sunday
    const daysInMonth = new Date(viewMonth.getFullYear(), viewMonth.getMonth() + 1, 0).getDate()
    const monthKey = format(viewMonth, "yyyy-MM")

    const result: BookingCalendarDay[] = []

    // Padding for days before month starts
    for (let i = 0; i < startDay; i++) {
        result.push({
            cellKey: `${monthKey}-padding-${i}`,
            date: null,
            dateKey: null,
            isToday: false,
            hasSlots: false,
        })
    }

    const todayKey = getTodayDateKeyInTimeZone(timezone)
    for (let d = 1; d <= daysInMonth; d++) {
        const date = new Date(viewMonth.getFullYear(), viewMonth.getMonth(), d)
        const dateKey = formatPlainDateKey(date)
        result.push({
            cellKey: dateKey,
            date,
            dateKey,
            isToday: dateKey === todayKey,
            hasSlots: availableDates.has(dateKey) && !isPastDateKey(dateKey, timezone),
        })
    }

    return result
}

function getTimezoneOptions(timezone: string) {
    if (TIMEZONE_OPTIONS.some((opt) => opt.value === timezone)) {
        return TIMEZONE_OPTIONS
    }
    return [...TIMEZONE_OPTIONS, { value: timezone, label: timezone }]
}

function getTimezoneLabel(timezone: string) {
    return getTimezoneOptions(timezone).find((option) => option.value === timezone)?.label ?? timezone
}

function getInitialBookingDateRange(timezone: string) {
    const start = getTodayDateKeyInTimeZone(timezone)
    const end = format(addDays(new Date(`${start}T12:00:00`), 30), "yyyy-MM-dd")
    return { start, end }
}

function subscribeTimezoneSnapshot() {
    return () => {}
}

function getInitialClientTimezone() {
    try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || DEFAULT_TIMEZONE
    } catch {
        return DEFAULT_TIMEZONE
    }
}

function getServerTimezoneSnapshot() {
    return DEFAULT_TIMEZONE
}

function getEffectiveBookingTimezone(
    timezoneOverride: string | null,
    orgTimezone: string | null | undefined,
    detectedTimezone: string
) {
    if (timezoneOverride) return timezoneOverride
    if (detectedTimezone === DEFAULT_TIMEZONE && orgTimezone) return orgTimezone
    return detectedTimezone
}

function getAvailableDates(slots: TimeSlot[] | undefined, timezone: string) {
    const dates = new Set<string>()
    slots?.forEach((slot) => {
        dates.add(schedulingDateKey(slot.start, timezone))
    })
    return dates
}

function getSlotsForDate(selectedDate: Date | null, slots: TimeSlot[] | undefined, timezone: string) {
    if (!selectedDate || !slots) return []
    const dateStr = formatPlainDateKey(selectedDate)
    return slots.filter((slot) =>
        schedulingDateKey(slot.start, timezone) === dateStr
    )
}

function hashIdempotencyKey(input: string) {
    let hash = 0x811c9dc5
    for (let i = 0; i < input.length; i += 1) {
        hash ^= input.charCodeAt(i)
        hash = Math.imul(hash, 0x01000193)
    }
    return (hash >>> 0).toString(16).padStart(8, "0")
}

function buildIdempotencyKey(email: string, scheduledStart: string, appointmentTypeId: string) {
    const raw = `${email}-${scheduledStart}-${appointmentTypeId}`
    if (raw.length <= 64) return raw
    return `bk_${hashIdempotencyKey(raw)}`
}

type BookingSubmissionError = { message: string; field?: "client_email" }

function getBookingSubmissionError(error: unknown): BookingSubmissionError {
    if (error instanceof ApiError) {
        if (error.status === 422 && /email/i.test(error.message)) {
            return { message: "Enter a valid email address.", field: "client_email" }
        }
        if (error.status === 422 || error.status === 400) {
            return { message: "Check your details and try again." }
        }
        if (error.status === 409) {
            return { message: "This time is no longer available. Choose another time." }
        }
        if (error.status === 429) {
            return { message: "Too many attempts. Please try again later." }
        }
    }
    return { message: "Booking could not be completed. Please try again." }
}

// =============================================================================
// Staff Card
// =============================================================================

function StaffCard({
    displayName,
    avatarUrl,
    orgName,
}: {
    displayName: string
    avatarUrl: string | null
    orgName: string | null
}) {
    const initials = displayName
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)

    return (
        <div className="flex items-center gap-4 mb-6">
            <Avatar className="size-16">
                {avatarUrl && <AvatarImage src={avatarUrl} alt={displayName} />}
                <AvatarFallback className="text-lg bg-primary/10 text-primary">
                    {initials}
                </AvatarFallback>
            </Avatar>
            <div>
                <h2 className="text-xl font-semibold">{displayName}</h2>
                {orgName && <p className="text-muted-foreground">{orgName}</p>}
            </div>
        </div>
    )
}

// =============================================================================
// Appointment Type Selector
// =============================================================================

function AppointmentTypeSelector({
    types,
    selectedId,
    onSelect,
}: {
    types: AppointmentType[]
    selectedId: string | null
    onSelect: (id: string) => void
}) {
    return (
        <div className="space-y-2">
            <Label className="font-medium">Appointment type</Label>
            <div className="grid gap-2 sm:grid-cols-2">
                {types.map((type) => {
                    const modes = getMeetingModes(type)
                    const primaryMode = modes[0] || type.meeting_mode
                    const isSelected = selectedId === type.id

                    return (
                        <Button
                            key={type.id}
                            variant="outline"
                            onClick={() => onSelect(type.id)}
                            aria-label={type.name}
                            aria-pressed={isSelected}
                            className={`flex items-center gap-3 p-3 h-auto min-w-0 rounded-lg text-left justify-start ${isSelected
                                ? "border-primary bg-primary/5 ring-2 ring-primary/20"
                                : "hover:border-primary/50 hover:bg-muted/50"
                                }`}
                        >
                            <div className="min-w-0 flex-1">
                                <h3 className="font-medium">{type.name}</h3>
                                <p className="text-sm text-muted-foreground">
                                    {type.duration_minutes} min · {modes.length > 1 ? "Choose format" : getMeetingModeLabel(primaryMode)}
                                </p>
                            </div>
                            {type.auto_approve && <Badge variant="secondary" className="shrink-0">Confirmed</Badge>}
                        </Button>
                    )
                })}
            </div>
        </div>
    )
}

// =============================================================================
// Meeting Mode Selector
// =============================================================================

function MeetingModeSelector({
    meetingModes,
    selectedMode,
    onSelect,
}: {
    meetingModes: MeetingMode[]
    selectedMode: MeetingMode | null
    onSelect: (mode: MeetingMode) => void
}) {
    return (
        <div className="space-y-2">
            <Label className="font-medium">Select Appointment Format</Label>
            <div className="flex flex-wrap gap-2">
                {meetingModes.map((mode) => {
                    const modeLabel = getMeetingModeLabel(mode)
                    const ModeIcon = getMeetingModeIcon(mode)
                    const isSelected = selectedMode === mode
                    return (
                        <Button
                            key={mode}
                            variant="outline"
                            onClick={() => onSelect(mode)}
                            aria-pressed={isSelected}
                            className={`flex items-center gap-2 px-3 py-2 h-auto rounded-lg text-left justify-start ${isSelected
                                ? "border-primary bg-primary/5 ring-2 ring-primary/20"
                                : "hover:border-primary/50 hover:bg-muted/50"
                                }`}
                        >
                            <ModeIcon className="size-4" aria-hidden="true" />
                            {modeLabel}
                        </Button>
                    )
                })}
            </div>
        </div>
    )
}

// =============================================================================
// Calendar View
// =============================================================================

function CalendarView({
    selectedDate,
    onSelect,
    availableDates,
    timezone,
}: {
    selectedDate: Date | null
    onSelect: (date: Date) => void
    availableDates: Set<string>
    timezone: string
}) {
    const [viewMonth, setViewMonth] = useState(() => new Date(`${getTodayDateKeyInTimeZone(timezone)}T12:00:00`))

    const days = buildCalendarDays(viewMonth, availableDates, timezone)

    const prevMonth = () => setViewMonth(new Date(viewMonth.getFullYear(), viewMonth.getMonth() - 1))
    const nextMonth = () => setViewMonth(new Date(viewMonth.getFullYear(), viewMonth.getMonth() + 1))

    return (
        <div className="space-y-4">
            <Label className="text-base font-medium">Select a Date</Label>
            <Card>
                <CardContent className="pt-4">
                    {/* Month Navigation */}
                    <div className="flex items-center justify-between mb-4">
                        <Button variant="ghost" size="sm" onClick={prevMonth} aria-label="Previous month">
                            <ChevronLeftIcon className="size-4" aria-hidden="true" />
                        </Button>
                        <span className="font-medium" aria-live="polite">{format(viewMonth, "MMMM yyyy")}</span>
                        <Button variant="ghost" size="sm" onClick={nextMonth} aria-label="Next month">
                            <ChevronRightIcon className="size-4" aria-hidden="true" />
                        </Button>
                    </div>

                    {/* Day Headers */}
                    <div className="grid grid-cols-7 text-center text-sm text-muted-foreground mb-2">
                        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
                            <div key={d} className="py-2">
                                {d}
                            </div>
                        ))}
                    </div>

                    {/* Days Grid */}
                    <div className="grid grid-cols-7 gap-1">
                        {days.map((day) => {
                            if (!day.date) {
                                return <div key={day.cellKey} className="h-10" />
                            }

                            const isSelected = selectedDate && day.dateKey === formatPlainDateKey(selectedDate)

                            return (
                                <Button
                                    key={day.cellKey}
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => day.hasSlots && onSelect(day.date!)}
                                    disabled={!day.hasSlots}
                                    aria-pressed={Boolean(isSelected)}
                                    className={`h-10 text-sm font-medium ${isSelected
                                        ? "bg-primary text-primary-foreground hover:bg-primary/90"
                                        : day.isToday
                                            ? "bg-primary/10 text-primary hover:bg-primary/20"
                                            : day.hasSlots
                                                ? "hover:bg-muted text-foreground"
                                                : "text-muted-foreground/40"
                                        }`}
                                >
                                    {day.date.getDate()}
                                </Button>
                            )
                        })}
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}

// =============================================================================
// Booking Form
// =============================================================================

function BookingForm({
    appointmentType,
    meetingMode,
    selectedSlot,
    timezone,
    onSubmit,
    onBack,
    isSubmitting,
    submissionError,
    onEdit,
}: {
    appointmentType: AppointmentType
    meetingMode: MeetingMode
    selectedSlot: TimeSlot
    timezone: string
    onSubmit: (data: Omit<BookingCreate, "appointment_type_id" | "scheduled_start" | "client_timezone">) => void
    onBack: () => void
    isSubmitting: boolean
    submissionError: BookingSubmissionError | null
    onEdit: () => void
}) {
    const [formData, setFormData] = useState({
        client_name: "",
        client_email: "",
        client_phone: "",
        client_notes: "",
    })
    const [errors, setErrors] = useState<Record<string, string>>({})

    const validate = () => {
        const newErrors: Record<string, string> = {}
        if (!formData.client_name.trim()) {
            newErrors.client_name = "Name is required"
        }
        if (!formData.client_email.trim()) {
            newErrors.client_email = "Email is required"
        } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.client_email)) {
            newErrors.client_email = "Invalid email address"
        }
        if (!formData.client_phone.trim()) {
            newErrors.client_phone = "Phone is required"
        }
        setErrors(newErrors)
        return Object.keys(newErrors).length === 0
    }

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        if (validate()) {
            onSubmit(formData)
        }
    }

    const mode = MEETING_MODES[meetingMode]
    const ModeIcon = mode?.icon || VideoIcon
    const isInPerson = meetingMode === "in_person"
    const isPhone = meetingMode === "phone"
    const emailError = errors.client_email || (submissionError?.field === "client_email" ? submissionError.message : null)

    return (
        <form onSubmit={handleSubmit} className="space-y-6">
            {/* Summary */}
            <Card className="bg-muted/50">
                <CardContent className="pt-4">
                    <div className="flex items-start justify-between">
                        <div>
                            <h3 className="font-medium">{appointmentType.name}</h3>
                            <p className="text-sm text-muted-foreground flex items-center gap-2 mt-1">
                                <CalendarIcon className="size-4" />
                                {formatSchedulingDate(selectedSlot.start, timezone)}
                            </p>
                            <p className="text-sm text-muted-foreground flex items-center gap-2">
                                <ClockIcon className="size-4" />
                                {formatSchedulingTime(selectedSlot.start, timezone)} · {getTimezoneLabel(timezone)} · {appointmentType.duration_minutes} min
                            </p>
                            <p className="text-sm text-muted-foreground flex items-center gap-2">
                                <ModeIcon className="size-4" />
                                {mode?.label || meetingMode}
                            </p>
                            {isInPerson && appointmentType.meeting_location && (
                                <p className="text-sm text-muted-foreground flex items-center gap-2">
                                    <MapPinIcon className="size-4" />
                                    {appointmentType.meeting_location}
                                </p>
                            )}
                            {isPhone && appointmentType.dial_in_number && (
                                <p className="text-sm text-muted-foreground flex items-center gap-2">
                                    <PhoneIcon className="size-4" />
                                    {appointmentType.dial_in_number}
                                </p>
                            )}
                        </div>
                        <Button type="button" variant="ghost" size="sm" onClick={onBack} disabled={isSubmitting}>
                            Change
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {/* Form Fields */}
            <div className="space-y-4">
                <h2 className="text-lg font-semibold">Your details</h2>
                <div className="space-y-2">
                    <Label htmlFor="name">Full name *</Label>
                    <Input
                        id="name"
                        value={formData.client_name}
                        onValueChange={(value) => { setFormData((current) => ({ ...current, client_name: value })); onEdit() }}
                        className={errors.client_name ? "border-destructive" : ""}
                    />
                    {errors.client_name && (
                        <p className="text-sm text-destructive">{errors.client_name}</p>
                    )}
                </div>

                <div className="space-y-2">
                    <Label htmlFor="email">Email *</Label>
                    <Input
                        id="email"
                        type="email"
                        value={formData.client_email}
                        onValueChange={(value) => { setFormData((current) => ({ ...current, client_email: value })); onEdit() }}
                        placeholder="your@email.com"
                        aria-invalid={Boolean(emailError)}
                        aria-describedby={emailError ? "email-error" : undefined}
                        className={emailError ? "border-destructive" : ""}
                    />
                    {emailError && (
                        <p id="email-error" role="alert" className="text-sm text-destructive">{emailError}</p>
                    )}
                </div>

                <div className="space-y-2">
                    <Label htmlFor="phone">Phone number *</Label>
                    <Input
                        id="phone"
                        type="tel"
                        value={formData.client_phone}
                        onValueChange={(value) => { setFormData((current) => ({ ...current, client_phone: value })); onEdit() }}
                        className={errors.client_phone ? "border-destructive" : ""}
                    />
                    {errors.client_phone && (
                        <p className="text-sm text-destructive">{errors.client_phone}</p>
                    )}
                </div>

                <div className="space-y-2">
                    <Label htmlFor="notes">Note (optional)</Label>
                    <Textarea
                        id="notes"
                        value={formData.client_notes}
                        onChange={(e) => { const value = e.currentTarget.value; setFormData((current) => ({ ...current, client_notes: value })); onEdit() }}
                        rows={2}
                    />
                </div>
            </div>

            {submissionError && submissionError.field !== "client_email" ? (
                <p role="alert" className="text-sm text-destructive">{submissionError.message}</p>
            ) : null}

            <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
                {isSubmitting && <Loader2Icon className="size-4 mr-2 animate-spin" />}
                {appointmentType.auto_approve ? "Confirm Appointment" : "Request Appointment"}
            </Button>

        </form>
    )
}

// Generate ICS file for calendar download
function generateICSFile(
    appointmentType: AppointmentType,
    startTime: string,
    timezone: string,
    staffName: string,
    meetingMode: MeetingMode,
    options?: {
        status?: string
        meetingLocation?: string | null
        dialInNumber?: string | null
        joinUrl?: string | null
    }
): string {
    const start = new Date(startTime)
    const end = new Date(start.getTime() + appointmentType.duration_minutes * 60 * 1000)

    // Format dates for ICS (YYYYMMDDTHHMMSSZ in UTC)
    const formatICSDate = (date: Date) => {
        return date.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '')
    }

    const meetingModeLabel = getMeetingModeLabel(meetingMode)
    const location = options?.meetingLocation || options?.dialInNumber || ""
    const status = options?.status === "confirmed" ? "confirmed" : "pending"
    const descriptionLines = [
        `Appointment format: ${meetingModeLabel}`,
        `Duration: ${appointmentType.duration_minutes} minutes`,
        status === "confirmed" ? "Status: Confirmed" : "Status: Pending approval",
    ]
    if (options?.meetingLocation) descriptionLines.push(`Location: ${options.meetingLocation}`)
    if (options?.dialInNumber) descriptionLines.push(`Dial-in: ${options.dialInNumber}`)
    if (options?.joinUrl) descriptionLines.push(`Join: ${options.joinUrl}`)

    const ics = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Surrogacy Force//Booking//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'BEGIN:VEVENT',
        `DTSTART:${formatICSDate(start)}`,
        `DTEND:${formatICSDate(end)}`,
        `SUMMARY:${appointmentType.name} with ${staffName}`,
        `DESCRIPTION:${descriptionLines.join("\\n")}`,
        location ? `LOCATION:${location}` : null,
        status === "confirmed" ? "STATUS:CONFIRMED" : "STATUS:TENTATIVE",
        `UID:${Date.now()}@crm-platform`,
        'END:VEVENT',
        'END:VCALENDAR',
    ]
        .filter((line): line is string => Boolean(line))
        .join('\r\n')

    return ics
}

function ConfirmationView({
    appointmentType,
    selectedSlot,
    timezone,
    staffName,
    confirmation,
    meetingMode,
}: {
    appointmentType: AppointmentType
    selectedSlot: TimeSlot
    timezone: string
    staffName: string
    confirmation: PublicAppointmentView | null
    meetingMode: MeetingMode
}) {
    const effectiveMeetingMode = confirmation?.meeting_mode || meetingMode
    const modeMeta = MEETING_MODES[effectiveMeetingMode]
    const ModeIcon = modeMeta?.icon || VideoIcon
    const isConfirmed = confirmation?.status === "confirmed"
    const meetingLocation = confirmation?.meeting_location ?? appointmentType.meeting_location
    const dialInNumber = confirmation?.dial_in_number ?? appointmentType.dial_in_number
    const joinUrl = confirmation?.zoom_join_url || confirmation?.google_meet_url || null
    const showLocation = effectiveMeetingMode === "in_person" && meetingLocation
    const showDialIn = effectiveMeetingMode === "phone" && dialInNumber

    const handleDownloadICS = () => {
        const ics = generateICSFile(appointmentType, confirmation?.scheduled_start ?? selectedSlot.start, timezone, staffName, effectiveMeetingMode, {
            ...(confirmation?.status ? { status: confirmation.status } : {}),
            meetingLocation,
            dialInNumber,
            joinUrl,
        })
        const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `appointment-${schedulingDateKey(confirmation?.scheduled_start ?? selectedSlot.start, timezone)}.ics`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        URL.revokeObjectURL(url)
    }

    return (
        <div className="text-center py-6">
            {/* Success Animation */}
            <div className="mb-6">
                <div className="size-20 mx-auto rounded-full bg-green-500/10 flex items-center justify-center animate-[pulse_2s_ease-in-out_1]">
                    <CheckCircleIcon className="size-10 text-green-600" />
                </div>
            </div>

            <h2 className="text-2xl font-semibold mb-2">
                {isConfirmed ? "Appointment Confirmed!" : "Request Submitted!"}
            </h2>

            {/* Appointment Summary Card */}
            <div className="bg-muted/50 rounded-lg p-4 mb-6 text-left">
                <h3 className="font-medium mb-3 text-sm text-muted-foreground uppercase tracking-wide">
                    Appointment Details
                </h3>
                <div className="space-y-3">
                    <div className="flex items-center gap-3">
                        <CalendarIcon className="size-5 text-muted-foreground flex-shrink-0" />
                        <div>
                            <p className="font-medium">{formatSchedulingDate(confirmation?.scheduled_start ?? selectedSlot.start, timezone)}</p>
                            <p className="text-sm text-muted-foreground">
                                {formatSchedulingTime(confirmation?.scheduled_start ?? selectedSlot.start, timezone)} · {getTimezoneLabel(timezone)}
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <ClockIcon className="size-5 text-muted-foreground flex-shrink-0" />
                        <div>
                            <p className="font-medium">{appointmentType.name}</p>
                            <p className="text-sm text-muted-foreground">{appointmentType.duration_minutes} minutes</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <ModeIcon className="size-5 text-muted-foreground flex-shrink-0" />
                        <p className="font-medium">{getMeetingModeLabel(effectiveMeetingMode)}</p>
                    </div>
                    {showLocation && (
                        <div className="flex items-center gap-3">
                            <MapPinIcon className="size-5 text-muted-foreground flex-shrink-0" />
                            <p className="font-medium">{meetingLocation}</p>
                        </div>
                    )}
                    {showDialIn && (
                        <div className="flex items-center gap-3">
                            <PhoneIcon className="size-5 text-muted-foreground flex-shrink-0" />
                            <p className="font-medium">{dialInNumber}</p>
                        </div>
                    )}
                    {isConfirmed && joinUrl && (
                        <div className="flex items-center gap-3">
                            <VideoIcon className="size-5 text-muted-foreground flex-shrink-0" />
                            <a
                                href={joinUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="font-medium text-primary underline"
                            >
                                Join Meeting
                            </a>
                        </div>
                    )}
                </div>
            </div>

            {/* Add to Calendar Button */}
            <Button
                variant="outline"
                onClick={handleDownloadICS}
                className="w-full mb-6"
            >
                <CalendarIcon className="size-4 mr-2" />
                Add to Calendar
            </Button>

        </div>
    )
}

function PublicBookingFooter() {
    return (
        <p className="mt-6 text-center text-xs text-muted-foreground">
            Powered by Surrogacy Force{" "}
            <span aria-hidden="true" className="mx-1">
                |
            </span>{" "}
            <Link href="/privacy" className="underline underline-offset-2 hover:text-foreground">
                Privacy Policy
            </Link>
            <span aria-hidden="true" className="mx-1">
                |
            </span>{" "}
            <Link href="/terms" className="underline underline-offset-2 hover:text-foreground">
                Terms
            </Link>
        </p>
    )
}

// =============================================================================
// Main Export
// =============================================================================

export function PublicBookingPage({
    publicSlug,
    preview = false,
}: {
    publicSlug: string
    preview?: boolean
}) {
    const isPreview = preview === true
    // State
    const [bookingSelection, dispatchBookingSelection] = useReducer(
        bookingSelectionReducer,
        initialBookingSelectionState,
    )
    const {
        selectedDate,
        selectedMeetingMode,
        selectedSlot,
        selectedTypeId,
        showForm,
    } = bookingSelection
    const [confirmation, setConfirmation] = useState<PublicAppointmentView | null>(null)
    const [bookingError, setBookingError] = useState<BookingSubmissionError | null>(null)
    const detectedTimezone = useSyncExternalStore(
        subscribeTimezoneSnapshot,
        getInitialClientTimezone,
        getServerTimezoneSnapshot
    )
    const [timezoneOverride, setTimezoneOverride] = useState<string | null>(null)

    // Queries
    const publicPageQuery = usePublicBookingPage(publicSlug, !isPreview)
    const previewPageQuery = useBookingPreviewPage(isPreview)
    const pageData = isPreview ? previewPageQuery.data : publicPageQuery.data
    const isLoadingPage = isPreview ? previewPageQuery.isLoading : publicPageQuery.isLoading
    const pageError = isPreview ? previewPageQuery.error : publicPageQuery.error
    const timezone = getEffectiveBookingTimezone(
        timezoneOverride,
        pageData?.org_timezone,
        detectedTimezone
    )

    const timezoneOptions = getTimezoneOptions(timezone)
    const dateRange = getInitialBookingDateRange(timezone)

    const publicSlotsQuery = useAvailableSlots(
        publicSlug,
        selectedTypeId || "",
        dateRange.start,
        dateRange.end,
        timezone,
        !isPreview
    )
    const previewSlotsQuery = useBookingPreviewSlots(
        selectedTypeId || "",
        dateRange.start,
        dateRange.end,
        timezone,
        isPreview
    )
    const slotsData = isPreview ? previewSlotsQuery.data : publicSlotsQuery.data
    const isLoadingSlots = isPreview
        ? previewSlotsQuery.isLoading
        : publicSlotsQuery.isLoading
    const slotsError = isPreview ? previewSlotsQuery.isError : publicSlotsQuery.isError
    const retrySlots = isPreview ? previewSlotsQuery.refetch : publicSlotsQuery.refetch

    const createBookingMutation = useCreateBooking()

    // Derived state
    const selectedType = pageData?.appointment_types.find((t) => t.id === selectedTypeId)
    const selectedTypeModes = getMeetingModes(selectedType)
    const requiresMeetingModeSelection = selectedTypeModes.length > 1
    const meetingModeReady = !requiresMeetingModeSelection || Boolean(selectedMeetingMode)

    const availableDates = getAvailableDates(slotsData?.slots, timezone)
    const slotsForDate = getSlotsForDate(selectedDate, slotsData?.slots, timezone)
    const validSelectedSlot = selectedSlot && !isLoadingSlots && !slotsError && slotsForDate.some((slot) => slot.start === selectedSlot.start)

    // Handlers
    const handleSubmit = (formData: Omit<BookingCreate, "appointment_type_id" | "scheduled_start" | "client_timezone">) => {
        if (!selectedTypeId || !selectedSlot || !validSelectedSlot) return
        const effectiveMeetingMode =
            selectedMeetingMode ?? (selectedTypeModes.length === 1 ? selectedTypeModes[0] : null)
        if (!effectiveMeetingMode) {
            toast.error("Select an appointment format to continue.")
            return
        }

        const data: BookingCreate = {
            ...formData,
            appointment_type_id: selectedTypeId,
            scheduled_start: selectedSlot.start,
            client_timezone: timezone,
            idempotency_key: buildIdempotencyKey(
                formData.client_email,
                selectedSlot.start,
                selectedTypeId
            ),
            request_id: createSchedulingRequestId(),
            meeting_mode: effectiveMeetingMode,
        }

        if (isPreview) {
            toast.info("Preview mode", {
                description: "Bookings are disabled while previewing.",
            })
            return
        }

        setBookingError(null)
        createBookingMutation.mutate(
            { publicSlug, data },
            {
                onSuccess: (response) => {
                    setBookingError(null)
                    setConfirmation(response)
                },
                onError: (error) => setBookingError(getBookingSubmissionError(error)),
            }
        )
    }

    // Loading state
    if (isLoadingPage) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    // Error state
    if (pageError || !pageData) {
        const title = isPreview ? "Preview Unavailable" : "Booking Page Not Found"
        const message = isPreview
            ? "Sign in and create at least one appointment type to preview this page."
            : "This booking link may be invalid or no longer active."
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <Card className="max-w-md">
                    <CardContent className="pt-6 text-center">
                        <h2 className="text-xl font-semibold mb-2">{title}</h2>
                        <p className="text-muted-foreground">{message}</p>
                    </CardContent>
                </Card>
            </div>
        )
    }

    // Confirmed state
    if (confirmation && selectedType && selectedSlot) {
        const confirmationMeetingMode =
            confirmation?.meeting_mode ??
            selectedMeetingMode ??
            selectedTypeModes[0] ??
            selectedType.meeting_mode
        return (
            <div className="min-h-screen bg-background py-12">
                <div className="max-w-lg mx-auto px-4">
                    <Card>
                        <CardContent className="pt-6">
                            <ConfirmationView
                                appointmentType={selectedType}
                                selectedSlot={selectedSlot}
                                timezone={timezone}
                                staffName={pageData?.staff?.display_name || "Staff Member"}
                                confirmation={confirmation}
                                meetingMode={confirmationMeetingMode}
                            />
                        </CardContent>
                    </Card>
                </div>
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-background py-12">
            <div className="max-w-4xl mx-auto px-4">
                <Card>
                    <CardHeader>
                        <StaffCard
                            displayName={pageData.staff.display_name}
                            avatarUrl={pageData.staff.avatar_url}
                            orgName={pageData.org_name}
                        />
                    </CardHeader>
                    <CardContent className="space-y-6">
                        {/* Timezone Selector */}
                        <div className="flex items-center gap-2 text-sm">
                            <GlobeIcon className="size-4 text-muted-foreground" />
                            <span className="text-muted-foreground">Timezone:</span>
                            <Select value={timezone} disabled={createBookingMutation.isPending} onValueChange={(v) => { if (v) { setTimezoneOverride(v); dispatchBookingSelection({ type: "selectDate", date: null }) } }}>
                                <SelectTrigger className="w-auto h-8 text-sm" aria-label="Timezone">
                                    <SelectValue>{(value: string | null) => value ? getTimezoneLabel(value) : "Timezone"}</SelectValue>
                                </SelectTrigger>
                                <SelectContent>
                                    {timezoneOptions.map((opt) => (
                                        <SelectItem key={opt.value} value={opt.value}>
                                            {opt.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        {isPreview && (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Badge variant="secondary">Preview</Badge>
                                <span>Bookings are disabled in preview mode.</span>
                            </div>
                        )}

                        {/* Booking Form */}
                        {showForm && selectedType && selectedSlot && validSelectedSlot ? (
                            <BookingForm
                                appointmentType={selectedType}
                                meetingMode={
                                    selectedMeetingMode ??
                                    selectedTypeModes[0] ??
                                    selectedType.meeting_mode
                                }
                                selectedSlot={selectedSlot}
                                timezone={timezone}
                                onSubmit={handleSubmit}
                                onBack={() => { setBookingError(null); dispatchBookingSelection({ type: "hideForm" }) }}
                                isSubmitting={isPreview ? false : createBookingMutation.isPending}
                                submissionError={bookingError}
                                onEdit={() => setBookingError(null)}
                            />
                        ) : (
                            <>
                                {/* Type Selector */}
                                <AppointmentTypeSelector
                                    types={pageData.appointment_types}
                                    selectedId={selectedTypeId}
                                    onSelect={(id) => {
                                        const nextType = pageData.appointment_types.find((type) => type.id === id)
                                        dispatchBookingSelection({
                                            type: "selectType",
                                            typeId: id,
                                            meetingModes: getMeetingModes(nextType),
                                        })
                                    }}
                                />

                                {/* Meeting Mode */}
                                {selectedTypeId && requiresMeetingModeSelection && selectedType && (
                                    <MeetingModeSelector
                                        meetingModes={selectedTypeModes}
                                        selectedMode={selectedMeetingMode}
                                        onSelect={(mode) =>
                                            dispatchBookingSelection({
                                                type: "selectMeetingMode",
                                                mode,
                                            })
                                        }
                                    />
                                )}

                                {selectedTypeId && meetingModeReady && isLoadingSlots && (
                                    <p role="status" className="text-sm text-muted-foreground">Loading available times…</p>
                                )}
                                {selectedTypeId && meetingModeReady && slotsError && (
                                    <div className="flex flex-wrap items-center gap-3" role="alert">
                                        <span className="text-sm text-destructive">Calendar availability is unavailable.</span>
                                        <Button type="button" size="sm" variant="outline" onClick={() => void retrySlots()}>Retry availability</Button>
                                    </div>
                                )}
                                {selectedTypeId && meetingModeReady && !isLoadingSlots && !slotsError && availableDates.size === 0 && (
                                    <p className="text-sm text-muted-foreground">No available times in this date range.</p>
                                )}

                                <div className="grid gap-5 md:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
                                {/* Calendar */}
                                {selectedTypeId && meetingModeReady && (
                                    <CalendarView
                                        key={timezone}
                                        selectedDate={selectedDate}
                                        onSelect={(date) =>
                                            dispatchBookingSelection({ type: "selectDate", date })
                                        }
                                        availableDates={availableDates}
                                        timezone={timezone}
                                    />
                                )}

                                {/* Time Slots */}
                                {selectedTypeId && meetingModeReady && (
                                    <div className="space-y-2">
                                    <Label className="font-medium">Select a time</Label>
                                    {selectedDate ? <SchedulingSlotList
                                        slots={slotsForDate}
                                        timezone={timezone}
                                        selectedStart={selectedSlot?.start ?? null}
                                        onSelectStart={(start) => { const slot = slotsForDate.find((item) => item.start === start); if (slot) dispatchBookingSelection({ type: "selectSlot", slot }) }}
                                        loading={isLoadingSlots}
                                        error={slotsError ? "Calendar availability is unavailable." : null}
                                        onRetry={() => void retrySlots()}
                                        disabled={isLoadingSlots}
                                    /> : <p className="py-4 text-sm text-muted-foreground">Choose a date.</p>}
                                    </div>
                                )}
                                </div>

                                {/* Contact Details Button */}
                                {selectedSlot && meetingModeReady && validSelectedSlot && (
                                    <Button
                                        className="w-full"
                                        size="lg"
                                        onClick={() => dispatchBookingSelection({ type: "showForm" })}
                                    >
                                        Enter contact details
                                    </Button>
                                )}
                            </>
                        )}
                    </CardContent>
                </Card>

                <PublicBookingFooter />
            </div>
        </div>
    )
}
