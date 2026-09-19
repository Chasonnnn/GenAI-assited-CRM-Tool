"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { CheckIcon, EyeIcon, PencilIcon, XIcon } from "lucide-react"
import { formatHeight } from "@/components/surrogates/detail/surrogate-detail-utils"
import { serializeHeightSelection, splitHeightFt } from "@/lib/height"
import { formatRace } from "@/lib/formatters"
import { useRecordEditing } from "@/components/records/RecordEditingContext"

const RACE_OPTIONS = [
    "american_indian_or_alaska_native",
    "asian",
    "black_or_african_american",
    "hispanic_or_latino",
    "native_hawaiian_or_other_pacific_islander",
    "white",
    "other_please_specify",
] as const

const RACE_OPTION_ALIASES: Record<string, (typeof RACE_OPTIONS)[number]> = {
    american_indian_alaska_native: "american_indian_or_alaska_native",
    black_african_american: "black_or_african_american",
    native_hawaiian_or_pacific_islander: "native_hawaiian_or_other_pacific_islander",
    native_hawaiian_or_other_pacific_islanders: "native_hawaiian_or_other_pacific_islander",
    other: "other_please_specify",
    other_please_specified: "other_please_specify",
}

function normalizeRaceOptionKey(value: string | null | undefined): string {
    const normalized = value?.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") ?? ""
    if (!normalized) return ""
    const aliased = RACE_OPTION_ALIASES[normalized] ?? normalized
    return RACE_OPTIONS.includes(aliased as (typeof RACE_OPTIONS)[number]) ? aliased : ""
}

type SelectOption = {
    value: string
    label: string
}

function formatSelectValue(
    value: string | null | undefined,
    options: readonly SelectOption[],
    placeholder: string
) {
    if (!value) return placeholder
    return options.find((option) => option.value === value)?.label ?? value
}

export function PersonalInfoRow({
    label,
    children,
}: {
    label: string
    children: React.ReactNode
}) {
    return (
        <div className="grid gap-1 sm:grid-cols-[8.25rem_minmax(0,1fr)] sm:items-center">
            <span className="text-sm text-muted-foreground">{label}:</span>
            <div className="min-w-0 text-sm">{children}</div>
        </div>
    )
}

export function InlineSelectField({
    value,
    options,
    onSave,
    label,
    placeholder = "Not provided",
    saveOnSelect = true,
    triggerClassName = "w-48",
}: {
    value: string | null | undefined
    options: readonly SelectOption[]
    onSave: (value: string | null) => Promise<void>
    label: string
    placeholder?: string
    saveOnSelect?: boolean
    triggerClassName?: string
}) {
    const canEdit = useRecordEditing()
    const [isEditing, setIsEditing] = React.useState(false)
    const [editValue, setEditValue] = React.useState(value ?? "")
    const [isSaving, setIsSaving] = React.useState(false)
    const [error, setError] = React.useState<string | null>(null)

    const displayValue = formatSelectValue(value, options, placeholder)
    const isPlaceholder = !value

    const handleStartEdit = () => {
        setEditValue(value ?? "")
        setError(null)
        setIsEditing(true)
    }

    const handleCancel = () => {
        setEditValue(value ?? "")
        setError(null)
        setIsEditing(false)
    }

    const handleSave = async (nextValue = editValue) => {
        const normalizedValue = nextValue || null
        if ((value ?? "") === (nextValue ?? "")) {
            setIsEditing(false)
            return
        }

        setIsSaving(true)
        const finishSaving = () => setIsSaving(false)
        try {
            await onSave(normalizedValue)
            setIsEditing(false)
            setError(null)
            finishSaving()
        } catch (err) {
            setError(err instanceof Error ? err.message : `Failed to save ${label}`)
            finishSaving()
        }
    }

    if (!isEditing) {
        return (
            <Button unstyled
                type="button"
                className="group -mx-1 flex w-fit cursor-pointer items-center gap-1 rounded px-1 transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                disabled={!canEdit}
                onClick={handleStartEdit}
                aria-label={`Edit ${label}`}
            >
                <span className={isPlaceholder ? "text-muted-foreground" : undefined}>
                    {displayValue}
                </span>
                <PencilIcon
                    className="size-3 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
                    aria-hidden="true"
                />
            </Button>
        )
    }

    return (
        <div className="space-y-1">
            <div className="flex max-w-full flex-wrap items-center gap-1">
                <Select
                    value={editValue}
                    onValueChange={(nextValue) => {
                        const normalizedValue = nextValue ?? ""
                        setEditValue(normalizedValue)
                        if (saveOnSelect) {
                            void handleSave(normalizedValue)
                        }
                    }}
                    disabled={isSaving}
                >
                    <SelectTrigger
                        aria-label={label}
                        size="sm"
                        className={triggerClassName}
                    >
                        <SelectValue>
                            {(selectedValue: string | null) =>
                                formatSelectValue(selectedValue, options, placeholder)
                            }
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent className={triggerClassName}>
                        <SelectGroup>
                            <SelectItem value="">{placeholder}</SelectItem>
                            {options.map((option) => (
                                <SelectItem key={option.value} value={option.value}>
                                    {option.label}
                                </SelectItem>
                            ))}
                        </SelectGroup>
                    </SelectContent>
                </Select>
                {!saveOnSelect && (
                    <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="size-6"
                        onClick={() => void handleSave()}
                        disabled={isSaving}
                        aria-label={`Save ${label}`}
                    >
                        <CheckIcon className="size-3 text-green-600" aria-hidden="true" />
                    </Button>
                )}
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-6"
                    onClick={handleCancel}
                    disabled={isSaving}
                    aria-label={`Cancel ${label}`}
                >
                    <XIcon className="size-3 text-destructive" aria-hidden="true" />
                </Button>
            </div>
            {error && <p className="text-xs text-destructive">{error}</p>}
        </div>
    )
}

