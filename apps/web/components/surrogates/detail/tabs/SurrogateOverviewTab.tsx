"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select"
import { Input } from "@/components/ui/input"
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuGroup,
    DropdownMenuItem,
    DropdownMenuSub,
    DropdownMenuSubContent,
    DropdownMenuSubTrigger,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { TabsContent } from "@/components/ui/tabs"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { InlineEditField } from "@/components/inline-edit-field"
import { InlineDateField } from "@/components/inline-date-field"
import { CombinedMedicalInsuranceCard } from "@/components/surrogates/CombinedMedicalInsuranceCard"
import { ActivityTimeline } from "@/components/surrogates/ActivityTimeline"
import { PregnancyTrackerCard } from "@/components/surrogates/PregnancyTrackerCard"
import { SurrogateOverviewCard } from "@/components/surrogates/SurrogateOverviewCard"
import { useDefaultPipeline } from "@/lib/hooks/use-pipelines"
import { useRevealSurrogateSensitiveInfo, useSurrogateActivity, useUpdateSurrogate } from "@/lib/hooks/use-surrogates"
import { useTasks } from "@/lib/hooks/use-tasks"
import {
    AlertTriangleIcon,
    CalendarDaysIcon,
    ChevronDownIcon,
    ClipboardCheckIcon,
    CopyIcon,
    EyeIcon,
    InfoIcon,
    CheckIcon,
    PencilIcon,
    PlusIcon,
    RulerIcon,
    ScaleIcon,
    Trash2Icon,
    UserIcon,
    UsersIcon,
    WeightIcon,
    XIcon,
} from "lucide-react"
import { computeBmi, formatDate, formatHeight } from "@/components/surrogates/detail/surrogate-detail-utils"
import { useSurrogateDetailContext } from "@/components/surrogates/detail/SurrogateDetailContext"
import { serializeHeightSelection, splitHeightFt } from "@/lib/height"
import { getMaritalStatusOptions } from "@/lib/intended-parent-marital-status"
import { getSurrogateStageContext, stageHasCapability } from "@/lib/surrogate-stage-context"
import type { SurrogateLeadIntakeWarning } from "@/lib/types/surrogate"
import type { SurrogateUpdatePayload } from "@/lib/api/surrogates"

const LEAD_WARNING_FIELD_LABELS = {
    email: "Email",
    phone: "Phone",
    state: "State",
    height_ft: "Height",
    weight_lb: "Weight",
} as const

const LEAD_WARNING_REASON_LABELS = {
    invalid_value: "Invalid structured value",
    missing_value: "Missing structured value",
} as const

const LEAD_WARNING_REASON_COPY = {
    invalid_value: "This value could not be structured, so the field needs review.",
    missing_value: "This value could not be structured, so the field needs review.",
} as const

const CHECKLIST_BOOLEAN_FIELD_KEYS = [
    "is_age_eligible",
    "is_citizen_or_pr",
    "has_child",
    "is_non_smoker",
    "has_surrogate_experience",
] as const

const JOURNEY_TIMING_OPTIONS = [
    { label: "0–3 months", value: "months_0_3" },
    { label: "3–6 months", value: "months_3_6" },
    { label: "Still deciding", value: "still_deciding" },
] as const

type ChecklistBooleanFieldKey = (typeof CHECKLIST_BOOLEAN_FIELD_KEYS)[number]

function isChecklistBooleanFieldKey(key: string): key is ChecklistBooleanFieldKey {
    return (CHECKLIST_BOOLEAN_FIELD_KEYS as readonly string[]).includes(key)
}

function getNextChecklistValue(value: boolean | null | undefined) {
    if (value === null || value === undefined) return true
    if (value === true) return false
    return null
}

function LeadWarningIndicator({
    warning,
    fieldLabel,
}: {
    warning: SurrogateLeadIntakeWarning
    fieldLabel: string
}) {
    return (
        <Tooltip>
            <TooltipTrigger
                type="button"
                aria-label={`${fieldLabel} lead intake warning`}
                className="inline-flex size-5 shrink-0 items-center justify-center rounded-full border border-red-300/80 bg-[radial-gradient(circle_at_28%_28%,rgba(255,255,255,0.96),rgba(255,255,255,0.42)_34%,rgba(252,165,165,0.3)_38%,rgba(248,113,113,0.26)_62%,rgba(220,38,38,0.18)_100%)] text-red-600 shadow-[0_6px_16px_-10px_rgba(220,38,38,0.95),inset_0_1px_0_rgba(255,255,255,0.95)] transition-transform duration-150 hover:-translate-y-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-300/70 focus-visible:ring-offset-2 dark:border-red-400/90 dark:bg-[radial-gradient(circle_at_30%_30%,rgba(255,255,255,0.3),rgba(255,255,255,0.08)_18%,rgba(248,113,113,0.72)_42%,rgba(220,38,38,0.86)_70%,rgba(69,10,10,0.98)_100%)] dark:text-red-50 dark:shadow-[0_10px_24px_-14px_rgba(248,113,113,0.98),inset_0_1px_0_rgba(255,255,255,0.18)] dark:focus-visible:ring-red-400/70"
            >
                <AlertTriangleIcon
                    className="size-3.5 drop-shadow-[0_0_1px_rgba(255,255,255,0.16)] dark:drop-shadow-[0_0_2px_rgba(255,255,255,0.52)]"
                    aria-hidden="true"
                />
            </TooltipTrigger>
            <TooltipContent
                className="max-w-64 border border-slate-200/80 bg-white px-3 py-2 text-slate-950 shadow-xl shadow-slate-950/12 dark:border-white/10 dark:bg-zinc-950 dark:text-zinc-50 dark:shadow-black/40"
                arrowClassName="bg-white fill-white dark:bg-zinc-950 dark:fill-zinc-950"
            >
                <div className="space-y-1.5">
                    <div className="text-sm font-medium">{fieldLabel}</div>
                    <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500 dark:text-zinc-400">
                        {LEAD_WARNING_REASON_LABELS[warning.issue]}
                    </div>
                    <p className="text-xs leading-relaxed text-slate-700 dark:text-zinc-200">
                        {LEAD_WARNING_REASON_COPY[warning.issue]}
                    </p>
                    <div className="border-t border-slate-200/80 pt-1.5 dark:border-white/10">
                        <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500 dark:text-zinc-400">
                            Raw lead value
                        </div>
                        <div className="mt-1 break-words text-xs font-medium">
                            {warning.raw_value}
                        </div>
                    </div>
                </div>
            </TooltipContent>
        </Tooltip>
    )
}

