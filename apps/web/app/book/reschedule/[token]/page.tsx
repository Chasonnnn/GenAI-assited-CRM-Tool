"use client"

/**
 * Self-Service Reschedule Page - /book/reschedule/[token]
 * 
 * Allows clients to reschedule their appointment using a secure token.
 */

import { useState, useEffect, useMemo } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
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
    LoaderIcon,
    CheckCircleIcon,
    AlertCircleIcon,
    GlobeIcon,
} from "lucide-react"
import { format, addDays, startOfDay, parseISO, isSameDay } from "date-fns"
import type { TimeSlot, PublicAppointmentView } from "@/lib/api/appointments"
import {
    getAppointmentForReschedule,
    rescheduleByToken,
    getAvailableSlots as fetchAvailableSlots
} from "@/lib/api/appointments"

// Timezone options
const TIMEZONE_OPTIONS = [
    { value: "America/New_York", label: "Eastern Time (ET)" },
    { value: "America/Chicago", label: "Central Time (CT)" },
    { value: "America/Denver", label: "Mountain Time (MT)" },
    { value: "America/Los_Angeles", label: "Pacific Time (PT)" },
]

interface PageProps {
    params: { token: string }
}

export default function ReschedulePage({ params }: PageProps) {
    const [appointment, setAppointment] = useState<PublicAppointmentView | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [selectedDate, setSelectedDate] = useState<Date | null>(null)
    const [selectedSlot, setSelectedSlot] = useState<TimeSlot | null>(null)
    const [slots, setSlots] = useState<TimeSlot[]>([])
    const [isLoadingSlots, setIsLoadingSlots] = useState(false)
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [isConfirmed, setIsConfirmed] = useState(false)
    const [timezone, setTimezone] = useState("America/New_York")
    const [viewMonth, setViewMonth] = useState(new Date())

    // Auto-detect timezone
    useEffect(() => {
        try {
            const tz = Intl.DateTimeFormat().resolvedOptions().timeZone
            const found = TIMEZONE_OPTIONS.find((opt) => opt.value === tz)
            if (found) setTimezone(tz)
        } catch {
            // Use default
        }
    }, [])

    // Fetch appointment
    useEffect(() => {
        async function load() {
            try {
                const data = await getAppointmentForReschedule(params.token)
                setAppointment(data as PublicAppointmentView)
            } catch (err: any) {
                setError(err.message || "Appointment not found")
            } finally {
                setIsLoading(false)
            }
        }
        load()
    }, [params.token])

    // Date selection handler
    const handleDateSelect = async (date: Date) => {
        setSelectedDate(date)
        setSelectedSlot(null)
        setIsLoadingSlots(true)

        // Note: In a full implementation, we would fetch slots from the booking API
        // For now, we'll simulate available slots
        try {
            // Simulate loading
            await new Promise(resolve => setTimeout(resolve, 500))

            // Generate sample slots for the selected date
            const sampleSlots: TimeSlot[] = []
            const baseDate = format(date, "yyyy-MM-dd")
            for (let hour = 9; hour < 17; hour++) {
                for (let min = 0; min < 60; min += 30) {
                    const start = `${baseDate}T${hour.toString().padStart(2, '0')}:${min.toString().padStart(2, '0')}:00Z`
                    const endHour = min === 30 ? hour + 1 : hour
                    const endMin = min === 30 ? 0 : 30
                    const end = `${baseDate}T${endHour.toString().padStart(2, '0')}:${endMin.toString().padStart(2, '0')}:00Z`
                    sampleSlots.push({ start, end })
                }
            }
            setSlots(sampleSlots)
        } finally {
            setIsLoadingSlots(false)
        }
    }

    // Submit reschedule
    const handleSubmit = async () => {
        if (!selectedSlot) return

        setIsSubmitting(true)
        try {
            await rescheduleByToken(params.token, selectedSlot.start)
            setIsConfirmed(true)
        } catch (err: any) {
            setError(err.message || "Failed to reschedule")
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
                <LoaderIcon className="size-8 animate-spin text-muted-foreground" />
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
                                    {TIMEZONE_OPTIONS.map((opt) => (
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
                                                <button
                                                    key={i}
                                                    onClick={() => day.isAvailable && handleDateSelect(day.date!)}
                                                    disabled={!day.isAvailable}
                                                    className={`h-10 rounded-lg text-sm font-medium transition-colors ${isSelected
                                                        ? "bg-primary text-primary-foreground"
                                                        : day.isToday
                                                            ? "bg-primary/10 text-primary"
                                                            : day.isAvailable
                                                                ? "hover:bg-muted"
                                                                : "text-muted-foreground/40 cursor-not-allowed"
                                                        }`}
                                                >
                                                    {day.date.getDate()}
                                                </button>
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
                                        <LoaderIcon className="size-6 animate-spin text-muted-foreground" />
                                    </div>
                                ) : slots.length === 0 ? (
                                    <p className="text-muted-foreground text-center py-4">No available times</p>
                                ) : (
                                    <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 max-h-64 overflow-y-auto">
                                        {slots.map((slot) => {
                                            const time = format(parseISO(slot.start), "h:mm a")
                                            const isSelected = selectedSlot?.start === slot.start
                                            return (
                                                <button
                                                    key={slot.start}
                                                    onClick={() => setSelectedSlot(slot)}
                                                    className={`py-2 px-3 rounded-lg border text-sm font-medium transition-all ${isSelected
                                                        ? "border-primary bg-primary text-primary-foreground"
                                                        : "border-border hover:border-primary/50"
                                                        }`}
                                                >
                                                    {time}
                                                </button>
                                            )
                                        })}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Submit */}
                        {selectedSlot && (
                            <Button className="w-full" size="lg" onClick={handleSubmit} disabled={isSubmitting}>
                                {isSubmitting && <LoaderIcon className="size-4 mr-2 animate-spin" />}
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