export function ProfileMetric({
    icon: Icon,
    label,
    primary,
    secondary,
    warning,
    badge,
}: {
    icon: React.ComponentType<{ className?: string }>
    label: string
    primary: React.ReactNode
    secondary?: React.ReactNode
    warning?: React.ReactNode
    badge?: React.ReactNode
}) {
    return (
        <div className="grid h-full grid-cols-[2.25rem_minmax(0,1fr)] gap-3 rounded-lg p-2">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-rose-100/65 text-rose-900 dark:bg-rose-950/40 dark:text-rose-100">
                <Icon className="size-4" />
            </div>
            <div className="min-w-0 space-y-0.5">
                <div className="flex items-center gap-1.5">
                    <span className="text-sm text-muted-foreground">{label}:</span>
                    {warning}
                </div>
                <div className="min-w-0 text-sm text-foreground">{primary}</div>
                {secondary && <div className="text-xs text-muted-foreground">{secondary}</div>}
                {badge}
            </div>
        </div>
    )
}

export function InlineHeightField({
    value,
    onSave,
}: {
    value: number | string | null | undefined
    onSave: (value: number | null) => Promise<void>
}) {
    const canEdit = useRecordEditing()
    const [isEditing, setIsEditing] = React.useState(false)
    const [feet, setFeet] = React.useState("")
    const [inches, setInches] = React.useState("")
    const [isSaving, setIsSaving] = React.useState(false)
    const [error, setError] = React.useState<string | null>(null)

    const displayValue = value != null ? formatHeight(value) : "-"

    const handleStartEdit = () => {
        const selection = splitHeightFt(value)
        setFeet(selection.feet)
        setInches(selection.inches)
        setError(null)
        setIsEditing(true)
    }

    const handleCancel = () => {
        const selection = splitHeightFt(value)
        setFeet(selection.feet)
        setInches(selection.inches)
        setError(null)
        setIsEditing(false)
    }

    const handleSave = async () => {
        const nextValue = serializeHeightSelection(feet, inches)
        if ((feet !== "" || inches !== "") && nextValue === null) {
            setError("Invalid height")
            return
        }

        setIsSaving(true)
        const finishSaving = () => setIsSaving(false)
        try {
            await onSave(nextValue)
            setIsEditing(false)
            setError(null)
            finishSaving()
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to save")
            finishSaving()
        }
    }

    if (!isEditing) {
        return (
            <Button unstyled
                type="button"
                className="group -mx-1 flex cursor-pointer items-center gap-1 rounded px-1 transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                disabled={!canEdit}
                onClick={handleStartEdit}
                aria-label="Edit Height"
            >
                <span className={value == null ? "text-muted-foreground" : undefined}>
                    {displayValue}
                </span>
                <PencilIcon
                    className="size-3 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
                    aria-hidden="true"
                />
            </Button>
        )
    }

    return (
        <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-1">
                <Select value={feet} onValueChange={(value) => setFeet(value ?? "")} disabled={isSaving}>
                    <SelectTrigger aria-label="Height feet" size="sm" className="w-20">
                        <SelectValue>
                            {(value: string | null) => (value ? `${value} ft` : "ft")}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent className="w-24">
                        <SelectGroup>
                            <SelectItem value="">ft</SelectItem>
                            {Array.from({ length: 9 }, (_, option) => option).map((option) => (
                                <SelectItem key={`inline-height-feet-${option}`} value={String(option)}>
                                    {option} ft
                                </SelectItem>
                            ))}
                        </SelectGroup>
                    </SelectContent>
                </Select>
                <Select value={inches} onValueChange={(value) => setInches(value ?? "")} disabled={isSaving}>
                    <SelectTrigger aria-label="Height inches" size="sm" className="w-20">
                        <SelectValue>
                            {(value: string | null) => (value ? `${value} in` : "in")}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent className="w-24">
                        <SelectGroup>
                            <SelectItem value="">in</SelectItem>
                            {Array.from({ length: 12 }, (_, option) => option).map((option) => (
                                <SelectItem key={`inline-height-inches-${option}`} value={String(option)}>
                                    {option} in
                                </SelectItem>
                            ))}
                        </SelectGroup>
                    </SelectContent>
                </Select>
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-6"
                    onClick={handleSave}
                    disabled={isSaving}
                    aria-label="Save Height"
                >
                    <CheckIcon className="size-3 text-green-600" aria-hidden="true" />
                </Button>
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-6"
                    onClick={handleCancel}
                    disabled={isSaving}
                    aria-label="Cancel Height"
                >
                    <XIcon className="size-3 text-destructive" aria-hidden="true" />
                </Button>
            </div>
            {error && <p className="text-xs text-destructive">{error}</p>}
        </div>
    )
}