function PersonalInfoRow({
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

function ProfileMetric({
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

function InlineHeightField({
    value,
    onSave,
}: {
    value: number | string | null | undefined
    onSave: (value: number | null) => Promise<void>
}) {
    const [isEditing, setIsEditing] = React.useState(false)
    const [feet, setFeet] = React.useState("")
    const [inches, setInches] = React.useState("")
    const [isSaving, setIsSaving] = React.useState(false)
    const [error, setError] = React.useState<string | null>(null)

    React.useEffect(() => {
        const selection = splitHeightFt(value)
        setFeet(selection.feet)
        setInches(selection.inches)
    }, [value])

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
        try {
            await onSave(nextValue)
            setIsEditing(false)
            setError(null)
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to save")
        } finally {
            setIsSaving(false)
        }
    }

    if (!isEditing) {
        return (
            <div
                className="group -mx-1 flex cursor-pointer items-center gap-1 rounded px-1 transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                onClick={handleStartEdit}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " " || event.key === "Spacebar") {
                        event.preventDefault()
                        handleStartEdit()
                    }
                }}
                aria-label="Edit Height"
            >
                <span className={value == null ? "text-muted-foreground" : undefined}>
                    {displayValue}
                </span>
                <PencilIcon
                    className="size-3 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
                    aria-hidden="true"
                />
            </div>
        )
    }

    return (
        <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-1">
                <NativeSelect
                    value={feet}
                    onChange={(event) => setFeet(event.target.value)}
                    size="sm"
                    className="w-20"
                    aria-label="Height feet"
                    disabled={isSaving}
                >
                    <NativeSelectOption value="">ft</NativeSelectOption>
                    {Array.from({ length: 9 }, (_, option) => option).map((option) => (
                        <NativeSelectOption key={`inline-height-feet-${option}`} value={String(option)}>
                            {option} ft
                        </NativeSelectOption>
                    ))}
                </NativeSelect>
                <NativeSelect
                    value={inches}
                    onChange={(event) => setInches(event.target.value)}
                    size="sm"
                    className="w-20"
                    aria-label="Height inches"
                    disabled={isSaving}
                >
                    <NativeSelectOption value="">in</NativeSelectOption>
                    {Array.from({ length: 12 }, (_, option) => option).map((option) => (
                        <NativeSelectOption key={`inline-height-inches-${option}`} value={String(option)}>
                            {option} in
                        </NativeSelectOption>
                    ))}
                </NativeSelect>
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={handleSave}
                    disabled={isSaving}
                    aria-label="Save Height"
                >
                    <CheckIcon className="size-3 text-green-600" />
                </Button>
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={handleCancel}
                    disabled={isSaving}
                    aria-label="Cancel Height"
                >
                    <XIcon className="size-3 text-destructive" />
                </Button>
            </div>
            {error && <p className="text-xs text-destructive">{error}</p>}
        </div>
    )
}

function InlineWeightField({
    value,
    onSave,
}: {
    value: number | null | undefined
    onSave: (value: number | null) => Promise<void>
}) {
    const [isEditing, setIsEditing] = React.useState(false)
    const [editValue, setEditValue] = React.useState(value != null ? String(value) : "")
    const [isSaving, setIsSaving] = React.useState(false)
    const [error, setError] = React.useState<string | null>(null)

    React.useEffect(() => {
        setEditValue(value != null ? String(value) : "")
    }, [value])

    const handleStartEdit = () => {
        setEditValue(value != null ? String(value) : "")
        setError(null)
        setIsEditing(true)
    }

    const handleCancel = () => {
        setEditValue(value != null ? String(value) : "")
        setError(null)
        setIsEditing(false)
    }

    const handleSave = async () => {
        const trimmed = editValue.trim()
        const parsed = trimmed ? Number(trimmed) : null
        if (parsed !== null && (!Number.isFinite(parsed) || parsed < 0)) {
            setError("Enter a valid weight")
            return
        }

        setIsSaving(true)
        try {
            await onSave(parsed)
            setIsEditing(false)
            setError(null)
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to save")
        } finally {
            setIsSaving(false)
        }
    }

    if (!isEditing) {
        return (
            <div
                className="group -mx-1 flex w-fit cursor-pointer items-center gap-1 rounded px-1 transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                onClick={handleStartEdit}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " " || event.key === "Spacebar") {
                        event.preventDefault()
                        handleStartEdit()
                    }
                }}
                aria-label="Edit Weight"
            >
                <span className={value == null ? "text-muted-foreground" : undefined}>
                    {value != null ? `${value} lb` : "-"}
                </span>
                <PencilIcon
                    className="size-3 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
                    aria-hidden="true"
                />
            </div>
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
                            handleSave()
                        } else if (event.key === "Escape") {
                            handleCancel()
                        }
                    }}
                    className="h-7 w-24 text-sm"
                    disabled={isSaving}
                    aria-label="Weight"
                />
                <span className="text-sm text-muted-foreground">lb</span>
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={handleSave}
                    disabled={isSaving}
                    aria-label="Save Weight"
                >
                    <CheckIcon className="size-3 text-green-600" />
                </Button>
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={handleCancel}
                    disabled={isSaving}
                    aria-label="Cancel Weight"
                >
                    <XIcon className="size-3 text-destructive" />
                </Button>
            </div>
            {error && <p className="text-xs text-destructive">{error}</p>}
        </div>
    )
}

