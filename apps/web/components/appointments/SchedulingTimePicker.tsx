"use client"

import { useEffect, useId, useRef } from "react"
import { startOfMonth } from "date-fns"
import { Loader2Icon } from "lucide-react"
import { Calendar } from "@/components/ui/calendar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
    formatSchedulingDate,
    formatSchedulingTime,
    schedulingDateKey,
    schedulingTimezoneLabel,
} from "@/lib/scheduling-time"
import { cn } from "@/lib/utils"
import { formatLocalDate, parseDateInput } from "@/lib/utils/date"

type Slot = { start: string; end: string }

export interface SchedulingSlotListProps {
    slots?: readonly Slot[] | undefined
    timezone: string
    selectedStart: string | null
    onSelectStart: (start: string) => void
    loading?: boolean | undefined
    error?: string | null | undefined
    onRetry?: (() => void) | undefined
    disabled?: boolean | undefined
}

export function SchedulingSlotList({
    slots = [], timezone, selectedStart, onSelectStart, loading, error, onRetry, disabled,
}: SchedulingSlotListProps) {
    if (loading) return <p role="status" className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Loader2Icon className="size-4 animate-spin" />Loading available times…</p>
    if (error) return <div className="space-y-3 rounded-lg border border-destructive/20 bg-destructive/5 p-3">
        <p role="alert" className="text-sm text-destructive">{error}</p>
        {onRetry ? <Button type="button" size="sm" variant="outline" onClick={onRetry} disabled={disabled}>Retry availability</Button> : null}
    </div>
    if (!slots.length) return <p role="status" className="py-4 text-sm text-muted-foreground">No available times on this date.</p>
    return <div role="group" aria-label="Available times" className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {slots.map(slot => {
            // The zone abbreviation distinguishes repeated wall-clock times at the DST boundary.
            const accessibleTime = new Intl.DateTimeFormat(undefined, {
                timeZone: timezone, hour: "numeric", minute: "2-digit", timeZoneName: "short",
            }).format(new Date(slot.start))
            return <Button
                key={slot.start}
                type="button"
                variant={selectedStart === slot.start ? "default" : "outline"}
                className="h-10 tabular-nums"
                aria-label={accessibleTime}
                aria-pressed={selectedStart === slot.start}
                disabled={disabled}
                onClick={() => onSelectStart(slot.start)}
            >{formatSchedulingTime(slot.start, timezone)}</Button>
        })}
    </div>
}

type AvailabilityOverride = {
    enabled: boolean
    onEnabledChange: (enabled: boolean) => void
    dateTime: string
    onDateTimeChange: (value: string) => void
    reason: string
    onReasonChange: (value: string) => void
}

export interface SchedulingTimePickerProps extends SchedulingSlotListProps {
    idPrefix: string
    date: string
    onDateChange: (date: string) => void
    minDate?: string | undefined
    availableDates?: ReadonlySet<string> | undefined
    datesLoading?: boolean | undefined
    month?: Date | undefined
    onMonthChange?: (month: Date) => void
    /** Each new value moves focus to the selected day, or to the next-month arrow when that day is closed. */
    dateFocusRequest?: number | undefined
    override?: AvailabilityOverride
}

function LoadingCaptionLabel({ className, children, ...props }: React.ComponentProps<"span">) {
    return <span className={cn(className, "inline-flex items-center gap-1.5")} {...props}>
        {children}<Loader2Icon className="size-3.5 animate-spin text-muted-foreground" aria-hidden="true" />
    </span>
}