export function InlineRaceField({
    value,
    onSave,
}: {
    value: string | null | undefined
    onSave: (value: string | null) => Promise<void>
}) {
    const canEdit = useRecordEditing()
    const [isEditing, setIsEditing] = React.useState(false)
    const [editValue, setEditValue] = React.useState(() => normalizeRaceOptionKey(value))
    const [isSaving, setIsSaving] = React.useState(false)
    const [error, setError] = React.useState<string | null>(null)

    const displayValue = formatRace(value)
    const fieldLabel = "Race / Ethnicity"

    const handleStartEdit = () => {
        setEditValue(normalizeRaceOptionKey(value))
        setError(null)
        setIsEditing(true)
    }

    const handleCancel = () => {
        setEditValue(normalizeRaceOptionKey(value))
        setError(null)
        setIsEditing(false)
    }

    const handleSave = async () => {
        const currentValue = normalizeRaceOptionKey(value)
        if (editValue === currentValue) {
            setIsEditing(false)
            return
        }

        setIsSaving(true)
        const finishSaving = () => setIsSaving(false)
        try {
            await onSave(editValue || null)
            setIsEditing(false)
            setError(null)
            finishSaving()
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to save")
            finishSaving()
        }
    }

    if (!isEditing) {
        return (
            <Button unstyled
                type="button"
                className="group -mx-1 flex w-fit cursor-pointer items-center gap-1 rounded px-1 transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                disabled={!canEdit}
                onClick={handleStartEdit}
                aria-label={`Edit ${fieldLabel}`}
            >
                <span className={displayValue ? undefined : "text-muted-foreground"}>
                    {displayValue || "-"}
                </span>
                <PencilIcon
                    className="size-3 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
                    aria-hidden="true"
                />
            </Button>
        )
    }

    return (
        <div className="space-y-1">
            <div className="flex max-w-full flex-wrap items-center gap-1">
                <Select
                    value={editValue}
                    onValueChange={(value) => setEditValue(value ?? "")}
                    disabled={isSaving}
                >
                    <SelectTrigger
                        aria-label={fieldLabel}
                        size="sm"
                        className="w-64 max-w-full"
                    >
                        <SelectValue>
                            {(value: string | null) => (value ? formatRace(value) : "No race selected")}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent className="w-64 max-w-full">
                        <SelectGroup>
                            <SelectItem value="">No race selected</SelectItem>
                            {RACE_OPTIONS.map((raceKey) => (
                                <SelectItem key={raceKey} value={raceKey}>
                                    {formatRace(raceKey)}
                                </SelectItem>
                            ))}
                        </SelectGroup>
                    </SelectContent>
                </Select>
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-6"
                    onClick={handleSave}
                    disabled={isSaving}
                    aria-label={`Save ${fieldLabel}`}
                >
                    <CheckIcon className="size-3 text-green-600" aria-hidden="true" />
                </Button>
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-6"
                    onClick={handleCancel}
                    disabled={isSaving}
                    aria-label={`Cancel ${fieldLabel}`}
                >
                    <XIcon className="size-3 text-destructive" aria-hidden="true" />
                </Button>
            </div>
            {error && <p className="text-xs text-destructive">{error}</p>}
        </div>
    )
}

