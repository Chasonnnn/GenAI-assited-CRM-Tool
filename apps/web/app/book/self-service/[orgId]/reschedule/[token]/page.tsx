"use client"

/**
 * Self-Service Reschedule Page - /book/self-service/[orgId]/reschedule/[token]
 *
 * Allows clients to reschedule their appointment using a secure token.
 */

import { use, useEffect, useMemo, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    ChevronLeftIcon,
    ChevronRightIcon,
    Loader2Icon,
    CheckCircleIcon,
    AlertCircleIcon,
    GlobeIcon,
} from "lucide-react"
import { format, startOfDay, parseISO, isSameDay } from "date-fns"
import type { TimeSlot, PublicAppointmentView } from "@/lib/api/appointments"
import {
    getAppointmentForReschedule,
    rescheduleByToken,
    getRescheduleSlotsByToken,
} from "@/lib/api/appointments"

// Timezone options
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

interface PageProps {
    params: Promise<{ orgId?: string | string[]; token?: string | string[] }>
}

export default function ReschedulePage({ params }: PageProps) {
    const resolvedParams = use(params)
    const rawOrgId = resolvedParams.orgId
    const rawToken = resolvedParams.token
    const orgId = Array.isArray(rawOrgId) ? rawOrgId[0] : rawOrgId
    const token = Array.isArray(rawToken) ? rawToken[0] : rawToken

    const [appointment, setAppointment] = useState<PublicAppointmentView | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [selectedDate, setSelectedDate] = useState<Date | null>(null)
    const [selectedSlot, setSelectedSlot] = useState<TimeSlot | null>(null)
    const [slots, setSlots] = useState<TimeSlot[]>([])
    const [isLoadingSlots, setIsLoadingSlots] = useState(false)
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [isConfirmed, setIsConfirmed] = useState(false)
    const [timezone, setTimezone] = useState("America/Los_Angeles")
    const [viewMonth, setViewMonth] = useState(new Date())

    // Auto-detect timezone
    useEffect(() => {
        try {
            const tz = Intl.DateTimeFormat().resolvedOptions().timeZone
            if (tz) setTimezone(tz)
        } catch {
            // Use default
        }
    }, [])

    const timezoneOptions = useMemo(() => {
        if (TIMEZONE_OPTIONS.some((opt) => opt.value === timezone)) {
            return TIMEZONE_OPTIONS
        }
        return [...TIMEZONE_OPTIONS, { value: timezone, label: timezone }]
    }, [timezone])

    // Fetch appointment
    useEffect(() => {
        if (!orgId || !token) {
            setError("Invalid reschedule link")
            setIsLoading(false)
            return
        }

        const orgIdForCall = orgId
        const tokenForCall = token

        async function load() {
            try {
                const data = await getAppointmentForReschedule(
                    orgIdForCall,
                    tokenForCall
                )
                setAppointment(data)
            } catch (err: unknown) {
                setError(err instanceof Error ? err.message : "Appointment not found")
            } finally {
                setIsLoading(false)
            }
        }
        load()
    }, [orgId, token])

    useEffect(() => {
        if (appointment?.client_timezone) {
            setTimezone(appointment.client_timezone)
        }
    }, [appointment?.client_timezone])

    // Date selection handler
    const handleDateSelect = async (date: Date) => {
        setSelectedDate(date)
        setSelectedSlot(null)
        setIsLoadingSlots(true)

        try {
            if (!orgId || !token) throw new Error("Invalid reschedule link")

            // Fetch real availability from API
            const dateStr = format(date, "yyyy-MM-dd")
            const response = await getRescheduleSlotsByToken(
                orgId,
                token,
                dateStr,
                dateStr,
                timezone
            )
            setSlots(response.slots)
        } catch (err: unknown) {
            console.error("Failed to fetch slots:", err instanceof Error ? err.message : err)
            setSlots([])
        } finally {
            setIsLoadingSlots(false)
        }
    }

    // Submit reschedule
    const handleSubmit = async () => {
        if (!selectedSlot) return

        setIsSubmitting(true)
        try {
            if (!orgId || !token) throw new Error("Invalid reschedule link")
            await rescheduleByToken(orgId, token, selectedSlot.start)
            setIsConfirmed(true)
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Failed to reschedule")
        } finally {
            setIsSubmitting(false)
        }
    }

    // Calendar days
    const days = useMemo(() => {
        const start = new Date(viewMonth.getFullYear(), viewMonth.getMonth(), 1)
        const startDay = start.getDay()
        const daysInMonth = new Date(viewMonth.getFullYear(), viewMonth.getMonth() + 1, 0).getDate()

        const result: Array<{ date: Date | null; isToday: boolean; isAvailable: boolean }> = []
        for (let i = 0; i < startDay; i++) {
            result.push({ date: null, isToday: false, isAvailable: false })
        }

        const today = startOfDay(new Date())
        for (let d = 1; d <= daysInMonth; d++) {
            const date = new Date(viewMonth.getFullYear(), viewMonth.getMonth(), d)
            const dayOfWeek = date.getDay()
            // Assume weekdays are available
            const isWeekday = dayOfWeek >= 1 && dayOfWeek <= 5
            result.push({
                date,
                isToday: isSameDay(date, today),
                isAvailable: isWeekday && date >= today,
            })
        }
        return result
    }, [viewMonth])

    // Loading state
    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    // Error state
    if (error && !appointment) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <Card className="max-w-md">
                    <CardContent className="pt-6 text-center">
                        <AlertCircleIcon className="size-12 mx-auto mb-4 text-destructive" />
                        <h2 className="text-xl font-semibold mb-2">Unable to Reschedule</h2>
                        <p className="text-muted-foreground">{error}</p>
                    </CardContent>
                </Card>
            </div>
        )
    }

    // Confirmed state
    if (isConfirmed) {
        return (
            <div className="min-h-screen bg-background py-12">
                <div className="max-w-lg mx-auto px-4">
                    <Card>
                        <CardContent className="pt-6 text-center">
                            <div className="size-16 mx-auto rounded-full bg-green-500/10 flex items-center justify-center mb-6">
                                <CheckCircleIcon className="size-8 text-green-600" />
                            </div>
                            <h2 className="text-2xl font-semibold mb-2">Rescheduled!</h2>
                            <p className="text-muted-foreground">
                                Your appointment has been rescheduled successfully. You will receive an updated confirmation email.
                            </p>
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
                        <CardTitle>Reschedule Appointment</CardTitle>
                        <CardDescription>
                            Select a new date and time for your appointment
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        {/* Current Appointment */}
                        {appointment && (
                            <div className="p-4 rounded-lg bg-muted">
                                <p className="text-sm text-muted-foreground mb-1">Current appointment</p>
                                <p className="font-medium">{appointment.appointment_type_name}</p>
                                <p className="text-sm text-muted-foreground">
                                    {format(parseISO(appointment.scheduled_start), "EEEE, MMMM d 'at' h:mm a")}
                                </p>
                                {appointment.meeting_location && (
                                    <p className="text-sm text-muted-foreground">
                                        Location: {appointment.meeting_location}
                                    </p>
                                )}
                                {appointment.dial_in_number && (
                                    <p className="text-sm text-muted-foreground">
                                        Dial-in: {appointment.dial_in_number}
                                    </p>
                                )}
                            </div>
                        )}

                        {/* Timezone */}
                        <div className="flex items-center gap-2 text-sm">
                            <GlobeIcon className="size-4 text-muted-foreground" />
                            <span className="text-muted-foreground">Timezone:</span>
                            <Select value={timezone} onValueChange={(v) => v && setTimezone(v)}>
                                <SelectTrigger className="w-auto h-8 text-sm">
                                    <SelectValue />
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

                        {/* Calendar */}
                        <div className="space-y-3">
                            <p className="font-medium">Select New Date</p>
                            <Card>
                                <CardContent className="pt-4">
                                    <div className="flex items-center justify-between mb-4">
                                        <Button variant="ghost" size="sm" onClick={() => setViewMonth(new Date(viewMonth.getFullYear(), viewMonth.getMonth() - 1))}>
                                            <ChevronLeftIcon className="size-4" />
                                        </Button>
                                        <span className="font-medium">{format(viewMonth, "MMMM yyyy")}</span>
                                        <Button variant="ghost" size="sm" onClick={() => setViewMonth(new Date(viewMonth.getFullYear(), viewMonth.getMonth() + 1))}>
                                            <ChevronRightIcon className="size-4" />
                                        </Button>
                                    </div>

                                    <div className="grid grid-cols-7 text-center text-sm text-muted-foreground mb-2">
                                        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
                                            <div key={d} className="py-2">{d}</div>
                                        ))}
                                    </div>

                                    <div className="grid grid-cols-7 gap-1">
                                        {days.map((day, i) => {
                                            if (!day.date) return <div key={i} className="h-10" />
                                            const isSelected = selectedDate && isSameDay(day.date, selectedDate)
                                            return (
                                                <Button
                                                    key={i}
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => day.isAvailable && handleDateSelect(day.date!)}
                                                    disabled={!day.isAvailable}
                                                    className={`h-10 text-sm font-medium ${isSelected
                                                        ? "bg-primary text-primary-foreground hover:bg-primary/90"
                                                        : day.isToday
                                                            ? "bg-primary/10 text-primary hover:bg-primary/20"
                                                            : day.isAvailable
                                                                ? "hover:bg-muted"
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

                        {/* Time Slots */}
                        {selectedDate && (
                            <div className="space-y-3">
                                <p className="font-medium">Select New Time</p>
                                {isLoadingSlots ? (
                                    <div className="py-8 flex items-center justify-center">
                                        <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                                    </div>
                                ) : slots.length === 0 ? (
                                    <p className="text-muted-foreground text-center py-4">No available times</p>
                                ) : (
                                    <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 max-h-64 overflow-y-auto">
                                        {slots.map((slot) => {
                                            const time = format(parseISO(slot.start), "h:mm a")
                                            const isSelected = selectedSlot?.start === slot.start
                                            return (
                                                <Button
                                                    key={slot.start}
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => setSelectedSlot(slot)}
                                                    className={`py-2 px-3 h-auto text-sm font-medium ${isSelected
                                                        ? "border-primary bg-primary text-primary-foreground hover:bg-primary/90"
                                                        : "hover:border-primary/50"
                                                        }`}
                                                >
                                                    {time}
                                                </Button>
                                            )
                                        })}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Submit */}
                        {selectedSlot && (
                            <Button className="w-full" size="lg" onClick={handleSubmit} disabled={isSubmitting}>
                                {isSubmitting && <Loader2Icon className="size-4 mr-2 animate-spin" />}
                                Confirm Reschedule
                            </Button>
                        )}

                        {error && appointment && (
                            <p className="text-sm text-destructive text-center">{error}</p>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
