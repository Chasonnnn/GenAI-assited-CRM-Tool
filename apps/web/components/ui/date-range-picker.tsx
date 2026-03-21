"use client"

import * as React from "react"
import { CalendarIcon, ChevronDownIcon } from "lucide-react"
import { isSameDay } from "date-fns"
import type { DateRange as DayPickerDateRange } from "react-day-picker"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover"
import { cn } from "@/lib/utils"
import { formatLocalDate } from "@/lib/utils/date"

export type DateRangePreset = 'all' | 'today' | 'week' | 'month' | 'custom'

interface DateRange {
    from: Date | undefined
    to: Date | undefined
}

interface DateRangePickerProps {
    preset: DateRangePreset
    onPresetChange: (preset: DateRangePreset) => void
    customRange?: DateRange
    onCustomRangeChange?: (range: DateRange) => void
    availableDateKeys?: string[]
    className?: string
    ariaLabel?: string
}

const presetLabels: Record<DateRangePreset, string> = {
    all: 'All Time',
    today: 'Today',
    week: 'This Week',
    month: 'This Month',
    custom: 'Custom',
}

export function DateRangePicker({
    preset,
    onPresetChange,
    customRange,
    onCustomRangeChange,
    availableDateKeys,
    className,
    ariaLabel,
}: DateRangePickerProps) {
    const [open, setOpen] = React.useState(false)
    const [showCalendar, setShowCalendar] = React.useState(false)
    const [localRange, setLocalRange] = React.useState<DateRange>({
        from: customRange?.from,
        to: customRange?.to,
    })

    // Reset local range when opening calendar
    const handleShowCalendar = () => {
        setLocalRange({ from: customRange?.from, to: customRange?.to })
        setShowCalendar(true)
    }

    const availableDateSet = React.useMemo(() => {
        if (!availableDateKeys?.length) return null
        return new Set(availableDateKeys)
    }, [availableDateKeys])

    const handlePresetSelect = (newPreset: DateRangePreset) => {
        if (newPreset === 'custom') {
            handleShowCalendar()
        } else {
            onPresetChange(newPreset)
            setOpen(false)
            setShowCalendar(false)
        }
    }

    const handleRangeSelect = (range: DayPickerDateRange | undefined) => {
        const newRange: DateRange = {
            from: range?.from,
            to: range?.to
        }

        // `react-day-picker` returns `{from: date, to: date}` on the first click when `min` is 0.
        // Treat that first click as selecting only the start date so users can pick an end date
        // without the popover closing.
        if (
            !localRange.from &&
            !localRange.to &&
            newRange.from &&
            newRange.to &&
            isSameDay(newRange.from, newRange.to)
        ) {
            setLocalRange({ from: newRange.from, to: undefined })
            return
        }

        setLocalRange(newRange)
    }

    const handleApply = () => {
        if (localRange.from && localRange.to) {
            // Some parents store the preset and the concrete range separately.
            // Apply the preset first so the subsequent range update wins with the selected dates.
            onPresetChange('custom')
            onCustomRangeChange?.(localRange)
            setOpen(false)
            setShowCalendar(false)
        }
    }

    const getDisplayLabel = () => {
        if (preset === 'custom' && customRange?.from && customRange?.to) {
            return `${shortDateFormatter.format(customRange.from)} - ${shortDateFormatter.format(customRange.to)}`
        }
        return presetLabels[preset]
    }

    return (
        <Popover open={open} onOpenChange={(newOpen, eventDetails) => {
            // When the calendar is open, ignore Base UI's "focus-out" closes while the user is picking a range,
            // but still allow explicit dismiss actions like clicking outside, pressing Escape, or toggling trigger.
            if (!newOpen && showCalendar) {
                const reason = eventDetails.reason
                const allowClose =
                    reason === "outside-press" ||
                    reason === "escape-key" ||
                    reason === "trigger-press"

                if (allowClose) {
                    setOpen(false)
                    setShowCalendar(false)
                }
                return
            }

            setOpen(newOpen)
            if (!newOpen) setShowCalendar(false)
        }}>
            <PopoverTrigger
                className={cn(
                    "inline-flex max-w-full min-w-[13rem] items-center justify-between gap-2 rounded-md border border-input bg-background px-3 py-2 text-sm font-normal hover:bg-accent hover:text-accent-foreground",
                    className
                )}
                aria-label={ariaLabel}
            >
                <CalendarIcon className="size-4 shrink-0" aria-hidden="true" />
                <span className="min-w-0 flex-1 text-left whitespace-nowrap">
                    {getDisplayLabel()}
                </span>
                <ChevronDownIcon className="size-4 shrink-0 opacity-50" aria-hidden="true" />
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="start">
                {!showCalendar ? (
                    <div className="flex flex-col p-1">
                        {(['all', 'today', 'week', 'month'] as DateRangePreset[]).map((p) => (
                            <Button
                                key={p}
                                variant={preset === p ? "secondary" : "ghost"}
                                className="justify-start"
                                onClick={() => handlePresetSelect(p)}
                            >
                                {presetLabels[p]}
                            </Button>
                        ))}
                        <div className="border-t my-1" />
                        <Button
                            variant={preset === 'custom' ? "secondary" : "ghost"}
                            className="justify-start"
                            onClick={() => handlePresetSelect('custom')}
                        >
                            <CalendarIcon className="size-4 mr-2" aria-hidden="true" />
                            Custom Range…
                        </Button>
                    </div>
                ) : (
                    <div className="p-3">
                        <div className="mb-3 flex items-center justify-between">
                            <div className="flex flex-col">
                                <span className="text-sm font-medium">Select date range</span>
                                {localRange.from && (
                                    <span className="text-xs text-muted-foreground">
                                        {localRange.from && longDateFormatter.format(localRange.from)}
                                        {localRange.to && ` → ${longDateFormatter.format(localRange.to)}`}
                                        {!localRange.to && ' → Select end date'}
                                    </span>
                                )}
                            </div>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setShowCalendar(false)}
                            >
                                Back
                            </Button>
                        </div>
                        <Calendar
                            mode="range"
                            selected={localRange}
                            onSelect={handleRangeSelect}
                            disabled={
                                availableDateSet
                                    ? (date) => !availableDateSet.has(formatLocalDate(date))
                                    : undefined
                            }
                            numberOfMonths={2}
                            defaultMonth={localRange.from || new Date()}
                            className="rounded-md border shadow-sm"
                        />
                        <div className="mt-3 flex items-center justify-between border-t pt-3">
                            <div className="text-xs text-muted-foreground">
                                {localRange.from && localRange.to
                                    ? 'Range selected. Click Apply.'
                                    : availableDateSet
                                        ? 'Select from available created dates only'
                                        : 'Click start date, then end date'}
                            </div>
                            <Button
                                size="sm"
                                disabled={!localRange.from || !localRange.to}
                                onClick={handleApply}
                            >
                                Apply
                            </Button>
                        </div>
                    </div>
                )}
            </PopoverContent>
        </Popover>
    )
}
    const shortDateFormatter = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" })
    const longDateFormatter = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" })
