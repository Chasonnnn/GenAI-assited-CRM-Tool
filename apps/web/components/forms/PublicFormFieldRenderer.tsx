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
import { splitHeightFt, totalInchesToHeightFt } from "@/lib/height"
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

function isDobField(field: FormField): boolean {
    const key = field.key.trim().toLowerCase()
    const label = field.label.trim().toLowerCase()

    return (
        key === "dob" ||
        /\bdob\b/.test(key) ||
        key.includes("date_of_birth") ||
        key.includes("birth_date") ||
        label.includes("date of birth") ||
        label.includes("birth date") ||
        /\bdob\b/.test(label)
    )
}

function parseHeightSelection(value: PublicFormAnswerValue | undefined): { feet: string; inches: string } {
    return splitHeightFt(
        typeof value === "string" || typeof value === "number" ? value : null,
    )
}

function serializeHeightSelection(feet: string, inches: string): string | null {
    if (feet === "" && inches === "") {
        return null
    }

    const normalizedHeight = totalInchesToHeightFt((Number(feet || 0) * 12) + Number(inches || 0))
    return normalizedHeight === null ? null : normalizedHeight.toFixed(2)
}

function normalizeFixedTableRows(
    field: FormField,
    value: PublicFormAnswerValue | undefined,
): TableRow[] {
    const configuredRows = field.rows || []
    const existingRows = Array.isArray(value)
        ? value.filter((item): item is TableRow => Boolean(item) && typeof item === "object" && !Array.isArray(item))
        : []
    const existingByRowKey = new Map<string, TableRow>()

    existingRows.forEach((row) => {
        const rowKey = row.row_key
        if (typeof rowKey === "string" && rowKey) {
            existingByRowKey.set(rowKey, row)
        }
    })

    return configuredRows.map((row) => ({
        ...(existingByRowKey.get(row.key) || {}),
        row_key: row.key,
    }))
}

