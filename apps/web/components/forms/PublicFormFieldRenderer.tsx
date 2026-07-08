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
type PublicFormDensity = "default" | "compact"
type FormOption = NonNullable<FormField["options"]>[number]
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
    density?: PublicFormDensity
}

function formatDate(value: string | null): string {
    if (!value) return ""
    return formatLocalDate(parseDateInput(value))
}

const publicFieldShellClassName = "space-y-2"
const publicFieldGroupShellClassName = "space-y-3 rounded-lg border border-stone-200/80 bg-stone-50/60 p-4"
const publicControlClassName = "h-11 rounded-md border-stone-200 bg-white shadow-none"

function getPublicFieldDensityStyles(density: PublicFormDensity) {
    const isCompact = density === "compact"

    return {
        fieldShellClassName: cn(publicFieldShellClassName, isCompact && "space-y-1.5"),
        fieldGroupClassName: cn(
            publicFieldGroupShellClassName,
            isCompact && "space-y-2 rounded-md bg-white p-3",
        ),
        labelClassName: cn("text-sm font-semibold leading-5 text-stone-900", isCompact && "text-stone-800"),
        controlClassName: cn(publicControlClassName, isCompact && "h-10 text-sm"),
        optionSize: (isCompact ? "compact" : "default") as "compact" | "default",
        isCompact,
    }
}

function normalizeChoiceText(value: string): string {
    return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "")
}

function getYesNoOptions(options: FormOption[]): FormOption[] | null {
    if (options.length !== 2) return null

    const yesOption = options.find((option) => {
        const label = normalizeChoiceText(option.label)
        const value = normalizeChoiceText(option.value)
        return label === "yes" || value === "yes"
    })
    const noOption = options.find((option) => {
        const label = normalizeChoiceText(option.label)
        const value = normalizeChoiceText(option.value)
        return label === "no" || value === "no"
    })

    if (!yesOption || !noOption || yesOption.value === noOption.value) return null
    return [yesOption, noOption]
}

function getChoiceOptions(options: FormOption[]): FormOption[] {
    return getYesNoOptions(options) ?? options
}

function getChoiceGridClassName(options: FormOption[], density: PublicFormDensity): string {
    const isCompact = density === "compact"
    const isYesNoChoice = getYesNoOptions(options) !== null

    return cn(
        "grid",
        isCompact ? "gap-2" : "gap-3",
        isYesNoChoice ? "grid-cols-2" : "sm:grid-cols-2",
    )
}

function getFieldPlaceholder(field: { key: string; label: string; type: string }): string {
    const key = field.key.trim().toLowerCase()
    const label = field.label.trim().toLowerCase()
    const searchable = `${key} ${label}`

    if (field.type === "email" || searchable.includes("email")) {
        return "e.g. jane@example.com"
    }
    if (field.type === "phone" || searchable.includes("phone")) {
        return "e.g. (555) 123-4567"
    }
    if (field.type === "textarea") {
        if (/(note|comment|detail|describe|about)/.test(searchable)) {
            return "Share any relevant details"
        }
        return "Enter your response"
    }
    if (field.type === "number") {
        if (searchable.includes("weight")) return "e.g. 150 lb"
        if (searchable.includes("age")) return "e.g. 32"
        if (/(child|children|pregnanc|birth|cycle|attempt|count)/.test(searchable)) return "e.g. 2"
        return "e.g. 123"
    }
    if (/(full[_\s-]?name|legal[_\s-]?name)/.test(searchable)) return "e.g. Jane Smith"
    if (/(first[_\s-]?name|given[_\s-]?name)/.test(searchable)) return "e.g. Jane"
    if (/(last[_\s-]?name|family[_\s-]?name|surname)/.test(searchable)) return "e.g. Smith"
    if (searchable.includes("city")) return "e.g. Chicago"
    if (searchable.includes("state")) return "e.g. CA"
    if (/(zip|postal)/.test(searchable)) return "e.g. 60614"
    if (searchable.includes("address")) return "e.g. 123 Main St"

    return "Enter your answer"
}

function isStateCodeField(field: FormField): boolean {
    const key = field.key.trim().toLowerCase()
    const label = field.label.trim().toLowerCase()
    const validation = field.validation
    const pattern = validation?.pattern?.replace(/\s/g, "") ?? ""

    return (
        key === "state" ||
        key.endsWith("_state") ||
        (label === "state" &&
            validation?.max_length === 2 &&
            /A-Za-z/.test(pattern))
    )
}