export function InlineWeightField({
    value,
    onSave,
}: {
    value: number | null | undefined
    onSave: (value: number | null) => Promise<void>
}) {
    const canEdit = useRecordEditing()
    const [isEditing, setIsEditing] = React.useState(false)
    const [editValue, setEditValue] = React.useState("")
    const [isSaving, setIsSaving] = React.useState(false)
    const [error, setError] = React.useState<string | null>(null)

    const handleStartEdit = () => {
        setEditValue("")
        setError(null)
        setIsEditing(true)
    }

    const handleCancel = () => {
        setEditValue("")
        setError(null)
        setIsEditing(false)
    }

    const handleSave = async () => {
        const trimmed = editValue.trim()
        if (!trimmed) {
            setIsEditing(false)
            setError(null)
            return
        }
        const parsed = trimmed ? Number(trimmed) : null
        if (parsed !== null && (!Number.isFinite(parsed) || parsed < 0)) {
            setError("Enter a valid weight")
            return
        }
        if (parsed === value) {
            setIsEditing(false)
            setError(null)
            return
        }

        setIsSaving(true)
        const finishSaving = () => setIsSaving(false)
        try {
            await onSave(parsed)
            setIsEditing(false)
            setError(null)
            finishSaving()
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to save")
            finishSaving()
        }
    }

    if (!isEditing) {
        return (
            <Button unstyled
                type="button"
                className="group -mx-1 flex w-fit cursor-pointer items-center gap-1 rounded px-1 transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                disabled={!canEdit}
                onClick={handleStartEdit}
                aria-label="Edit Weight"
            >
                <span className={value == null ? "text-muted-foreground" : undefined}>
                    {value != null ? `${value} lb` : "-"}
                </span>
                <PencilIcon
                    className="size-3 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
                    aria-hidden="true"
                />
            </Button>
        )
    }

    return (
        <div className="space-y-1">
            <div className="flex items-center gap-1">
                <Input
                    type="number"
                    min="0"
                    value={editValue}
                    onChange={(event) => setEditValue(event.target.value)}
                    onKeyDown={(event) => {
                        if (event.key === "Enter") {
                            event.preventDefault()
                            void handleSave()
                        } else if (event.key === "Escape") {
                            handleCancel()
                        }
                    }}
                    className="h-7 w-24 text-sm"
                    disabled={isSaving}
                    aria-label="Weight"
                    placeholder={value != null ? String(value) : undefined}
                />
                <span className="text-sm text-muted-foreground">lb</span>
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-6"
                    onClick={handleSave}
                    disabled={isSaving}
                    aria-label="Save Weight"
                >
                    <CheckIcon className="size-3 text-green-600" aria-hidden="true" />
                </Button>
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-6"
                    onClick={handleCancel}
                    disabled={isSaving}
                    aria-label="Cancel Weight"
                >
                    <XIcon className="size-3 text-destructive" aria-hidden="true" />
                </Button>
            </div>
            {error && <p className="text-xs text-destructive">{error}</p>}
        </div>
    )
}

export function PersonalInfoColumn({
    title,
    icon: Icon,
    children,
}: {
    title: string
    icon: React.ComponentType<{ className?: string }>
    children: React.ReactNode
}) {
    return (
        <section className="flex h-full min-w-0 flex-col rounded-lg border border-border/70 bg-card p-4 shadow-sm">
            <h3 className="flex items-center gap-2 text-sm font-medium text-foreground">
                <Icon className="size-4 text-muted-foreground" />
                {title}
            </h3>
            <div className="mt-4 space-y-3">{children}</div>
        </section>
    )
}