function PersonalInfoColumn({
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

function ChecklistStatusButton({
    label,
    value,
    onChange,
}: {
    label: string
    value: boolean | null | undefined
    onChange: (value: boolean | null) => Promise<void>
}) {
    const [isSaving, setIsSaving] = React.useState(false)
    const nextValue = getNextChecklistValue(value)
    const statusLabel = value === true ? "Yes" : value === false ? "No" : "Not set"

    const handleClick = async () => {
        setIsSaving(true)
        try {
            await onChange(nextValue)
        } finally {
            setIsSaving(false)
        }
    }

    return (
        <button
            type="button"
            className="flex size-6 shrink-0 items-center justify-center rounded-full transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-60"
            onClick={handleClick}
            disabled={isSaving}
            aria-label={`${label}: ${statusLabel}. Click to change.`}
        >
            {value === true && <CheckIcon className="size-4 text-green-500" />}
            {value === false && <XIcon className="size-4 text-red-500" />}
            {(value === null || value === undefined) && (
                <span className="text-sm leading-none text-muted-foreground">-</span>
            )}
        </button>
    )
}

function SectionActionIcon({
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

function getAgeLabel(dateOfBirth: string | null | undefined) {
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

function getBmiCategory(bmi: number | null) {
    if (bmi == null) return null
    if (bmi < 18.5) return "Underweight"
    if (bmi < 25) return "Normal"
    if (bmi < 30) return "Overweight"
    if (bmi < 35) return "Obese (Class I)"
    if (bmi < 40) return "Obese (Class II)"
    return "Obese (Class III)"
}

function SsnField({
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
    const [isEditing, setIsEditing] = React.useState(false)
    const [editValue, setEditValue] = React.useState("")
    const [isSaving, setIsSaving] = React.useState(false)
    const displayValue = revealedValue || maskedValue || "-"

    const save = async () => {
        setIsSaving(true)
        try {
            await onSave(editValue.trim() || null)
            setEditValue("")
            setIsEditing(false)
        } finally {
            setIsSaving(false)
        }
    }

    if (isEditing) {
        return (
            <div className="flex min-w-0 items-center gap-2">
                <input
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
                            setIsEditing(false)
                        }
                    }}
                    placeholder="XXX-XX-XXXX"
                    className="h-7 min-w-0 rounded-md border border-input bg-background px-2 text-sm"
                />
                <Button type="button" variant="ghost" size="icon" className="size-7" onClick={() => void save()} disabled={isSaving}>
                    <CheckIcon className="size-3.5" />
                </Button>
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-7"
                    onClick={() => {
                        setEditValue("")
                        setIsEditing(false)
                    }}
                    disabled={isSaving}
                >
                    <XIcon className="size-3.5" />
                </Button>
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
                    <EyeIcon className="size-3.5" />
                </Button>
            )}
            <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-7"
                onClick={() => setIsEditing(true)}
                aria-label={`Edit ${label}`}
            >
                <PencilIcon className="size-3.5" />
            </Button>
        </div>
    )
}

export function SurrogateOverviewTab() {
    const params = useParams<{ id: string }>()
    const id = params.id
    const detailContext = useSurrogateDetailContext()
    const surrogateData = detailContext?.surrogate
    const { data: defaultPipeline } = useDefaultPipeline()
    const stageOptions = React.useMemo(() => defaultPipeline?.stages || [], [defaultPipeline])
    const stageById = React.useMemo(
        () => new Map(stageOptions.map((stage) => [stage.id, stage])),
        [stageOptions]
    )
    const { data: activityData } = useSurrogateActivity(id)
    const { data: tasksData } = useTasks({ surrogate_id: id, exclude_approvals: true })
    const updateSurrogateMutation = useUpdateSurrogate()
    const revealSensitiveInfoMutation = useRevealSurrogateSensitiveInfo()
    const [copiedEmail, setCopiedEmail] = React.useState(false)
    const [revealedSsn, setRevealedSsn] = React.useState<string | null>(null)
    const [revealedPartnerSsn, setRevealedPartnerSsn] = React.useState<string | null>(null)
    const [surrogatePersonalSectionAdded, setSurrogatePersonalSectionAdded] = React.useState(false)
    const [surrogatePersonalSectionHidden, setSurrogatePersonalSectionHidden] = React.useState(false)
    const [partnerSectionAdded, setPartnerSectionAdded] = React.useState(false)
    const [partnerSectionHidden, setPartnerSectionHidden] = React.useState(false)
    const [isDeletingPersonalSection, setIsDeletingPersonalSection] = React.useState(false)
    const [personalSectionPendingDelete, setPersonalSectionPendingDelete] = React.useState<"surrogate" | "partner" | null>(null)

    const bmiValue = React.useMemo(() => {
        if (!surrogateData) return null
        if (typeof surrogateData.bmi === "number") return surrogateData.bmi
        return computeBmi(surrogateData.height_ft, surrogateData.weight_lb)
    }, [surrogateData])
    const stageContext = React.useMemo(
        () => getSurrogateStageContext(surrogateData ?? null, stageById),
        [surrogateData, stageById]
    )
    const leadIntakeWarnings = React.useMemo(
        () => surrogateData?.lead_intake_warnings ?? [],
        [surrogateData]
    )
    const leadWarningMap = React.useMemo(
        () => new Map(leadIntakeWarnings.map((warning) => [warning.field_key, warning])),
        [leadIntakeWarnings]
    )

    if (!surrogateData) {
        return null
    }

    const effectiveStage = stageContext.effectiveStage
    const isHeartbeatConfirmedOrLater = stageHasCapability(
        effectiveStage ?? { stage_key: surrogateData.stage_key, stage_slug: surrogateData.stage_slug },
        "shows_pregnancy_tracking"
    )
    const isTerminalIntakeOutcome =
        stageContext.effectiveStageKey === "lost" || stageContext.effectiveStageKey === "disqualified"
    const emailLeadWarning = leadWarningMap.get("email")
    const phoneLeadWarning = leadWarningMap.get("phone")
    const stateLeadWarning = leadWarningMap.get("state")
    const heightLeadWarning = leadWarningMap.get("height_ft")
    const weightLeadWarning = leadWarningMap.get("weight_lb")
    const maritalStatusOptions = getMaritalStatusOptions(surrogateData.marital_status)
    const bmiCategory = getBmiCategory(bmiValue)
    const hasSurrogatePersonalInfo = Boolean(
        surrogateData.marital_status ||
        surrogateData.ssn_masked ||
        surrogateData.address_line1 ||
        surrogateData.address_line2 ||
        surrogateData.address_city ||
        surrogateData.address_state ||
        surrogateData.address_postal
    )
    const hasPartnerInfo = Boolean(
        surrogateData.partner_name ||
        surrogateData.partner_date_of_birth ||
        surrogateData.partner_email ||
        surrogateData.partner_phone ||
        surrogateData.partner_ssn_masked ||
        surrogateData.partner_address_line1 ||
        surrogateData.partner_address_line2 ||
        surrogateData.partner_city ||
        surrogateData.partner_state ||
        surrogateData.partner_postal
    )
    const showSurrogatePersonalInfo =
        (hasSurrogatePersonalInfo || surrogatePersonalSectionAdded) && !surrogatePersonalSectionHidden
    const showPartnerInfo = (hasPartnerInfo || partnerSectionAdded) && !partnerSectionHidden
    const hasAnyPersonalInfoSection = showSurrogatePersonalInfo || showPartnerInfo

    const copyEmail = () => {
        navigator.clipboard.writeText(surrogateData.email)
        setCopiedEmail(true)
        setTimeout(() => setCopiedEmail(false), 2000)
    }

    const updateSurrogate = async (data: Partial<SurrogateUpdatePayload>) => {
        await updateSurrogateMutation.mutateAsync({
            surrogateId: id,
            data,
        })
    }

    const revealSensitiveInfo = async () => {
        const payload = await revealSensitiveInfoMutation.mutateAsync(id)
        setRevealedSsn(payload.ssn)
        setRevealedPartnerSsn(payload.partner_ssn)
    }

    const addSurrogatePersonalSection = () => {
        setSurrogatePersonalSectionHidden(false)
        setSurrogatePersonalSectionAdded(true)
    }

    const addPartnerSection = () => {
        setPartnerSectionHidden(false)
        setPartnerSectionAdded(true)
    }

    const deletePersonalSection = async () => {
        if (!personalSectionPendingDelete) return

        setIsDeletingPersonalSection(true)
        try {
            if (personalSectionPendingDelete === "surrogate") {
                await updateSurrogate({
                    marital_status: null,
                    ssn: null,
                    address_line1: null,
                    address_line2: null,
                    address_city: null,
                    address_state: null,
                    address_postal: null,
                })
                setRevealedSsn(null)
                setSurrogatePersonalSectionAdded(false)
                setSurrogatePersonalSectionHidden(true)
            } else {
                await updateSurrogate({
                    partner_name: null,
                    partner_date_of_birth: null,
                    partner_email: null,
                    partner_phone: null,
                    partner_ssn: null,
                    partner_address_line1: null,
                    partner_address_line2: null,
                    partner_city: null,
                    partner_state: null,
                    partner_postal: null,
                })
                setRevealedPartnerSsn(null)
                setPartnerSectionAdded(false)
                setPartnerSectionHidden(true)
            }
            setPersonalSectionPendingDelete(null)
        } finally {
            setIsDeletingPersonalSection(false)
        }
    }

    return (
        <TabsContent value="overview" className="space-y-4">
            <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
                <div className="space-y-4">
                    <SurrogateOverviewCard title="Contact Information" icon={UserIcon}>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Name:</span>
                            <InlineEditField
                                value={surrogateData.full_name}
                                onSave={async (value) => {
                                    await updateSurrogateMutation.mutateAsync({
                                        surrogateId: id,
                                        data: { full_name: value },
                                    })
                                }}
                                placeholder="Enter name"
                                className="text-base font-medium"
                                label="Full name"
                            />
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Email:</span>
                            <div className="flex min-w-0 items-center gap-1.5">
                                <InlineEditField
                                    value={surrogateData.email}
                                    onSave={async (value) => {
                                        await updateSurrogateMutation.mutateAsync({
                                            surrogateId: id,
                                            data: { email: value },
                                        })
                                    }}
                                    type="email"
                                    placeholder="Enter email"
                                    validate={(value) => (!value.includes("@") ? "Invalid email" : null)}
                                    label="Email"
                                />
                                {emailLeadWarning && (
                                    <LeadWarningIndicator
                                        warning={emailLeadWarning}
                                        fieldLabel={LEAD_WARNING_FIELD_LABELS.email}
                                    />
                                )}
                            </div>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-6 w-6"
                                onClick={copyEmail}
                                aria-label="Copy email"
                            >
                                {copiedEmail ? (
                                    <CheckIcon className="h-3 w-3" />
                                ) : (
                                    <CopyIcon className="h-3 w-3" />
                                )}
                            </Button>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Phone:</span>
                            <div className="flex min-w-0 items-center gap-1.5">
                                <InlineEditField
                                    value={surrogateData.phone ?? undefined}
                                    onSave={async (value) => {
                                        await updateSurrogateMutation.mutateAsync({
                                            surrogateId: id,
                                            data: { phone: value || null },
                                        })
                                    }}
                                    type="tel"
                                    placeholder="-"
                                    label="Phone"
                                />
                                {phoneLeadWarning && (
                                    <LeadWarningIndicator
                                        warning={phoneLeadWarning}
                                        fieldLabel={LEAD_WARNING_FIELD_LABELS.phone}
                                    />
                                )}
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">State:</span>
                            <div className="flex min-w-0 items-center gap-1.5">
                                <InlineEditField
                                    value={surrogateData.state ?? undefined}
                                    onSave={async (value) => {
                                        await updateSurrogateMutation.mutateAsync({
                                            surrogateId: id,
                                            data: { state: value || null },
                                        })
                                    }}
                                    placeholder="-"
                                    validate={(value) =>
                                        value && value.length !== 2
                                            ? "Use 2-letter code (e.g., CA, TX)"
                                            : null
                                    }
                                    label="State"
                                />
                                {stateLeadWarning && (
                                    <LeadWarningIndicator
                                        warning={stateLeadWarning}
                                        fieldLabel={LEAD_WARNING_FIELD_LABELS.state}
                                    />
                                )}
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Source:</span>
                            <Badge variant="secondary" className="capitalize">
                                {surrogateData.source}
                            </Badge>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">Created:</span>
                            <span className="text-sm">{formatDate(surrogateData.created_at)}</span>
                        </div>
                    </SurrogateOverviewCard>

                    <SurrogateOverviewCard title="Demographics" icon={InfoIcon}>
                        <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-5">
                            <ProfileMetric
                                icon={CalendarDaysIcon}
                                label="Date of Birth"
                                primary={
                                    <InlineDateField
                                        value={surrogateData.date_of_birth}
                                        onSave={async (value) => {
                                            await updateSurrogateMutation.mutateAsync({
                                                surrogateId: id,
                                                data: { date_of_birth: value },
                                            })
                                        }}
                                        placeholder="-"
                                        label="Date of Birth"
                                    />
                                }
                                secondary={getAgeLabel(surrogateData.date_of_birth)}
                            />
                            <ProfileMetric
                                icon={UsersIcon}
                                label="Race / Ethnicity"
                                primary={
                                    <InlineEditField
                                        value={surrogateData.race ?? undefined}
                                        onSave={async (value) => {
                                            await updateSurrogateMutation.mutateAsync({
                                                surrogateId: id,
                                                data: { race: value || null },
                                            })
                                        }}
                                        placeholder="-"
                                        label="Race / Ethnicity"
                                        displayClassName="w-fit"
                                    />
                                }
                            />
                            <ProfileMetric
                                icon={RulerIcon}
                                label="Height"
                                primary={
                                    <InlineHeightField
                                        value={surrogateData.height_ft}
                                        onSave={async (value) => {
                                            await updateSurrogateMutation.mutateAsync({
                                                surrogateId: id,
                                                data: { height_ft: value },
                                            })
                                        }}
                                    />
                                }
                                warning={
                                    heightLeadWarning ? (
                                        <LeadWarningIndicator
                                            warning={heightLeadWarning}
                                            fieldLabel={LEAD_WARNING_FIELD_LABELS.height_ft}
                                        />
                                    ) : undefined
                                }
                            />
                            <ProfileMetric
                                icon={WeightIcon}
                                label="Weight"
                                primary={
                                    <InlineWeightField
                                        value={surrogateData.weight_lb}
                                        onSave={async (value) => {
                                            await updateSurrogateMutation.mutateAsync({
                                                surrogateId: id,
                                                data: { weight_lb: value },
                                            })
                                        }}
                                    />
                                }
                                warning={
                                    weightLeadWarning ? (
                                        <LeadWarningIndicator
                                            warning={weightLeadWarning}
                                            fieldLabel={LEAD_WARNING_FIELD_LABELS.weight_lb}
                                        />
                                    ) : undefined
                                }
                            />
                            <ProfileMetric
                                icon={ScaleIcon}
                                label="BMI"
                                primary={bmiValue ?? "-"}
                                badge={
                                    bmiCategory ? (
                                        <Badge variant="secondary" className="bg-emerald-100 text-emerald-900 hover:bg-emerald-100 dark:bg-emerald-950/60 dark:text-emerald-100">
                                            {bmiCategory}
                                        </Badge>
                                    ) : undefined
                                }
                            />
                        </div>
                    </SurrogateOverviewCard>

                    <>
                            <SurrogateOverviewCard
                                title="Personal Information"
                                icon={UserIcon}
                                action={
                                    <DropdownMenu>
                                        <DropdownMenuTrigger
                                            render={
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    aria-label="Edit Personal Information"
                                                    className="group h-8 rounded-full border-border/70 bg-background/90 px-3.5 text-xs font-medium shadow-none transition-colors hover:bg-accent/70 data-[state=open]:bg-accent data-[state=open]:text-accent-foreground"
                                                />
                                            }
                                        >
                                            <PencilIcon className="size-3.5 text-muted-foreground transition-colors group-data-[state=open]:text-current" />
                                            Edit Info
                                            <ChevronDownIcon className="ml-0.5 size-3.5 text-muted-foreground transition-all group-data-[state=open]:translate-y-px group-data-[state=open]:text-current" />
                                        </DropdownMenuTrigger>
                                        <DropdownMenuContent
                                            align="end"
                                            sideOffset={8}
                                            className="w-56 rounded-2xl border border-border/70 bg-background/95 p-1.5 shadow-lg supports-[backdrop-filter]:bg-background/90"
                                        >
                                            {(!showSurrogatePersonalInfo || !showPartnerInfo) && (
                                                <DropdownMenuGroup>
                                                    <DropdownMenuSub>
                                                        <DropdownMenuSubTrigger className="rounded-xl px-2.5 py-2 font-medium">
                                                            <SectionActionIcon icon={<PlusIcon className="size-4" />} />
                                                            Add Section
                                                        </DropdownMenuSubTrigger>
                                                        <DropdownMenuSubContent className="w-52 rounded-2xl border border-border/70 bg-background/95 p-1.5 shadow-lg supports-[backdrop-filter]:bg-background/90">
                                                            {!showSurrogatePersonalInfo && (
                                                                <DropdownMenuItem
                                                                    onClick={addSurrogatePersonalSection}
                                                                    className="rounded-xl px-2.5 py-2"
                                                                >
                                                                    <SectionActionIcon icon={<UserIcon className="size-4" />} />
                                                                    <span className="font-medium">Surrogate</span>
                                                                </DropdownMenuItem>
                                                            )}
                                                            {!showPartnerInfo && (
                                                                <DropdownMenuItem
                                                                    onClick={addPartnerSection}
                                                                    className="rounded-xl px-2.5 py-2"
                                                                >
                                                                    <SectionActionIcon icon={<UsersIcon className="size-4" />} />
                                                                    <span className="font-medium">Partner</span>
                                                                </DropdownMenuItem>
                                                            )}
                                                        </DropdownMenuSubContent>
                                                    </DropdownMenuSub>
                                                </DropdownMenuGroup>
                                            )}
                                            {hasAnyPersonalInfoSection && (
                                                <DropdownMenuGroup>
                                                    <DropdownMenuSub>
                                                        <DropdownMenuSubTrigger className="rounded-xl px-2.5 py-2 font-medium text-destructive data-open:bg-destructive/10 data-open:text-destructive focus:bg-destructive/10 focus:text-destructive">
                                                            <SectionActionIcon icon={<Trash2Icon className="size-4" />} tone="destructive" />
                                                            Delete Section
                                                        </DropdownMenuSubTrigger>
                                                        <DropdownMenuSubContent className="w-52 rounded-2xl border border-border/70 bg-background/95 p-1.5 shadow-lg supports-[backdrop-filter]:bg-background/90">
                                                            {showSurrogatePersonalInfo && (
                                                                <DropdownMenuItem
                                                                    onClick={() => setPersonalSectionPendingDelete("surrogate")}
                                                                    variant="destructive"
                                                                    className="rounded-xl px-2.5 py-2"
                                                                >
                                                                    <SectionActionIcon icon={<UserIcon className="size-4" />} tone="destructive" />
                                                                    <span className="font-medium">Delete Surrogate</span>
                                                                </DropdownMenuItem>
                                                            )}
                                                            {showPartnerInfo && (
                                                                <DropdownMenuItem
                                                                    onClick={() => setPersonalSectionPendingDelete("partner")}
                                                                    variant="destructive"
                                                                    className="rounded-xl px-2.5 py-2"
                                                                >
                                                                    <SectionActionIcon icon={<UsersIcon className="size-4" />} tone="destructive" />
                                                                    <span className="font-medium">Delete Partner</span>
                                                                </DropdownMenuItem>
                                                            )}
                                                        </DropdownMenuSubContent>
                                                    </DropdownMenuSub>
                                                </DropdownMenuGroup>
                                            )}
                                        </DropdownMenuContent>
                                    </DropdownMenu>
                                }
                            >
                                {!hasAnyPersonalInfoSection ? (
                                    <p className="py-4 text-center text-sm text-muted-foreground">
                                        No personal information added yet.
                                    </p>
                                ) : (
                                    <div className="grid items-stretch gap-4 lg:grid-cols-2">
                                    {showSurrogatePersonalInfo && (
                                        <PersonalInfoColumn title="Surrogate" icon={UserIcon}>
                                        <PersonalInfoRow label="Marital Status">
                                            <NativeSelect
                                                aria-label="Marital status"
                                                value={surrogateData.marital_status ?? ""}
                                                onChange={(event) =>
                                                    void updateSurrogate({
                                                        marital_status: event.target.value || null,
                                                    })
                                                }
                                                className="h-8 w-full max-w-[15rem]"
                                            >
                                                <NativeSelectOption value="">Not provided</NativeSelectOption>
                                                {maritalStatusOptions.map((option) => (
                                                    <NativeSelectOption key={option.value} value={option.value}>
                                                        {option.label}
                                                    </NativeSelectOption>
                                                ))}
                                            </NativeSelect>
                                        </PersonalInfoRow>
                                        <PersonalInfoRow label="SSN">
                                            <SsnField
                                                label="surrogate SSN"
                                                maskedValue={surrogateData.ssn_masked}
                                                revealedValue={revealedSsn}
                                                isRevealPending={revealSensitiveInfoMutation.isPending}
                                                onReveal={revealSensitiveInfo}
                                                onSave={async (value) => {
                                                    await updateSurrogate({ ssn: value })
                                                    setRevealedSsn(null)
                                                }}
                                            />
                                        </PersonalInfoRow>
                                        <PersonalInfoRow label="Address Line 1">
                                            <InlineEditField
                                                value={surrogateData.address_line1}
                                                onSave={async (value) => updateSurrogate({ address_line1: value || null })}
                                                placeholder="-"
                                                label="Surrogate address line 1"
                                            />
                                        </PersonalInfoRow>
                                        <PersonalInfoRow label="Address Line 2">
                                            <InlineEditField
                                                value={surrogateData.address_line2}
                                                onSave={async (value) => updateSurrogate({ address_line2: value || null })}
                                                placeholder="-"
                                                label="Surrogate address line 2"
                                            />
                                        </PersonalInfoRow>
                                        <PersonalInfoRow label="City">
                                            <InlineEditField
                                                value={surrogateData.address_city}
                                                onSave={async (value) => updateSurrogate({ address_city: value || null })}
                                                placeholder="-"
                                                label="Surrogate city"
                                            />
                                        </PersonalInfoRow>
                                        <PersonalInfoRow label="State">
                                            <InlineEditField
                                                value={surrogateData.address_state}
                                                onSave={async (value) => updateSurrogate({ address_state: value || null })}
                                                placeholder="-"
                                                validate={(value) =>
                                                    value && value.length !== 2
                                                        ? "Use 2-letter code (e.g., CA, TX)"
                                                        : null
                                                }
                                                label="Surrogate state"
                                            />
                                        </PersonalInfoRow>
                                        <PersonalInfoRow label="Postal Code">
                                            <InlineEditField
                                                value={surrogateData.address_postal}
                                                onSave={async (value) => updateSurrogate({ address_postal: value || null })}
                                                placeholder="-"
                                                label="Surrogate postal code"
                                            />
                                        </PersonalInfoRow>
                                        </PersonalInfoColumn>
                                    )}

                                    {showPartnerInfo && (
                                        <PersonalInfoColumn title="Partner" icon={UsersIcon}>
                                            <PersonalInfoRow label="Full Name">
                                                <InlineEditField
                                                    value={surrogateData.partner_name}
                                                    onSave={async (value) => updateSurrogate({ partner_name: value || null })}
                                                    placeholder="-"
                                                    label="Partner full name"
                                                />
                                            </PersonalInfoRow>
                                            <PersonalInfoRow label="DOB">
                                                <InlineDateField
                                                    value={surrogateData.partner_date_of_birth}
                                                    onSave={async (value) => updateSurrogate({ partner_date_of_birth: value })}
                                                    placeholder="-"
                                                    label="Partner date of birth"
                                                />
                                            </PersonalInfoRow>
                                            <PersonalInfoRow label="Email">
                                                <InlineEditField
                                                    value={surrogateData.partner_email}
                                                    onSave={async (value) => updateSurrogate({ partner_email: value || null })}
                                                    type="email"
                                                    placeholder="-"
                                                    validate={(value) => (value && !value.includes("@") ? "Invalid email" : null)}
                                                    label="Partner email"
                                                />
                                            </PersonalInfoRow>
                                            <PersonalInfoRow label="Phone">
                                                <InlineEditField
                                                    value={surrogateData.partner_phone}
                                                    onSave={async (value) => updateSurrogate({ partner_phone: value || null })}
                                                    type="tel"
                                                    placeholder="-"
                                                    label="Partner phone"
                                                />
                                            </PersonalInfoRow>
                                            <PersonalInfoRow label="SSN">
                                                <SsnField
                                                    label="partner SSN"
                                                    maskedValue={surrogateData.partner_ssn_masked}
                                                    revealedValue={revealedPartnerSsn}
                                                    isRevealPending={revealSensitiveInfoMutation.isPending}
                                                    onReveal={revealSensitiveInfo}
                                                    onSave={async (value) => {
                                                        await updateSurrogate({ partner_ssn: value })
                                                        setRevealedPartnerSsn(null)
                                                    }}
                                                />
                                            </PersonalInfoRow>
                                            <PersonalInfoRow label="Address Line 1">
                                                <InlineEditField
                                                    value={surrogateData.partner_address_line1}
                                                    onSave={async (value) => updateSurrogate({ partner_address_line1: value || null })}
                                                    placeholder="-"
                                                    label="Partner address line 1"
                                                />
                                            </PersonalInfoRow>
                                            <PersonalInfoRow label="Address Line 2">
                                                <InlineEditField
                                                    value={surrogateData.partner_address_line2}
                                                    onSave={async (value) => updateSurrogate({ partner_address_line2: value || null })}
                                                    placeholder="-"
                                                    label="Partner address line 2"
                                                />
                                            </PersonalInfoRow>
                                            <PersonalInfoRow label="City">
                                                <InlineEditField
                                                    value={surrogateData.partner_city}
                                                    onSave={async (value) => updateSurrogate({ partner_city: value || null })}
                                                    placeholder="-"
                                                    label="Partner city"
                                                />
                                            </PersonalInfoRow>
                                            <PersonalInfoRow label="State">
                                                <InlineEditField
                                                    value={surrogateData.partner_state}
                                                    onSave={async (value) => updateSurrogate({ partner_state: value || null })}
                                                    placeholder="-"
                                                    validate={(value) =>
                                                        value && value.length !== 2
                                                            ? "Use 2-letter code (e.g., CA, TX)"
                                                            : null
                                                    }
                                                    label="Partner state"
                                                />
                                            </PersonalInfoRow>
                                            <PersonalInfoRow label="Postal Code">
                                                <InlineEditField
                                                    value={surrogateData.partner_postal}
                                                    onSave={async (value) => updateSurrogate({ partner_postal: value || null })}
                                                    placeholder="-"
                                                    label="Partner postal code"
                                                />
                                            </PersonalInfoRow>
                                        </PersonalInfoColumn>
                                    )}
                                    </div>
                                )}
                            </SurrogateOverviewCard>

                            <AlertDialog
                                open={personalSectionPendingDelete !== null}
                                onOpenChange={(open) => {
                                    if (!open && !isDeletingPersonalSection) {
                                        setPersonalSectionPendingDelete(null)
                                    }
                                }}
                            >
                                <AlertDialogContent>
                                    <AlertDialogHeader>
                                        <AlertDialogTitle>
                                            Delete {personalSectionPendingDelete === "surrogate" ? "Surrogate" : "Partner"} section?
                                        </AlertDialogTitle>
                                        <AlertDialogDescription>
                                            This removes the section from Personal Information and clears any saved details. You can add it back later.
                                        </AlertDialogDescription>
                                    </AlertDialogHeader>
                                    <AlertDialogFooter>
                                        <AlertDialogCancel disabled={isDeletingPersonalSection}>Cancel</AlertDialogCancel>
                                        <AlertDialogAction
                                            variant="destructive"
                                            onClick={deletePersonalSection}
                                            disabled={isDeletingPersonalSection}
                                        >
                                            Delete Section
                                        </AlertDialogAction>
                                    </AlertDialogFooter>
                                </AlertDialogContent>
                            </AlertDialog>
                        </>

                    <CombinedMedicalInsuranceCard
                        surrogateData={surrogateData}
                        onUpdate={async (data) => {
                            await updateSurrogateMutation.mutateAsync({
                                surrogateId: id,
                                data,
                            })
                        }}
                    />
                </div>

                <div className="space-y-4">
                    {isHeartbeatConfirmedOrLater && !isTerminalIntakeOutcome && (
                        <PregnancyTrackerCard
                            surrogateData={surrogateData}
                            onUpdate={async (data) => {
                                await updateSurrogateMutation.mutateAsync({
                                    surrogateId: id,
                                    data,
                                })
                            }}
                        />
                    )}

                    <ActivityTimeline
                        surrogateId={id}
                        currentStageId={surrogateData.stage_id}
                        stages={stageOptions}
                        activities={activityData?.items ?? []}
                        tasks={tasksData?.items ?? []}
                        {...(effectiveStage?.id ? { effectiveStageId: effectiveStage.id } : {})}
                    />

                    <SurrogateOverviewCard title="Eligibility Checklist" icon={ClipboardCheckIcon}>
                        {(surrogateData.eligibility_checklist ?? []).map((item) => {
                            if (item.type === "boolean") {
                                if (!isChecklistBooleanFieldKey(item.key)) {
                                    return (
                                        <div key={item.key} className="flex items-center gap-2">
                                            <span className="flex size-6 shrink-0 items-center justify-center text-sm text-muted-foreground">
                                                -
                                            </span>
                                            <span className="text-sm">{item.label}</span>
                                        </div>
                                    )
                                }

                                const currentValue = surrogateData[item.key]

                                return (
                                    <div key={item.key} className="flex items-center gap-2">
                                        <ChecklistStatusButton
                                            label={item.label}
                                            value={currentValue}
                                            onChange={async (value) => {
                                                await updateSurrogateMutation.mutateAsync({
                                                    surrogateId: id,
                                                    data: { [item.key]: value } as SurrogateUpdatePayload,
                                                })
                                            }}
                                        />
                                        <span className="text-sm">{item.label}</span>
                                    </div>
                                )
                            }

                            if (item.key === "journey_timing_preference") {
                                const currentValue =
                                    surrogateData.journey_timing_preference ??
                                    (typeof item.value === "string" ? item.value : "")

                                return (
                                    <div key={item.key} className="grid gap-1 sm:grid-cols-[8rem_minmax(0,1fr)] sm:items-center">
                                        <span className="text-sm text-muted-foreground">{item.label}:</span>
                                        <NativeSelect
                                            value={currentValue}
                                            onChange={async (event) => {
                                                await updateSurrogateMutation.mutateAsync({
                                                    surrogateId: id,
                                                    data: {
                                                        journey_timing_preference: event.target.value || null,
                                                    },
                                                })
                                            }}
                                            size="sm"
                                            className="w-full max-w-44"
                                            aria-label={item.label}
                                        >
                                            <NativeSelectOption value="">Not provided</NativeSelectOption>
                                            {JOURNEY_TIMING_OPTIONS.map((option) => (
                                                <NativeSelectOption key={option.value} value={option.value}>
                                                    {option.label}
                                                </NativeSelectOption>
                                            ))}
                                        </NativeSelect>
                                    </div>
                                )
                            }

                            if (item.type === "number" && (item.key === "num_deliveries" || item.key === "num_csections")) {
                                const fallbackValue =
                                    typeof item.value === "number"
                                        ? item.value
                                        : typeof item.value === "string" && /^\d+$/.test(item.value)
                                            ? Number.parseInt(item.value, 10)
                                            : null
                                const currentValue = surrogateData[item.key] ?? fallbackValue

                                return (
                                    <div key={item.key} className="grid gap-1 sm:grid-cols-[8rem_minmax(0,1fr)] sm:items-center">
                                        <span className="text-sm text-muted-foreground">{item.label}:</span>
                                        <InlineEditField
                                            value={currentValue != null ? String(currentValue) : undefined}
                                            onSave={async (value) => {
                                                const trimmed = value.trim()
                                                await updateSurrogateMutation.mutateAsync({
                                                    surrogateId: id,
                                                    data: {
                                                        [item.key]: trimmed ? Number.parseInt(trimmed, 10) : null,
                                                    } as SurrogateUpdatePayload,
                                                })
                                            }}
                                            validate={(value) => {
                                                const trimmed = value.trim()
                                                if (!trimmed) return null
                                                return /^\d+$/.test(trimmed)
                                                    ? null
                                                    : "Enter a valid number"
                                            }}
                                            placeholder="-"
                                            label={item.label}
                                            displayClassName="w-fit"
                                        />
                                    </div>
                                )
                            }

                            return (
                                <div key={item.key} className="flex items-center gap-2">
                                    <span className="text-sm text-muted-foreground">
                                        {item.label}:
                                    </span>
                                    <span className="text-sm">{item.display_value}</span>
                                </div>
                            )
                        })}
                    </SurrogateOverviewCard>
                </div>
            </div>
        </TabsContent>
    )
}