function normalizePublicTextInput(field: FormField, value: string): string {
    if (isStateCodeField(field)) {
        return value.replace(/[^a-z]/gi, "").slice(0, 2).toUpperCase()
    }
    if (field.type === "number") {
        const numeric = value.replace(/[^\d.]/g, "")
        const decimalIndex = numeric.indexOf(".")
        if (decimalIndex === -1) return numeric
        return `${numeric.slice(0, decimalIndex + 1)}${numeric.slice(decimalIndex + 1).replace(/\./g, "")}`
    }
    return value
}

function getInputAttributes(field: FormField): React.InputHTMLAttributes<HTMLInputElement> {
    const validation = field.validation
    const attributes: React.InputHTMLAttributes<HTMLInputElement> = {}

    if (field.type === "email") {
        attributes.autoComplete = "email"
        attributes.inputMode = "email"
    }
    if (field.type === "phone") {
        attributes.autoComplete = "tel"
        attributes.inputMode = "tel"
    }
    if (field.type === "number") {
        attributes.inputMode = "numeric"
        if (validation?.min_value !== null && validation?.min_value !== undefined) {
            attributes.min = validation.min_value
        }
        if (validation?.max_value !== null && validation?.max_value !== undefined) {
            attributes.max = validation.max_value
        }
    }
    if (
        field.type === "text" ||
        field.type === "textarea" ||
        field.type === "email" ||
        field.type === "phone" ||
        field.type === "address"
    ) {
        if (validation?.max_length !== null && validation?.max_length !== undefined) {
            attributes.maxLength = validation.max_length
        }
        if (validation?.pattern) {
            attributes.pattern = validation.pattern
        }
    }
    if (isStateCodeField(field)) {
        attributes.autoCapitalize = "characters"
        attributes.inputMode = "text"
        attributes.maxLength = 2
        attributes.pattern = "^[A-Za-z]{2}$"
    }

    return attributes
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

type HeightDraftSelection = {
    serializedValue: string | null
    feet: string
    inches: string
}

function getHeightDraftSelection(value: PublicFormAnswerValue | undefined): HeightDraftSelection {
    const parsedSelection = parseHeightSelection(value)

    return {
        serializedValue: serializeHeightSelection(parsedSelection.feet, parsedSelection.inches),
        feet: parsedSelection.feet,
        inches: parsedSelection.inches,
    }
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
    const rows = normalizeFixedTableRows(field, value)

    const updateCell = (rowKey: string, columnKey: string, nextValue: string) => {
        const nextRows = rows.map((row) =>
            row.row_key === rowKey ? { ...row, [columnKey]: nextValue } : row,
        )
        updateField(field.key, nextRows)
    }

    if (columns.length === 0 || (field.rows?.length ?? 0) === 0) {
        return (
            <div key={field.key} className={publicFieldGroupShellClassName}>
                <Label className="text-sm font-medium">
                    {field.label} {requiredMark}
                </Label>
                <p className="text-sm text-stone-500">Configure rows and columns to use this table field.</p>
            </div>
        )
    }

    return (
        <div key={field.key} className={publicFieldGroupShellClassName}>
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
                            className="rounded-lg border border-stone-200 bg-white p-4 @container/table-row @xl/table-row:grid @xl/table-row:grid-cols-[minmax(0,10rem)_minmax(0,12rem)_minmax(0,1fr)] @xl/table-row:items-start @xl/table-row:gap-4"
                        >
                            <div className="mb-4 space-y-1 @xl/table-row:mb-0 @xl/table-row:pr-2">
                                <div className="text-base font-semibold text-stone-900">{rowLabel}</div>
                                {rowHelpText ? <p className="mt-1 text-xs text-stone-500">{rowHelpText}</p> : null}
                            </div>

                            {columns.map((column) => {
                                const cellValue = row[column.key]
                                const normalizedValue =
                                    cellValue === null || cellValue === undefined ? "" : String(cellValue)
                                const fieldInputId = `${field.key}-${rowKey}-${column.key}`
                                const fieldInputLabelId = `${fieldInputId}-label`
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
                                        <Label
                                            id={fieldInputLabelId}
                                            htmlFor={fieldInputId}
                                            className="text-[11px] font-semibold uppercase tracking-[0.16em] text-stone-500"
                                        >
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
                                                id={fieldInputId}
                                                aria-labelledby={fieldInputLabelId}
                                                className="h-11 w-full rounded-md border border-stone-200 bg-white px-3 text-sm shadow-none"
                                                value={normalizedValue}
                                                onChange={(event) => updateCell(rowKey, column.key, event.target.value)}
                                            >
                                                <option value="">Select&hellip;</option>
                                                {options.map((option) => (
                                                    <option key={option.value} value={option.value}>
                                                        {option.label}
                                                    </option>
                                                ))}
                                            </select>
                                        ) : column.type === "textarea" ? (
                                            <Input
                                                id={fieldInputId}
                                                type="text"
                                                value={normalizedValue}
                                                onChange={(event) => updateCell(rowKey, column.key, event.target.value)}
                                                placeholder={getFieldPlaceholder(column)}
                                                className={publicControlClassName}
                                            />
                                        ) : (
                                            <Input
                                                id={fieldInputId}
                                                type={
                                                    column.type === "number"
                                                        ? "number"
                                                        : column.type === "date"
                                                            ? "date"
                                                            : "text"
                                                }
                                                value={normalizedValue}
                                                onChange={(event) => updateCell(rowKey, column.key, event.target.value)}
                                                placeholder={getFieldPlaceholder(column)}
                                                className={publicControlClassName}
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
    const incomingSelection = getHeightDraftSelection(value)
    const [draftSelection, setDraftSelection] = React.useState<HeightDraftSelection>(() => incomingSelection)
    const currentSelection = draftSelection.serializedValue === incomingSelection.serializedValue
        ? draftSelection
        : incomingSelection
    const feetValue = currentSelection.feet
    const inchesValue = currentSelection.inches

    const syncHeight = (nextFeet: string, nextInches: string) => {
        const nextValue = serializeHeightSelection(nextFeet, nextInches)
        setDraftSelection({
            serializedValue: nextValue,
            feet: nextFeet,
            inches: nextInches,
        })
        updateField(field.key, nextValue)
    }

    return (
        <div key={field.key} className="space-y-3">
            <Label className="text-sm font-medium">
                {field.label} {requiredMark}
            </Label>
            <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                    <Label
                        htmlFor={`${field.key}_ft`}
                        className="text-xs font-medium uppercase tracking-[0.2em] text-stone-500"
                    >
                        Feet
                    </Label>
                    <select
                        id={`${field.key}_ft`}
                        aria-label={`${field.label} Feet`}
                        value={feetValue}
                        onChange={(event) => syncHeight(event.target.value, inchesValue)}
                        className="h-11 w-full rounded-md border border-stone-200 bg-white px-3 text-sm shadow-none"
                    >
                        <option value="">e.g. 5 ft</option>
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
                        Inches
                    </Label>
                    <select
                        id={`${field.key}_in`}
                        aria-label={`${field.label} Inches`}
                        value={inchesValue}
                        onChange={(event) => syncHeight(feetValue, event.target.value)}
                        className="h-11 w-full rounded-md border border-stone-200 bg-white px-3 text-sm shadow-none"
                    >
                        <option value="">e.g. 6 in</option>
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
                "min-h-11 w-full border border-stone-200 bg-white text-left transition-all",
                size === "compact" ? "min-h-10 rounded-md px-3 py-2" : "rounded-lg px-4 py-3",
                "hover:border-primary/25 hover:bg-stone-50",
                "focus:outline-none focus:ring-2 focus:ring-primary/20 focus:ring-offset-2",
                selected
                    ? "border-primary/45 bg-primary/[0.04] shadow-[0_0_0_1px_rgba(31,41,55,0.08)]"
                    : "border-stone-200",
            )}
        >
            <div className="flex items-center gap-3">
                <div
                    className={cn(
                        "flex items-center justify-center rounded-full border-2 transition-all",
                        size === "compact" ? "size-4" : "size-5",
                        selected ? "border-primary bg-primary" : "border-stone-300 bg-white",
                    )}
                >
                    {selected && <CheckIcon className={cn("text-white", size === "compact" ? "size-3" : "size-3.5")} />}
                </div>
                <div className="text-sm font-medium leading-5 text-stone-900">
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
    density = "default",
}: PublicFormFieldRendererProps) {
    const requiredMark = field.required ? <span className="text-red-500">*</span> : null
    const densityStyles = getPublicFieldDensityStyles(density)

    if (field.type === "textarea") {
        return (
            <div key={field.key} className={densityStyles.fieldShellClassName}>
                <Label htmlFor={field.key} className={densityStyles.labelClassName}>
                    {field.label} {requiredMark}
                </Label>
                <Textarea
                    id={field.key}
                    value={typeof value === "string" ? value : ""}
                    onChange={(event) => updateField(field.key, event.target.value)}
                    placeholder={getFieldPlaceholder(field)}
                    className={cn(
                        "min-h-24 rounded-md border-stone-200 bg-white shadow-none",
                        densityStyles.isCompact && "min-h-20 text-[15px]",
                    )}
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
            <div key={field.key} className={densityStyles.fieldShellClassName}>
                <Label className={densityStyles.labelClassName}>
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
                                    densityStyles.controlClassName,
                                    "w-full justify-start text-left font-normal",
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
        const orderedOptions = getChoiceOptions(options)
        const gridClassName = getChoiceGridClassName(options, density)
        const legendId = `${field.key}-legend`

        return (
            <fieldset key={field.key} className={densityStyles.fieldShellClassName}>
                <legend id={legendId} className={densityStyles.labelClassName}>
                    {field.label} {requiredMark}
                </legend>
                {options.length === 0 ? (
                    <p className="text-sm text-stone-500">No options configured.</p>
                ) : (
                    <div
                        role="radiogroup"
                        aria-labelledby={legendId}
                        className={gridClassName}
                    >
                        {orderedOptions.map((option) => (
                            <OptionCard
                                key={option.value}
                                selected={value === option.value}
                                onClick={() => updateField(field.key, option.value)}
                                label={option.label}
                                size={densityStyles.optionSize}
                            />
                        ))}
                    </div>
                )}
                {field.help_text && <p className="text-xs text-stone-500">{field.help_text}</p>}
            </fieldset>
        )
    }

    if (field.type === "multiselect") {
        const options = field.options || []
        const gridClassName = getChoiceGridClassName(options, density)
        const legendId = `${field.key}-legend`
        const selectedValues = Array.isArray(value)
            ? value.filter((item): item is string => typeof item === "string")
            : []
        const selectedValueSet = new Set(selectedValues)

        return (
            <fieldset key={field.key} className={densityStyles.fieldShellClassName}>
                <legend id={legendId} className={densityStyles.labelClassName}>
                    {field.label} {requiredMark}
                </legend>
                {options.length === 0 ? (
                    <p className="text-sm text-stone-500">No options configured.</p>
                ) : (
                    <div aria-labelledby={legendId} className={gridClassName}>
                        {options.map((option) => {
                            const selected = selectedValueSet.has(option.value)
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
                                    size={densityStyles.optionSize}
                                />
                            )
                        })}
                    </div>
                )}
                {field.help_text && <p className="text-xs text-stone-500">{field.help_text}</p>}
            </fieldset>
        )
    }

    if (field.type === "checkbox") {
        return (
            <div key={field.key} className={densityStyles.fieldGroupClassName}>
                <div className="flex items-start gap-3">
                    <Checkbox
                        id={field.key}
                        checked={value === true}
                        onCheckedChange={(next) => updateField(field.key, next === true)}
                        className="mt-0.5"
                    />
                    <div className="space-y-1">
                        <Label htmlFor={field.key} className={cn(densityStyles.labelClassName, "leading-relaxed")}>
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
        <div key={field.key} className={densityStyles.fieldShellClassName}>
            <Label htmlFor={field.key} className={densityStyles.labelClassName}>
                {field.label} {requiredMark}
            </Label>
            <Input
                id={field.key}
                type={inputType}
                {...getInputAttributes(field)}
                value={typeof value === "string" ? value : value ? String(value) : ""}
                onChange={(event) =>
                    updateField(field.key, normalizePublicTextInput(field, event.target.value))
                }
                placeholder={getFieldPlaceholder(field)}
                className={densityStyles.controlClassName}
            />
            {field.help_text && <p className="text-xs text-stone-500">{field.help_text}</p>}
        </div>
    )
}