function FixedTableFieldInput({
    field,
    value,
    requiredMark,
    updateField,
}: {
    field: FormField
    value: PublicFormAnswerValue | undefined
    requiredMark: React.ReactNode
    updateField: (fieldKey: string, value: PublicFormAnswerValue) => void
}) {
    const columns = field.columns || []
    const rows = React.useMemo(() => normalizeFixedTableRows(field, value), [field, value])

    const updateCell = (rowKey: string, columnKey: string, nextValue: string) => {
        const nextRows = rows.map((row) =>
            row.row_key === rowKey ? { ...row, [columnKey]: nextValue } : row,
        )
        updateField(field.key, nextRows)
    }

    if (columns.length === 0 || (field.rows?.length ?? 0) === 0) {
        return (
            <div key={field.key} className="space-y-2 rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <Label className="text-sm font-medium">
                    {field.label} {requiredMark}
                </Label>
                <p className="text-sm text-stone-500">Configure rows and columns to use this table field.</p>
            </div>
        )
    }

    return (
        <div key={field.key} className="space-y-3 rounded-2xl border border-stone-200 bg-stone-50 p-4">
            <div className="space-y-1">
                <Label className="text-sm font-medium">
                    {field.label} {requiredMark}
                </Label>
                {field.help_text ? <p className="text-xs text-stone-500">{field.help_text}</p> : null}
            </div>

            <div className="space-y-3">
                {rows.map((row) => {
                    const rowKey = typeof row.row_key === "string" ? row.row_key : ""
                    const rowDefinition = field.rows?.find((item) => item.key === rowKey)
                    const rowLabel = rowDefinition?.label || rowKey || "Row"
                    const rowHelpText = rowDefinition?.help_text || ""

                    return (
                        <div
                            key={rowKey || rowLabel}
                            role="group"
                            aria-label={`${rowLabel} row`}
                            className="rounded-2xl border border-stone-200 bg-white p-4 @container/table-row @xl/table-row:grid @xl/table-row:grid-cols-[minmax(0,10rem)_minmax(0,12rem)_minmax(0,1fr)] @xl/table-row:items-start @xl/table-row:gap-4"
                        >
                            <div className="mb-4 space-y-1 @xl/table-row:mb-0 @xl/table-row:pr-2">
                                <div className="text-base font-semibold text-stone-900">{rowLabel}</div>
                                {rowHelpText ? <p className="mt-1 text-xs text-stone-500">{rowHelpText}</p> : null}
                            </div>

                            {columns.map((column) => {
                                const cellValue = row[column.key]
                                const normalizedValue =
                                    cellValue === null || cellValue === undefined ? "" : String(cellValue)
                                const options =
                                    column.options && column.options.length > 0
                                        ? column.options
                                        : column.type === "radio"
                                            ? [
                                                  { label: "No", value: "no" },
                                                  { label: "Yes", value: "yes" },
                                              ]
                                            : []

                                return (
                                    <div key={column.key} className="space-y-2 @xl/table-row:min-w-0">
                                        <Label className="text-[11px] font-semibold uppercase tracking-[0.16em] text-stone-500">
                                            {column.label}
                                            {column.required ? <span className="text-red-500"> *</span> : null}
                                        </Label>

                                        {column.type === "radio" ? (
                                            <div className="grid gap-2 sm:grid-cols-2">
                                                {options.map((option) => (
                                                    <OptionCard
                                                        key={option.value}
                                                        selected={normalizedValue === option.value}
                                                        onClick={() => updateCell(rowKey, column.key, option.value)}
                                                        label={option.label}
                                                        size="compact"
                                                    />
                                                ))}
                                            </div>
                                        ) : column.type === "select" ? (
                                            <select
                                                className="h-11 w-full rounded-xl border border-stone-200 bg-white px-3 text-sm shadow-none"
                                                value={normalizedValue}
                                                onChange={(event) => updateCell(rowKey, column.key, event.target.value)}
                                            >
                                                <option value="">Select...</option>
                                                {options.map((option) => (
                                                    <option key={option.value} value={option.value}>
                                                        {option.label}
                                                    </option>
                                                ))}
                                            </select>
                                        ) : column.type === "textarea" ? (
                                            <Input
                                                type="text"
                                                value={normalizedValue}
                                                onChange={(event) => updateCell(rowKey, column.key, event.target.value)}
                                                placeholder={column.label}
                                                className="h-11 rounded-xl border-stone-200 bg-white shadow-none"
                                            />
                                        ) : (
                                            <Input
                                                type={
                                                    column.type === "number"
                                                        ? "number"
                                                        : column.type === "date"
                                                            ? "date"
                                                            : "text"
                                                }
                                                value={normalizedValue}
                                                onChange={(event) => updateCell(rowKey, column.key, event.target.value)}
                                                placeholder={column.label}
                                                className="h-11 rounded-xl border-stone-200 bg-white shadow-none"
                                            />
                                        )}
                                    </div>
                                )
                            })}
                        </div>
                    )
                })}
            </div>
        </div>
    )
}

