"use client"

import * as React from "react"
import { CalendarIcon, CheckIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Textarea } from "@/components/ui/textarea"
import type { FormField } from "@/lib/api/forms"
import { cn } from "@/lib/utils"
import { formatLocalDate, parseDateInput } from "@/lib/utils/date"

type TableRow = Record<string, string | number | null>
export type PublicFormAnswerValue =
    | string
    | number
    | boolean
    | string[]
    | TableRow[]
    | null

interface PublicFormFieldRendererProps {
    field: FormField
    value: PublicFormAnswerValue | undefined
    updateField: (fieldKey: string, value: PublicFormAnswerValue) => void
    datePickerOpen: Record<string, boolean>
    setDatePickerOpen: React.Dispatch<React.SetStateAction<Record<string, boolean>>>
}

function formatDate(value: string | null): string {
    if (!value) return ""
    return formatLocalDate(parseDateInput(value))
}

function OptionCard({
    selected,
    onClick,
    label,
    selectionRole = "radio",
}: {
    selected: boolean
    onClick: () => void
    label: string
    selectionRole?: "radio" | "checkbox"
}) {
    return (
        <button
            type="button"
            role={selectionRole}
            aria-checked={selected}
            onClick={onClick}
            className={cn(
                "w-full rounded-2xl border border-stone-200 bg-white p-4 text-left transition-all",
                "hover:border-primary/60 hover:bg-primary/5",
                "focus:outline-none focus:ring-2 focus:ring-primary/20 focus:ring-offset-2",
                selected ? "border-primary bg-primary/10" : "border-stone-200",
            )}
        >
            <div className="flex items-center gap-3">
                <div
                    className={cn(
                        "flex size-6 items-center justify-center rounded-full border-2 transition-all",
                        selected ? "border-primary bg-primary" : "border-stone-300 bg-white",
                    )}
                >
                    {selected && <CheckIcon className="size-4 text-white" />}
                </div>
                <div className="font-medium text-stone-900">{label}</div>
            </div>
        </button>
    )
}

