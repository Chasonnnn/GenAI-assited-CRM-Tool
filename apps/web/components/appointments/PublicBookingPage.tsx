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

import { useState, useEffect, useMemo } from "react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
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
import type { AppointmentType, TimeSlot, BookingCreate } from "@/lib/api/appointments"
import { format, addDays, startOfDay, parseISO, isSameDay } from "date-fns"
import { toast } from "sonner"

// Timezone options
const TIMEZONE_OPTIONS = [
    { value: "America/Los_Angeles", label: "Pacific Time (PT)" },
    { value: "America/New_York", label: "Eastern Time (ET)" },
    { value: "America/Chicago", label: "Central Time (CT)" },
    { value: "America/Denver", label: "Mountain Time (MT)" },
    { value: "America/Phoenix", label: "Arizona (AZ)" },
    { value: "Pacific/Honolulu", label: "Hawaii (HI)" },
    { value: "America/Anchorage", label: "Alaska (AK)" },
]

// Appointment format display
const MEETING_MODES: Record<string, { icon: typeof VideoIcon; label: string }> = {
    zoom: { icon: VideoIcon, label: "Zoom Video Call" },
    google_meet: { icon: VideoIcon, label: "Google Meet" },
    phone: { icon: PhoneIcon, label: "Phone Call" },
    in_person: { icon: MapPinIcon, label: "In-Person Appointment" },
}

function formatDateKey(date: Date, timezone: string) {
    return new Intl.DateTimeFormat("en-CA", {
        timeZone: timezone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
    }).format(date)
}

function formatTimeInZone(date: Date, timezone: string) {
    return new Intl.DateTimeFormat("en-US", {
        timeZone: timezone,
        hour: "numeric",
        minute: "2-digit",
    }).format(date)
}