function HeightFieldInput({
    field,
    value,
    requiredMark,
    updateField,
}: {
    field: FormField
    value: PublicFormAnswerValue | undefined
    requiredMark: React.ReactNode
    updateField: (fieldKey: string, value: PublicFormAnswerValue) => void
}) {
    const parsedSelection = React.useMemo(() => parseHeightSelection(value), [value])
    const [feetValue, setFeetValue] = React.useState(() => parsedSelection.feet)
    const [inchesValue, setInchesValue] = React.useState(() => parsedSelection.inches)
    const serializedSelection = React.useMemo(
        () => serializeHeightSelection(feetValue, inchesValue),
        [feetValue, inchesValue],
    )
    const serializedIncomingValue = React.useMemo(
        () => serializeHeightSelection(parsedSelection.feet, parsedSelection.inches),
        [parsedSelection.feet, parsedSelection.inches],
    )

    React.useEffect(() => {
        if (serializedIncomingValue === serializedSelection) {
            return
        }
        setFeetValue(parsedSelection.feet)
        setInchesValue(parsedSelection.inches)
    }, [parsedSelection.feet, parsedSelection.inches, serializedIncomingValue, serializedSelection])

    const syncHeight = (nextFeet: string, nextInches: string) => {
        setFeetValue(nextFeet)
        setInchesValue(nextInches)
        updateField(field.key, serializeHeightSelection(nextFeet, nextInches))
    }

    return (
        <div key={field.key} className="space-y-3 rounded-2xl border border-stone-200 bg-stone-50 p-4">
            <Label className="text-sm font-medium">
                {field.label} {requiredMark}
            </Label>
            <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                    <Label
                        htmlFor={`${field.key}_ft`}
                        className="text-xs font-medium uppercase tracking-[0.2em] text-stone-500"
                    >
                        {field.label} Feet
                    </Label>
                    <select
                        id={`${field.key}_ft`}
                        aria-label={`${field.label} Feet`}
                        value={feetValue}
                        onChange={(event) => syncHeight(event.target.value, inchesValue)}
                        className="h-11 w-full rounded-xl border border-stone-200 bg-white px-3 text-sm shadow-none"
                    >
                        <option value="">ft</option>
                        {Array.from({ length: 9 }, (_, value) => value).map((value) => (
                            <option key={`feet-${value}`} value={value}>
                                {value} ft
                            </option>
                        ))}
                    </select>
                </div>
                <div className="space-y-2">
                    <Label
                        htmlFor={`${field.key}_in`}
                        className="text-xs font-medium uppercase tracking-[0.2em] text-stone-500"
                    >
                        {field.label} Inches
                    </Label>
                    <select
                        id={`${field.key}_in`}
                        aria-label={`${field.label} Inches`}
                        value={inchesValue}
                        onChange={(event) => syncHeight(feetValue, event.target.value)}
                        className="h-11 w-full rounded-xl border border-stone-200 bg-white px-3 text-sm shadow-none"
                    >
                        <option value="">in</option>
                        {Array.from({ length: 12 }, (_, value) => value).map((value) => (
                            <option key={`inches-${value}`} value={value}>
                                {value} in
                            </option>
                        ))}
                    </select>
                </div>
            </div>
            {field.help_text && <p className="text-xs text-stone-500">{field.help_text}</p>}
        </div>
    )
}

function OptionCard({
    selected,
    onClick,
    label,
    selectionRole = "radio",
    size = "default",
}: {
    selected: boolean
    onClick: () => void
    label: string
    selectionRole?: "radio" | "checkbox"
    size?: "default" | "compact"
}) {
    return (
        <button
            type="button"
            role={selectionRole}
            aria-checked={selected}
            onClick={onClick}
            className={cn(
                "w-full border border-stone-200 bg-white text-left transition-all",
                size === "compact" ? "rounded-xl px-3 py-2.5" : "rounded-2xl p-4",
                "hover:border-primary/60 hover:bg-primary/5",
                "focus:outline-none focus:ring-2 focus:ring-primary/20 focus:ring-offset-2",
                selected ? "border-primary bg-primary/10" : "border-stone-200",
            )}
        >
            <div className="flex items-center gap-3">
                <div
                    className={cn(
                        "flex items-center justify-center rounded-full border-2 transition-all",
                        size === "compact" ? "size-5" : "size-6",
                        selected ? "border-primary bg-primary" : "border-stone-300 bg-white",
                    )}
                >
                    {selected && <CheckIcon className={cn("text-white", size === "compact" ? "size-3.5" : "size-4")} />}
                </div>
                <div className={cn("font-medium text-stone-900", size === "compact" ? "text-[15px]" : "text-sm")}>
                    {label}
                </div>
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
        const usesDobPickerNavigation = isDobField(field)

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
                            {...(usesDobPickerNavigation
                                ? {
                                      captionLayout: "dropdown" as const,
                                      startMonth: new Date(1950, 0),
                                      endMonth: new Date(),
                                  }
                                : {})}
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
        return (
            <HeightFieldInput
                field={field}
                value={value}
                requiredMark={requiredMark}
                updateField={updateField}
            />
        )
    }

    if (field.type === "table") {
        return (
            <FixedTableFieldInput
                field={field}
                value={value}
                requiredMark={requiredMark}
                updateField={updateField}
            />
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