export function PublicFormFieldRenderer({
    field,
    value,
    updateField,
    datePickerOpen,
    setDatePickerOpen,
}: PublicFormFieldRendererProps) {
    const requiredMark = field.required ? <span className="text-red-500">*</span> : null

    if (field.type === "textarea") {
        return (
            <div key={field.key} className="space-y-2 rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <Label htmlFor={field.key} className="text-sm font-medium">
                    {field.label} {requiredMark}
                </Label>
                <Textarea
                    id={field.key}
                    value={typeof value === "string" ? value : ""}
                    onChange={(event) => updateField(field.key, event.target.value)}
                    placeholder={field.label}
                    className="min-h-24 rounded-xl border-stone-200 bg-white shadow-none"
                />
                {field.help_text && <p className="text-xs text-stone-500">{field.help_text}</p>}
            </div>
        )
    }

    if (field.type === "date") {
        const isOpen = datePickerOpen[field.key] || false
        const dateValue = typeof value === "string" ? parseDateInput(value) : undefined

        return (
            <div key={field.key} className="space-y-2 rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <Label className="text-sm font-medium">
                    {field.label} {requiredMark}
                </Label>
                <Popover
                    open={isOpen}
                    onOpenChange={(open) =>
                        setDatePickerOpen((prev) => ({ ...prev, [field.key]: open }))
                    }
                >
                    <PopoverTrigger
                        render={
                            <Button
                                variant="outline"
                                className={cn(
                                    "h-11 w-full justify-start rounded-xl border-stone-200 bg-white text-left font-normal shadow-none",
                                    !value && "text-stone-500",
                                )}
                            >
                                <CalendarIcon className="mr-2 size-4" />
                                {typeof value === "string" ? formatDate(value) : "Select a date"}
                            </Button>
                        }
                    />
                    <PopoverContent className="w-auto p-0" align="start">
                        <Calendar
                            mode="single"
                            captionLayout="dropdown"
                            startMonth={new Date(1950, 0)}
                            endMonth={new Date()}
                            selected={dateValue}
                            onSelect={(date) => {
                                updateField(field.key, date ? formatLocalDate(date) : null)
                                setDatePickerOpen((prev) => ({ ...prev, [field.key]: false }))
                            }}
                            initialFocus
                        />
                    </PopoverContent>
                </Popover>
                {field.help_text && <p className="text-xs text-stone-500">{field.help_text}</p>}
            </div>
        )
    }

    if (field.type === "height") {
        const numericValue =
            typeof value === "string" ? parseFloat(value) : typeof value === "number" ? value : NaN
        const hasParsed = !Number.isNaN(numericValue) && numericValue >= 0
        const feet = hasParsed ? Math.floor(numericValue) : ""
        const inches = hasParsed ? Math.round((numericValue - Math.floor(numericValue)) * 12) : ""

        const computeDecimal = (ft: number, inc: number) => (ft + inc / 12).toFixed(2)

        return (
            <div key={field.key} className="space-y-3 rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <Label className="text-sm font-medium">
                    {field.label} {requiredMark}
                </Label>
                <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-2">
                        <Label htmlFor={`${field.key}_ft`} className="text-xs font-medium uppercase tracking-[0.2em] text-stone-500">
                            {field.label} Feet
                        </Label>
                        <select
                            id={`${field.key}_ft`}
                            aria-label={`${field.label} Feet`}
                            value={String(feet)}
                            onChange={(event) => {
                                const ft = Number(event.target.value)
                                const inc = typeof inches === "number" ? inches : 0
                                updateField(field.key, computeDecimal(ft, inc))
                            }}
                            className="h-11 w-full rounded-xl border border-stone-200 bg-white px-3 text-sm shadow-none"
                        >
                            <option value="">ft</option>
                            {Array.from({ length: 9 }, (_, index) => (
                                <option key={index} value={index}>
                                    {index} ft
                                </option>
                            ))}
                        </select>
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor={`${field.key}_in`} className="text-xs font-medium uppercase tracking-[0.2em] text-stone-500">
                            {field.label} Inches
                        </Label>
                        <select
                            id={`${field.key}_in`}
                            aria-label={`${field.label} Inches`}
                            value={String(inches)}
                            onChange={(event) => {
                                const inc = Number(event.target.value)
                                const ft = typeof feet === "number" ? feet : 0
                                updateField(field.key, computeDecimal(ft, inc))
                            }}
                            className="h-11 w-full rounded-xl border border-stone-200 bg-white px-3 text-sm shadow-none"
                        >
                            <option value="">in</option>
                            {Array.from({ length: 12 }, (_, index) => (
                                <option key={index} value={index}>
                                    {index} in
                                </option>
                            ))}
                        </select>
                    </div>
                </div>
                {field.help_text && <p className="text-xs text-stone-500">{field.help_text}</p>}
            </div>
        )
    }

    if (field.type === "select" || field.type === "radio") {
        const options = field.options || []

        return (
            <div key={field.key} className="space-y-3 rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <Label className="text-sm font-medium">
                    {field.label} {requiredMark}
                </Label>
                {options.length === 0 ? (
                    <p className="text-sm text-stone-500">No options configured.</p>
                ) : (
                    <div className="grid gap-3 sm:grid-cols-2">
                        {options.map((option) => (
                            <OptionCard
                                key={option.value}
                                selected={value === option.value}
                                onClick={() => updateField(field.key, option.value)}
                                label={option.label}
                            />
                        ))}
                    </div>
                )}
                {field.help_text && <p className="text-xs text-stone-500">{field.help_text}</p>}
            </div>
        )
    }

    if (field.type === "multiselect") {
        const options = field.options || []
        const selectedValues = Array.isArray(value)
            ? value.filter((item): item is string => typeof item === "string")
            : []

        return (
            <div key={field.key} className="space-y-3 rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <Label className="text-sm font-medium">
                    {field.label} {requiredMark}
                </Label>
                {options.length === 0 ? (
                    <p className="text-sm text-stone-500">No options configured.</p>
                ) : (
                    <div className="grid gap-3 sm:grid-cols-2">
                        {options.map((option) => {
                            const selected = selectedValues.includes(option.value)
                            return (
                                <OptionCard
                                    key={option.value}
                                    selected={selected}
                                    selectionRole="checkbox"
                                    onClick={() => {
                                        const next = selected
                                            ? selectedValues.filter((item) => item !== option.value)
                                            : [...selectedValues, option.value]
                                        updateField(field.key, next)
                                    }}
                                    label={option.label}
                                />
                            )
                        })}
                    </div>
                )}
                {field.help_text && <p className="text-xs text-stone-500">{field.help_text}</p>}
            </div>
        )
    }

    if (field.type === "checkbox") {
        return (
            <div key={field.key} className="space-y-3 rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <div className="flex items-start gap-3">
                    <Checkbox
                        id={field.key}
                        checked={value === true}
                        onCheckedChange={(next) => updateField(field.key, next === true)}
                        className="mt-0.5"
                    />
                    <div className="space-y-1">
                        <Label htmlFor={field.key} className="text-sm font-medium leading-relaxed">
                            {field.label} {requiredMark}
                        </Label>
                        {field.help_text && <p className="text-xs text-stone-500">{field.help_text}</p>}
                    </div>
                </div>
            </div>
        )
    }

    const inputType =
        field.type === "email"
            ? "email"
            : field.type === "phone"
                ? "tel"
                : field.type === "number"
                    ? "number"
                    : "text"

    return (
        <div key={field.key} className="space-y-2 rounded-2xl border border-stone-200 bg-stone-50 p-4">
            <Label htmlFor={field.key} className="text-sm font-medium">
                {field.label} {requiredMark}
            </Label>
            <Input
                id={field.key}
                type={inputType}
                value={typeof value === "string" ? value : value ? String(value) : ""}
                onChange={(event) => updateField(field.key, event.target.value)}
                placeholder={field.label}
                className="h-11 rounded-xl border-stone-200 bg-white shadow-none"
            />
            {field.help_text && <p className="text-xs text-stone-500">{field.help_text}</p>}
        </div>
    )
}
