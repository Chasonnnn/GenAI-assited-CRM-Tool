"use client"

import * as React from "react"
import { CalendarIcon, ChevronDownIcon } from "lucide-react"
import { format } from "date-fns"
import type { DateRange as DayPickerDateRange } from "react-day-picker"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover"
import { cn } from "@/lib/utils"

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
    className?: string
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
    className,
}: DateRangePickerProps) {
    const [open, setOpen] = React.useState(false)
    const [showCalendar, setShowCalendar] = React.useState(false)
    const [localRange, setLocalRange] = React.useState<DateRange>({
        from: customRange?.from,
        to: customRange?.to,
    })

    // Reset local range when opening calendar
    const handleShowCalendar = () => {
        setLocalRange({ from: undefined, to: undefined })
        setShowCalendar(true)
    }

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
        setLocalRange(newRange)

        // Only close when BOTH dates are selected
        if (newRange.from && newRange.to) {
            onCustomRangeChange?.(newRange)
            onPresetChange('custom')
            // Small delay so user can see the final selection
            setTimeout(() => {
                setOpen(false)
                setShowCalendar(false)
            }, 300)
        }
    }

    const handleApply = () => {
        if (localRange.from && localRange.to) {
            onCustomRangeChange?.(localRange)
            onPresetChange('custom')
            setOpen(false)
            setShowCalendar(false)
        }
    }

    const getDisplayLabel = () => {
        if (preset === 'custom' && customRange?.from && customRange?.to) {
            return `${format(customRange.from, 'MMM d')} - ${format(customRange.to, 'MMM d')}`
        }
        return presetLabels[preset]
    }

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger
                className={cn(
                    "inline-flex items-center justify-between gap-2 rounded-md border border-input bg-background px-3 py-2 text-sm font-normal hover:bg-accent hover:text-accent-foreground w-44",
                    className
                )}
            >
                <CalendarIcon className="size-4" />
                {getDisplayLabel()}
                <ChevronDownIcon className="size-4 opacity-50" />
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
                            <CalendarIcon className="size-4 mr-2" />
                            Custom Range...
                        </Button>
                    </div>
                ) : (
                    <div className="p-3">
                        <div className="mb-3 flex items-center justify-between">
                            <div className="flex flex-col">
                                <span className="text-sm font-medium">Select date range</span>
                                {localRange.from && (
                                    <span className="text-xs text-muted-foreground">
                                        {localRange.from && format(localRange.from, 'MMM d, yyyy')}
                                        {localRange.to && ` → ${format(localRange.to, 'MMM d, yyyy')}`}
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
                            numberOfMonths={2}
                            defaultMonth={localRange.from || new Date()}
                            className="rounded-md border shadow-sm"
                        />
                        <div className="mt-3 flex items-center justify-between border-t pt-3">
                            <div className="text-xs text-muted-foreground">
                                {localRange.from && localRange.to
                                    ? 'Range selected! Click Apply or it will auto-apply.'
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
