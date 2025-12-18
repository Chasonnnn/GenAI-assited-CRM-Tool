"use client"

import * as React from "react"
import { CalendarIcon, ClockIcon, ChevronDownIcon } from "lucide-react"
import { format } from "date-fns"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/lib/utils"

export interface DateTimePickerProps {
    value: Date | undefined
    onChange: (value: Date | undefined) => void
    className?: string
    disabled?: boolean
    placeholder?: string
}

function parseTime(value: string): { hours: number; minutes: number } | null {
    const match = /^(\d{2}):(\d{2})$/.exec(value)
    if (!match) return null
    const hours = Number(match[1])
    const minutes = Number(match[2])
    if (!Number.isFinite(hours) || !Number.isFinite(minutes)) return null
    if (hours < 0 || hours > 23) return null
    if (minutes < 0 || minutes > 59) return null
    return { hours, minutes }
}

export function DateTimePicker({
    value,
    onChange,
    className,
    disabled = false,
    placeholder = "Select date & time",
}: DateTimePickerProps) {
    const [open, setOpen] = React.useState(false)
    const [draftDate, setDraftDate] = React.useState<Date | undefined>(value)
    const [draftTime, setDraftTime] = React.useState<string>(value ? format(value, "HH:mm") : "09:00")

    React.useEffect(() => {
        if (!open) return
        setDraftDate(value)
        setDraftTime(value ? format(value, "HH:mm") : "09:00")
    }, [open, value])

    const displayLabel = value ? format(value, "MMM d, yyyy 'at' h:mm a") : placeholder

    const apply = () => {
        if (!draftDate) {
            onChange(undefined)
            setOpen(false)
            return
        }

        const parsed = parseTime(draftTime)
        const next = new Date(draftDate)
        if (parsed) {
            next.setHours(parsed.hours, parsed.minutes, 0, 0)
        } else {
            next.setHours(9, 0, 0, 0)
        }
        onChange(next)
        setOpen(false)
    }

    return (
        <Popover
            open={open}
            onOpenChange={(newOpen, eventDetails) => {
                if (!newOpen) {
                    const reason = eventDetails.reason
                    const allowClose =
                        reason === "outside-press" ||
                        reason === "escape-key" ||
                        reason === "trigger-press"
                    if (!allowClose) return
                }
                setOpen(newOpen)
            }}
        >
            <PopoverTrigger
                className={cn(
                    "inline-flex w-full items-center justify-between gap-2 rounded-md border border-input bg-background px-3 py-2 text-sm font-normal hover:bg-accent hover:text-accent-foreground",
                    disabled && "pointer-events-none opacity-50",
                    className
                )}
                aria-disabled={disabled}
            >
                <span className="inline-flex items-center gap-2">
                    <CalendarIcon className="size-4" />
                    {displayLabel}
                </span>
                <ChevronDownIcon className="size-4 opacity-50" />
            </PopoverTrigger>
            <PopoverContent className="w-auto p-3" align="start">
                <div className="space-y-3">
                    <div className="space-y-1">
                        <div className="text-sm font-medium">Select date & time</div>
                        <div className="text-xs text-muted-foreground">
                            {draftDate ? format(draftDate, "MMM d, yyyy") : "Pick a date"}
                        </div>
                    </div>

                    <Calendar
                        mode="single"
                        selected={draftDate}
                        onSelect={setDraftDate}
                        defaultMonth={draftDate || new Date()}
                        className="rounded-md border shadow-sm"
                    />

                    <div className="space-y-2">
                        <Label className="inline-flex items-center gap-2">
                            <ClockIcon className="size-4" />
                            Time
                        </Label>
                        <Input
                            type="time"
                            value={draftTime}
                            onChange={(e) => setDraftTime(e.target.value)}
                        />
                    </div>

                    <div className="flex items-center justify-end gap-2 border-t pt-3">
                        <Button variant="outline" size="sm" onClick={() => setOpen(false)}>
                            Cancel
                        </Button>
                        <Button size="sm" onClick={apply} disabled={!draftDate}>
                            Apply
                        </Button>
                    </div>
                </div>
            </PopoverContent>
        </Popover>
    )
}