export function SchedulingTimePicker({
    idPrefix, date, onDateChange, minDate, availableDates, datesLoading, month, onMonthChange, dateFocusRequest, override,
    slots, timezone, selectedStart, onSelectStart, loading, error, onRetry, disabled,
}: SchedulingTimePickerProps) {
    const uniqueId = useId()
    const dateId = `${idPrefix}-${uniqueId}-date-time`
    const reasonId = `${idPrefix}-${uniqueId}-reason`
    const calendarRef = useRef<HTMLDivElement>(null)
    const handledFocusRequest = useRef<number | undefined>(undefined)
    const firstDate = minDate ?? schedulingDateKey(new Date(), timezone)
    const selectedDate = date ? parseDateInput(date) : undefined
    const selectedSlot = slots?.find(slot => slot.start === selectedStart)

    // The caller picks the date after mount (from a request), so focus follows each request once.
    useEffect(() => {
        if (!dateFocusRequest || !date || handledFocusRequest.current === dateFocusRequest) return
        handledFocusRequest.current = dateFocusRequest
        const calendar = calendarRef.current
        const day = calendar?.querySelector<HTMLButtonElement>(`[data-day="${date}"] button:not(:disabled)`)
        ;(day ?? calendar?.querySelector<HTMLButtonElement>(".rdp-button_next:not([aria-disabled=true])"))?.focus()
    }, [dateFocusRequest, date])

    if (override?.enabled) return <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm font-medium">Custom time</span>
            <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={() => override.onEnabledChange(false)}>Use available times</Button>
        </div>
        <div className="space-y-2">
            <Label htmlFor={dateId}>Date and time · {schedulingTimezoneLabel(timezone)}</Label>
            <Input id={dateId} type="datetime-local" value={override.dateTime} min={`${firstDate}T00:00`} onValueChange={override.onDateTimeChange} disabled={disabled} required />
        </div>
        <div className="space-y-2">
            <Label htmlFor={reasonId}>Reason <span className="text-muted-foreground">required</span></Label>
            <Input id={reasonId} value={override.reason} onValueChange={override.onReasonChange} disabled={disabled} required />
        </div>
    </div>

    return <div className="@container space-y-4">
        <div className="text-sm text-muted-foreground">{schedulingTimezoneLabel(timezone)}</div>
        <div className="grid items-start gap-4 @min-[32rem]:grid-cols-[minmax(16rem,1fr)_minmax(0,1fr)]">
            <div ref={calendarRef} aria-busy={datesLoading || undefined}>
                <Calendar
                    mode="single"
                    selected={selectedDate}
                    {...(month ? { month } : { defaultMonth: selectedDate ?? parseDateInput(firstDate) })}
                    // Months before the first selectable day have nothing to pick.
                    startMonth={startOfMonth(parseDateInput(firstDate))}
                    {...(onMonthChange ? { onMonthChange } : {})}
                    {...(datesLoading ? { components: { CaptionLabel: LoadingCaptionLabel } } : {})}
                    onSelect={next => { if (next) onDateChange(formatLocalDate(next)) }}
                    disabled={day => disabled === true || formatLocalDate(day) < firstDate || Boolean(availableDates && !availableDates.has(formatLocalDate(day)))}
                    className="w-full p-0 [--cell-size:--spacing(8)]"
                    // With known open days, an open day of the next or previous month reads as pickable.
                    classNames={{ month_grid: "w-full", ...(availableDates ? { outside: "" } : {}) }}
                />
            </div>
            <div className="min-w-0 space-y-3">
                {date ? <p className="text-sm font-medium">{parseDateInput(date).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}</p> : null}
                {date || loading || error ? <SchedulingSlotList
                    {...(slots ? { slots } : {})}
                    timezone={timezone}
                    selectedStart={selectedStart}
                    onSelectStart={onSelectStart}
                    {...(loading !== undefined ? { loading } : {})}
                    {...(error !== undefined ? { error } : {})}
                    {...(onRetry ? { onRetry } : {})}
                    {...(disabled !== undefined ? { disabled } : {})}
                /> : <p className="py-4 text-sm text-muted-foreground">Choose a date.</p>}
            </div>
        </div>
        {selectedSlot && !loading && !error ? <p role="status" className="rounded-lg bg-primary/5 px-3 py-2 text-sm text-primary">
            {formatSchedulingDate(selectedSlot.start, timezone)} · {formatSchedulingTime(selectedSlot.start, timezone)} · {schedulingTimezoneLabel(timezone)}
        </p> : null}
        {override ? <div className="border-t pt-3"><Button type="button" variant="ghost" size="sm" className="h-auto whitespace-normal px-0 text-left text-muted-foreground" disabled={disabled} onClick={() => override.onEnabledChange(true)}>Choose a time outside availability</Button></div> : null}
    </div>
}