export function SectionActionIcon({
    icon,
    tone = "default",
}: {
    icon: React.ReactNode
    tone?: "default" | "destructive"
}) {
    return (
        <span
            className={
                tone === "destructive"
                    ? "flex size-7 items-center justify-center rounded-full bg-destructive/10 text-destructive"
                    : "flex size-7 items-center justify-center rounded-full bg-muted text-muted-foreground"
            }
        >
            {icon}
        </span>
    )
}

export function getAgeLabel(dateOfBirth: string | null | undefined) {
    if (!dateOfBirth) return null
    const parsed = new Date(`${dateOfBirth}T00:00:00`)
    if (Number.isNaN(parsed.getTime())) return null
    const today = new Date()
    let age = today.getFullYear() - parsed.getFullYear()
    const monthDelta = today.getMonth() - parsed.getMonth()
    if (monthDelta < 0 || (monthDelta === 0 && today.getDate() < parsed.getDate())) {
        age -= 1
    }
    return `Age ${age}`
}

export function SsnField({
    label,
    maskedValue,
    revealedValue,
    onReveal,
    onSave,
    isRevealPending,
}: {
    label: string
    maskedValue: string | null | undefined
    revealedValue: string | null
    onReveal: () => Promise<void>
    onSave: (value: string | null) => Promise<void>
    isRevealPending: boolean
}) {
    const canEdit = useRecordEditing()
    const [isEditing, setIsEditing] = React.useState(false)
    const [editValue, setEditValue] = React.useState("")
    const [isSaving, setIsSaving] = React.useState(false)
    const [error, setError] = React.useState<string | null>(null)
    const displayValue = revealedValue || maskedValue || "-"

    const save = async () => {
        setIsSaving(true)
        const finishSaving = () => setIsSaving(false)
        try {
            await onSave(editValue.trim() || null)
            setEditValue("")
            setError(null)
            setIsEditing(false)
            finishSaving()
        } catch (err) {
            setError(err instanceof Error ? err.message : `Failed to save ${label}`)
            finishSaving()
        }
    }

    if (isEditing) {
        return (
            <div className="space-y-1">
                <div className="flex min-w-0 items-center gap-2">
                    <Input
                        aria-label={label}
                        value={editValue}
                        onChange={(event) => setEditValue(event.target.value)}
                        onKeyDown={(event) => {
                            if (event.key === "Enter") {
                                event.preventDefault()
                                void save()
                            }
                            if (event.key === "Escape") {
                                setEditValue("")
                                setError(null)
                                setIsEditing(false)
                            }
                        }}
                        placeholder="XXX-XX-XXXX"
                        className="h-7 min-w-0 rounded-md border border-input bg-background px-2 text-sm"
                    />
                    <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="size-7"
                        onClick={() => void save()}
                        disabled={isSaving}
                        aria-label={`Save ${label}`}
                    >
                        <CheckIcon className="size-3.5" aria-hidden="true" />
                    </Button>
                    <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="size-7"
                        onClick={() => {
                            setEditValue("")
                            setError(null)
                            setIsEditing(false)
                        }}
                        disabled={isSaving}
                        aria-label={`Cancel editing ${label}`}
                    >
                        <XIcon className="size-3.5" aria-hidden="true" />
                    </Button>
                </div>
                {error && <p className="text-xs text-destructive">{error}</p>}
            </div>
        )
    }

    return (
        <div className="flex min-w-0 items-center gap-1.5">
            <span className="shrink-0 whitespace-nowrap font-mono text-[13px] tabular-nums">
                {displayValue}
            </span>
            {maskedValue && !revealedValue && (
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-7"
                    onClick={() => void onReveal()}
                    disabled={isRevealPending}
                    aria-label={`Reveal ${label}`}
                >
                    <EyeIcon className="size-3.5" aria-hidden="true" />
                </Button>
            )}
            <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-7"
                onClick={() => {
                    setError(null)
                    setIsEditing(true)
                }}
                disabled={!canEdit}
                aria-label={`Edit ${label}`}
            >
                <PencilIcon className="size-3.5" aria-hidden="true" />
            </Button>
        </div>
    )
}