function formatDateInZone(date: Date, timezone: string) {
    return new Intl.DateTimeFormat("en-US", {
        timeZone: timezone,
        weekday: "long",
        month: "long",
        day: "numeric",
        year: "numeric",
    }).format(date)
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
        <div className="space-y-3">
            <Label className="text-base font-medium">Select Appointment Type</Label>
            <div className="grid gap-3">
                {types.map((type) => {
                    const mode = MEETING_MODES[type.meeting_mode]
                    const ModeIcon = mode?.icon || VideoIcon
                    const isSelected = selectedId === type.id

                    return (
                        <Button
                            key={type.id}
                            variant="outline"
                            onClick={() => onSelect(type.id)}
                            className={`flex items-center gap-4 p-4 h-auto rounded-xl text-left justify-start ${isSelected
                                ? "border-primary bg-primary/5 ring-2 ring-primary/20"
                                : "hover:border-primary/50 hover:bg-muted/50"
                                }`}
                        >
                            <div className={`p-3 rounded-lg ${isSelected ? "bg-primary/20" : "bg-muted"}`}>
                                <ModeIcon className={`size-5 ${isSelected ? "text-primary" : "text-muted-foreground"}`} />
                            </div>
                            <div className="flex-1">
                                <h3 className="font-medium">{type.name}</h3>
                                <p className="text-sm text-muted-foreground">
                                    {type.duration_minutes} min • {mode?.label || type.meeting_mode}
                                </p>
                                {type.description && (
                                    <p className="text-sm text-muted-foreground mt-1">{type.description}</p>
                                )}
                            </div>
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
    const [viewMonth, setViewMonth] = useState(new Date())

    const days = useMemo(() => {
        const start = new Date(viewMonth.getFullYear(), viewMonth.getMonth(), 1)
        const startDay = start.getDay() // 0 = Sunday
        const daysInMonth = new Date(viewMonth.getFullYear(), viewMonth.getMonth() + 1, 0).getDate()

        const result: Array<{ date: Date | null; isToday: boolean; hasSlots: boolean }> = []

        // Padding for days before month starts
        for (let i = 0; i < startDay; i++) {
            result.push({ date: null, isToday: false, hasSlots: false })
        }

        const todayDate = startOfDay(new Date())
        const todayKey = formatDateKey(new Date(), timezone)
        for (let d = 1; d <= daysInMonth; d++) {
            const date = new Date(viewMonth.getFullYear(), viewMonth.getMonth(), d)
            const dateStr = formatDateKey(date, timezone)
            result.push({
                date,
                isToday: dateStr === todayKey,
                hasSlots: availableDates.has(dateStr) && date >= todayDate,
            })
        }

        return result
    }, [viewMonth, availableDates, timezone])

    const prevMonth = () => setViewMonth(new Date(viewMonth.getFullYear(), viewMonth.getMonth() - 1))
    const nextMonth = () => setViewMonth(new Date(viewMonth.getFullYear(), viewMonth.getMonth() + 1))

    return (
        <div className="space-y-4">
            <Label className="text-base font-medium">Select a Date</Label>
            <Card>
                <CardContent className="pt-4">
                    {/* Month Navigation */}
                    <div className="flex items-center justify-between mb-4">
                        <Button variant="ghost" size="sm" onClick={prevMonth}>
                            <ChevronLeftIcon className="size-4" />
                        </Button>
                        <span className="font-medium">{format(viewMonth, "MMMM yyyy")}</span>
                        <Button variant="ghost" size="sm" onClick={nextMonth}>
                            <ChevronRightIcon className="size-4" />
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
                        {days.map((day, i) => {
                            if (!day.date) {
                                return <div key={i} className="h-10" />
                            }

                            const isSelected = selectedDate && isSameDay(day.date, selectedDate)
                            const isPast = day.date < startOfDay(new Date())

                            return (
                                <Button
                                    key={i}
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => day.hasSlots && onSelect(day.date!)}
                                    disabled={!day.hasSlots || isPast}
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
// Time Slot Selector
// =============================================================================

function TimeSlotSelector({
    slots,
    selectedSlot,
    onSelect,
    isLoading,
    timezone,
}: {
    slots: TimeSlot[]
    selectedSlot: TimeSlot | null
    onSelect: (slot: TimeSlot) => void
    isLoading: boolean
    timezone: string
}) {
    if (isLoading) {
        return (
            <div className="py-8 flex items-center justify-center">
                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (slots.length === 0) {
        return (
            <div className="py-8 text-center text-muted-foreground">
                <ClockIcon className="size-8 mx-auto mb-2 opacity-50" />
                <p>No available times for this date</p>
            </div>
        )
    }

    return (
        <div className="space-y-3">
            <Label className="text-base font-medium">Select a Time</Label>
            <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 max-h-64 overflow-y-auto">
                {slots.map((slot) => {
                    const time = formatTimeInZone(parseISO(slot.start), timezone)
                    const isSelected = selectedSlot?.start === slot.start

                    return (
                        <Button
                            key={slot.start}
                            variant="outline"
                            size="sm"
                            onClick={() => onSelect(slot)}
                            className={`py-2 px-3 h-auto text-sm font-medium ${isSelected
                                ? "border-primary bg-primary text-primary-foreground hover:bg-primary/90"
                                : "hover:border-primary/50 hover:bg-muted/50"
                                }`}
                        >
                            {time}
                        </Button>
                    )
                })}
            </div>
        </div>
    )
}

// =============================================================================
// Booking Form
// =============================================================================

function BookingForm({
    appointmentType,
    selectedSlot,
    timezone,
    onSubmit,
    onBack,
    isSubmitting,
}: {
    appointmentType: AppointmentType
    selectedSlot: TimeSlot
    timezone: string
    onSubmit: (data: Omit<BookingCreate, "appointment_type_id" | "scheduled_start" | "client_timezone">) => void
    onBack: () => void
    isSubmitting: boolean
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

    const mode = MEETING_MODES[appointmentType.meeting_mode]
    const ModeIcon = mode?.icon || VideoIcon

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
                                {formatDateInZone(parseISO(selectedSlot.start), timezone)}
                            </p>
                            <p className="text-sm text-muted-foreground flex items-center gap-2">
                                <ClockIcon className="size-4" />
                                {formatTimeInZone(parseISO(selectedSlot.start), timezone)} ({appointmentType.duration_minutes} min)
                            </p>
                            <p className="text-sm text-muted-foreground flex items-center gap-2">
                                <ModeIcon className="size-4" />
                                {mode?.label}
                            </p>
                        </div>
                        <Button variant="ghost" size="sm" onClick={onBack}>
                            Change
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {/* Form Fields */}
            <div className="space-y-4">
                <div className="space-y-2">
                    <Label htmlFor="name">Full Name *</Label>
                    <Input
                        id="name"
                        value={formData.client_name}
                        onChange={(e) => setFormData({ ...formData, client_name: e.target.value })}
                        placeholder="Your full name"
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
                        onChange={(e) => setFormData({ ...formData, client_email: e.target.value })}
                        placeholder="your@email.com"
                        className={errors.client_email ? "border-destructive" : ""}
                    />
                    {errors.client_email && (
                        <p className="text-sm text-destructive">{errors.client_email}</p>
                    )}
                </div>

                <div className="space-y-2">
                    <Label htmlFor="phone">Phone Number *</Label>
                    <Input
                        id="phone"
                        type="tel"
                        value={formData.client_phone}
                        onChange={(e) => setFormData({ ...formData, client_phone: e.target.value })}
                        placeholder="(555) 123-4567"
                        className={errors.client_phone ? "border-destructive" : ""}
                    />
                    {errors.client_phone && (
                        <p className="text-sm text-destructive">{errors.client_phone}</p>
                    )}
                </div>

                <div className="space-y-2">
                    <Label htmlFor="notes">Additional Notes (optional)</Label>
                    <Textarea
                        id="notes"
                        value={formData.client_notes}
                        onChange={(e) => setFormData({ ...formData, client_notes: e.target.value })}
                        placeholder="Any additional information you'd like to share..."
                        rows={3}
                    />
                </div>
            </div>

            <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
                {isSubmitting && <Loader2Icon className="size-4 mr-2 animate-spin" />}
                Request Appointment
            </Button>

            <p className="text-xs text-center text-muted-foreground">
                Your appointment request will be sent for review. You'll receive a confirmation email once approved.
            </p>
        </form>
    )
}

// Generate ICS file for calendar download
function generateICSFile(
    appointmentType: AppointmentType,
    startTime: string,
    timezone: string,
    staffName: string,
): string {
    const start = new Date(startTime)
    const end = new Date(start.getTime() + appointmentType.duration_minutes * 60 * 1000)

    // Format dates for ICS (YYYYMMDDTHHMMSSZ in UTC)
    const formatICSDate = (date: Date) => {
        return date.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '')
    }

    const meetingModeLabel = MEETING_MODES[appointmentType.meeting_mode as keyof typeof MEETING_MODES]?.label || appointmentType.meeting_mode

    const ics = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//CRM Platform//Booking//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'BEGIN:VEVENT',
        `DTSTART:${formatICSDate(start)}`,
        `DTEND:${formatICSDate(end)}`,
        `SUMMARY:${appointmentType.name} with ${staffName}`,
        `DESCRIPTION:Appointment format: ${meetingModeLabel}\\nDuration: ${appointmentType.duration_minutes} minutes\\n\\nThis appointment is pending approval. You will receive a confirmation email once approved.`,
        'STATUS:TENTATIVE',
        `UID:${Date.now()}@crm-platform`,
        'END:VEVENT',
        'END:VCALENDAR',
    ].join('\r\n')

    return ics
}

function ConfirmationView({
    appointmentType,
    selectedSlot,
    timezone,
    staffName,
}: {
    appointmentType: AppointmentType
    selectedSlot: TimeSlot
    timezone: string
    staffName: string
}) {
    const meetingMode = MEETING_MODES[appointmentType.meeting_mode as keyof typeof MEETING_MODES]
    const ModeIcon = meetingMode?.icon || VideoIcon

    const handleDownloadICS = () => {
        const ics = generateICSFile(appointmentType, selectedSlot.start, timezone, staffName)
        const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `appointment-${format(parseISO(selectedSlot.start), 'yyyy-MM-dd')}.ics`
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

            <h2 className="text-2xl font-semibold mb-2">Request Submitted!</h2>
            <p className="text-muted-foreground mb-6">
                Your appointment request has been submitted successfully.
            </p>

            {/* Appointment Summary Card */}
            <div className="bg-muted/50 rounded-lg p-4 mb-6 text-left">
                <h3 className="font-medium mb-3 text-sm text-muted-foreground uppercase tracking-wide">
                    Appointment Details
                </h3>
                <div className="space-y-3">
                    <div className="flex items-center gap-3">
                        <CalendarIcon className="size-5 text-muted-foreground flex-shrink-0" />
                        <div>
                            <p className="font-medium">{formatDateInZone(parseISO(selectedSlot.start), timezone)}</p>
                            <p className="text-sm text-muted-foreground">
                                {formatTimeInZone(parseISO(selectedSlot.start), timezone)} ({timezone.split('/')[1]?.replace('_', ' ') || timezone})
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
                        <p className="font-medium">{meetingMode?.label || appointmentType.meeting_mode}</p>
                    </div>
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

            {/* What's Next Section */}
            <div className="bg-blue-500/5 border border-blue-500/20 rounded-lg p-4 text-left">
                <h3 className="font-medium text-blue-700 dark:text-blue-400 mb-2">What&apos;s Next?</h3>
                <ol className="text-sm text-muted-foreground space-y-2">
                    <li className="flex gap-2">
                        <span className="font-medium text-blue-600 dark:text-blue-400">1.</span>
                        <span>Our team will review your request</span>
                    </li>
                    <li className="flex gap-2">
                        <span className="font-medium text-blue-600 dark:text-blue-400">2.</span>
                        <span>You&apos;ll receive an email confirmation once approved</span>
                    </li>
                    <li className="flex gap-2">
                        <span className="font-medium text-blue-600 dark:text-blue-400">3.</span>
                        <span>Appointment details will be included in the confirmation</span>
                    </li>
                </ol>
            </div>

            <p className="text-xs text-muted-foreground mt-6">
                You can safely close this page now.
            </p>
        </div>
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
    const [selectedTypeId, setSelectedTypeId] = useState<string | null>(null)
    const [selectedDate, setSelectedDate] = useState<Date | null>(null)
    const [selectedSlot, setSelectedSlot] = useState<TimeSlot | null>(null)
    const [showForm, setShowForm] = useState(false)
    const [isConfirmed, setIsConfirmed] = useState(false)
    const [timezone, setTimezone] = useState("America/Los_Angeles")

    // Auto-detect timezone
    useEffect(() => {
        try {
            const tz = Intl.DateTimeFormat().resolvedOptions().timeZone
            const found = TIMEZONE_OPTIONS.find((opt) => opt.value === tz)
            if (found) {
                setTimezone(tz)
            }
        } catch {
            // Use default
        }
    }, [])

    // Queries
    const publicPageQuery = usePublicBookingPage(publicSlug, !isPreview)
    const previewPageQuery = useBookingPreviewPage(isPreview)
    const pageData = isPreview ? previewPageQuery.data : publicPageQuery.data
    const isLoadingPage = isPreview ? previewPageQuery.isLoading : publicPageQuery.isLoading
    const pageError = isPreview ? previewPageQuery.error : publicPageQuery.error

    useEffect(() => {
        if (pageData?.org_timezone && timezone === "America/Los_Angeles") {
            setTimezone(pageData.org_timezone)
        }
    }, [pageData?.org_timezone, timezone])

    const dateRange = useMemo(() => {
        const start = format(new Date(), "yyyy-MM-dd")
        const end = format(addDays(new Date(), 30), "yyyy-MM-dd")
        return { start, end }
    }, [])

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

    const createBookingMutation = useCreateBooking()

    // Derived state
    const selectedType = pageData?.appointment_types.find((t) => t.id === selectedTypeId)

    const availableDates = useMemo(() => {
        const dates = new Set<string>()
        slotsData?.slots.forEach((slot) => {
            dates.add(formatDateKey(parseISO(slot.start), timezone))
        })
        return dates
    }, [slotsData, timezone])

    const slotsForDate = useMemo(() => {
        if (!selectedDate || !slotsData) return []
        const dateStr = formatDateKey(selectedDate, timezone)
        return slotsData.slots.filter((slot) =>
            formatDateKey(parseISO(slot.start), timezone) === dateStr
        )
    }, [selectedDate, slotsData, timezone])

    // Handlers
    const handleSubmit = (formData: Omit<BookingCreate, "appointment_type_id" | "scheduled_start" | "client_timezone">) => {
        if (!selectedTypeId || !selectedSlot) return

        const data: BookingCreate = {
            ...formData,
            appointment_type_id: selectedTypeId,
            scheduled_start: selectedSlot.start,
            client_timezone: timezone,
            idempotency_key: `${formData.client_email}-${selectedSlot.start}-${selectedTypeId}`,
        }

        if (isPreview) {
            toast.info("Preview mode", {
                description: "Bookings are disabled while previewing.",
            })
            return
        }

        createBookingMutation.mutate(
            { publicSlug, data },
            { onSuccess: () => setIsConfirmed(true) }
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
    if (isConfirmed && selectedType && selectedSlot) {
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
                            />
                        </CardContent>
                    </Card>
                </div>
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-background py-12">
            <div className="max-w-xl mx-auto px-4">
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
                            <Select value={timezone} onValueChange={(v) => v && setTimezone(v)}>
                                <SelectTrigger className="w-auto h-8 text-sm">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {TIMEZONE_OPTIONS.map((opt) => (
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
                        {showForm && selectedType && selectedSlot ? (
                            <BookingForm
                                appointmentType={selectedType}
                                selectedSlot={selectedSlot}
                                timezone={timezone}
                                onSubmit={handleSubmit}
                                onBack={() => setShowForm(false)}
                                isSubmitting={isPreview ? false : createBookingMutation.isPending}
                            />
                        ) : (
                            <>
                                {/* Type Selector */}
                                <AppointmentTypeSelector
                                    types={pageData.appointment_types}
                                    selectedId={selectedTypeId}
                                    onSelect={(id) => {
                                        setSelectedTypeId(id)
                                        setSelectedDate(null)
                                        setSelectedSlot(null)
                                    }}
                                />

                                {/* Calendar */}
                                {selectedTypeId && (
                                    <CalendarView
                                        selectedDate={selectedDate}
                                        onSelect={(date) => {
                                            setSelectedDate(date)
                                            setSelectedSlot(null)
                                        }}
                                        availableDates={availableDates}
                                        timezone={timezone}
                                    />
                                )}

                                {/* Time Slots */}
                                {selectedDate && (
                                    <TimeSlotSelector
                                        slots={slotsForDate}
                                        selectedSlot={selectedSlot}
                                        onSelect={setSelectedSlot}
                                        isLoading={isLoadingSlots}
                                        timezone={timezone}
                                    />
                                )}

                                {/* Continue Button */}
                                {selectedSlot && (
                                    <Button
                                        className="w-full"
                                        size="lg"
                                        onClick={() => setShowForm(true)}
                                    >
                                        Continue
                                    </Button>
                                )}
                            </>
                        )}
                    </CardContent>
                </Card>

                {/* Footer */}
                <p className="text-center text-xs text-muted-foreground mt-6">
                    Powered by CRM Platform
                </p>
            </div>
        </div>
    )
}
