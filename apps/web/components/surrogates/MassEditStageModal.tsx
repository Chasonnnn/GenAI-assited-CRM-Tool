"use client"

import * as React from "react"
import { Loader2Icon, SparklesIcon, TriangleAlertIcon, XIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { formatRace } from "@/lib/formatters"
import { cn } from "@/lib/utils"
import type { PipelineStage } from "@/lib/api/pipelines"
import type {
    SurrogateMassEditStageFilters,
    SurrogateMassEditStagePreviewResponse,
} from "@/lib/api/surrogates"
import {
    useApplySurrogateMassEditStage,
    usePreviewSurrogateMassEditStage,
    useSurrogateMassEditOptions,
} from "@/lib/hooks/use-surrogates"
import { toast } from "sonner"

type TriState = "any" | "true" | "false"
type ComparisonOp = ">" | ">=" | "<" | "<=" | "="

function parseStates(input: string): { states: string[] | undefined; error: string | null } {
    const trimmed = input.trim()
    if (!trimmed) return { states: undefined, error: null }

    const parts = trimmed
        .split(/[,\s]+/g)
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean)

    const invalid = parts.filter((s) => !/^[A-Z]{2}$/.test(s))
    if (invalid.length > 0) {
        return { states: undefined, error: `Invalid state codes: ${invalid.slice(0, 5).join(", ")}` }
    }

    // Deduplicate while preserving order
    const seen = new Set<string>()
    const states = parts.filter((s) => (seen.has(s) ? false : (seen.add(s), true)))
    return { states, error: null }
}

function triStateToBool(v: TriState): boolean | undefined {
    if (v === "any") return undefined
    return v === "true"
}

function numberOrUndefined(raw: string, opts?: { min?: number; max?: number }): number | undefined {
    const trimmed = raw.trim()
    if (!trimmed) return undefined
    const n = Number(trimmed)
    if (!Number.isFinite(n)) return undefined
    const value = Math.floor(n)
    if (opts?.min !== undefined && value < opts.min) return undefined
    if (opts?.max !== undefined && value > opts.max) return undefined
    return value
}

function floatOrUndefined(raw: string, opts?: { min?: number; max?: number }): number | undefined {
    const trimmed = raw.trim()
    if (!trimmed) return undefined
    const n = Number(trimmed)
    if (!Number.isFinite(n)) return undefined
    if (opts?.min !== undefined && n < opts.min) return undefined
    if (opts?.max !== undefined && n > opts.max) return undefined
    return n
}

export function MassEditStageModal({
    open,
    onOpenChange,
    stages,
    baseFilters,
}: {
    open: boolean
    onOpenChange: (open: boolean) => void
    stages: PipelineStage[]
    baseFilters: SurrogateMassEditStageFilters
}) {
    const previewMutation = usePreviewSurrogateMassEditStage()
    const applyMutation = useApplySurrogateMassEditStage()
    const optionsQuery = useSurrogateMassEditOptions({ enabled: open })

    const [statesInput, setStatesInput] = React.useState("")
    const [selectedRaces, setSelectedRaces] = React.useState<string[]>([])
    const [raceToAdd, setRaceToAdd] = React.useState<string | null>(null)
    const [ageOp, setAgeOp] = React.useState<ComparisonOp | null>(null)
    const [ageValue, setAgeValue] = React.useState("")
    const [bmiOp, setBmiOp] = React.useState<ComparisonOp | null>(null)
    const [bmiValue, setBmiValue] = React.useState("")

    const [isAgeEligible, setIsAgeEligible] = React.useState<TriState>("any")
    const [isCitizenOrPr, setIsCitizenOrPr] = React.useState<TriState>("any")
    const [hasChild, setHasChild] = React.useState<TriState>("any")
    const [isNonSmoker, setIsNonSmoker] = React.useState<boolean | null>(null)
    const [hasSurrogateExperience, setHasSurrogateExperience] = React.useState<TriState>("any")

    const [targetStageId, setTargetStageId] = React.useState<string>("")
    const [triggerWorkflows, setTriggerWorkflows] = React.useState(false)
    const [reason, setReason] = React.useState("")

    const [preview, setPreview] = React.useState<SurrogateMassEditStagePreviewResponse | null>(null)

    const activeStages = React.useMemo(
        () => [...stages].filter((s) => s.is_active).sort((a, b) => a.order - b.order),
        [stages]
    )

    // Reset when opened (and pick disqualified by default if present)
    React.useEffect(() => {
        if (!open) return
        setStatesInput("")
        setSelectedRaces([])
        setRaceToAdd(null)
        setAgeOp(null)
        setAgeValue("")
        setBmiOp(null)
        setBmiValue("")
        setIsAgeEligible("any")
        setIsCitizenOrPr("any")
        setHasChild("any")
        setIsNonSmoker(null)
        setHasSurrogateExperience("any")
        setTriggerWorkflows(false)
        setReason("")
        setPreview(null)

        const disqualified = activeStages.find((s) => s.slug === "disqualified")
        setTargetStageId(disqualified?.id ?? "")
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open])

    const { states, error: statesError } = React.useMemo(() => parseStates(statesInput), [statesInput])
    const races = React.useMemo(() => (selectedRaces.length ? selectedRaces : undefined), [selectedRaces])

    const { age_min, age_max, ageError } = React.useMemo(() => {
        const raw = ageValue.trim()
        if (!raw) return { age_min: undefined, age_max: undefined, ageError: null as string | null }

        if (!ageOp) return { age_min: undefined, age_max: undefined, ageError: "Choose an operator for Age." }

        const value = numberOrUndefined(raw, { min: 0, max: 120 })
        if (value === undefined) {
            return { age_min: undefined, age_max: undefined, ageError: "Age must be an integer from 0 to 120." }
        }

        switch (ageOp) {
            case ">":
                return { age_min: value + 1, age_max: undefined, ageError: null }
            case ">=":
                return { age_min: value, age_max: undefined, ageError: null }
            case "<":
                return { age_min: undefined, age_max: value - 1, ageError: null }
            case "<=":
                return { age_min: undefined, age_max: value, ageError: null }
            case "=":
                return { age_min: value, age_max: value, ageError: null }
        }
    }, [ageOp, ageValue])

    const { bmi_min, bmi_max, bmiError } = React.useMemo(() => {
        const raw = bmiValue.trim()
        if (!raw) return { bmi_min: undefined, bmi_max: undefined, bmiError: null as string | null }

        if (!bmiOp) return { bmi_min: undefined, bmi_max: undefined, bmiError: "Choose an operator for BMI." }

        const value = floatOrUndefined(raw, { min: 0, max: 100 })
        if (value === undefined) {
            return { bmi_min: undefined, bmi_max: undefined, bmiError: "BMI must be a number from 0 to 100." }
        }

        const STRICT_EPS = 0.0001
        const EQ_TOL = 0.05 // approx match for 1-decimal BMI (e.g. 32.0 matches [31.95, 32.0499])

        switch (bmiOp) {
            case ">":
                return { bmi_min: value + STRICT_EPS, bmi_max: undefined, bmiError: null }
            case ">=":
                return { bmi_min: value, bmi_max: undefined, bmiError: null }
            case "<":
                return { bmi_min: undefined, bmi_max: value - STRICT_EPS, bmiError: null }
            case "<=":
                return { bmi_min: undefined, bmi_max: value, bmiError: null }
            case "=":
                return {
                    bmi_min: Math.max(0, value - EQ_TOL),
                    bmi_max: value + (EQ_TOL - STRICT_EPS),
                    bmiError: null,
                }
        }
    }, [bmiOp, bmiValue])

    const derivedFilters = React.useMemo<SurrogateMassEditStageFilters>(() => {
        const is_age_eligible = triStateToBool(isAgeEligible)
        const is_citizen_or_pr = triStateToBool(isCitizenOrPr)
        const has_child = triStateToBool(hasChild)
        const is_non_smoker = isNonSmoker === null ? undefined : isNonSmoker
        const has_surrogate_experience = triStateToBool(hasSurrogateExperience)

        return {
            ...(states ? { states } : {}),
            ...(races ? { races } : {}),
            ...(age_min !== undefined ? { age_min } : {}),
            ...(age_max !== undefined ? { age_max } : {}),
            ...(bmi_min !== undefined ? { bmi_min } : {}),
            ...(bmi_max !== undefined ? { bmi_max } : {}),
            ...(is_age_eligible !== undefined ? { is_age_eligible } : {}),
            ...(is_citizen_or_pr !== undefined ? { is_citizen_or_pr } : {}),
            ...(has_child !== undefined ? { has_child } : {}),
            ...(is_non_smoker !== undefined ? { is_non_smoker } : {}),
            ...(has_surrogate_experience !== undefined ? { has_surrogate_experience } : {}),
        }
    }, [
        states,
        races,
        age_min,
        age_max,
        bmi_min,
        bmi_max,
        isAgeEligible,
        isCitizenOrPr,
        hasChild,
        isNonSmoker,
        hasSurrogateExperience,
    ])

    // Any filter change invalidates preview (forces a re-preview before apply)
    React.useEffect(() => {
        setPreview(null)
    }, [derivedFilters, targetStageId, triggerWorkflows, reason])

    const mergedFilters: SurrogateMassEditStageFilters = React.useMemo(
        () => ({ ...baseFilters, ...derivedFilters }),
        [baseFilters, derivedFilters]
    )

    const selectedStage = React.useMemo(
        () => activeStages.find((s) => s.id === targetStageId),
        [activeStages, targetStageId]
    )

    const canPreview = !statesError && !ageError && !bmiError
    const canApply = !!preview && !preview.over_limit && !!targetStageId && !applyMutation.isPending

    const handlePreview = async () => {
        if (!canPreview) return
        try {
            const result = await previewMutation.mutateAsync({ data: { filters: mergedFilters }, limit: 25 })
            setPreview(result)
            if (result.total === 0) toast.info("No surrogates matched those filters.")
        } catch (err) {
            const message = err instanceof Error ? err.message : "Preview failed"
            toast.error(message)
        }
    }

    const handleApply = async () => {
        if (!preview || !targetStageId) return
        try {
            const result = await applyMutation.mutateAsync({
                filters: mergedFilters,
                stage_id: targetStageId,
                expected_total: preview.total,
                trigger_workflows: triggerWorkflows,
                ...(reason.trim() ? { reason: reason.trim() } : {}),
            })

            if (result.failed?.length) {
                toast.error(`Updated ${result.applied}/${result.matched}. ${result.failed.length} failed.`)
            } else if (result.pending_approval) {
                toast.info(`Applied ${result.applied}. ${result.pending_approval} pending approval.`)
            } else {
                toast.success(`Updated ${result.applied} surrogate${result.applied === 1 ? "" : "s"}.`)
            }

            onOpenChange(false)
        } catch (err) {
            const message = err instanceof Error ? err.message : "Mass edit failed"
            toast.error(message)
        }
    }

    const baseBadges: Array<{ label: string; value: string }> = []
    if (baseFilters.stage_ids?.length) baseBadges.push({ label: "Stage", value: `${baseFilters.stage_ids.length} selected` })
    if (baseFilters.source) baseBadges.push({ label: "Source", value: baseFilters.source })
    if (baseFilters.queue_id) baseBadges.push({ label: "Queue", value: "Selected" })
    if (baseFilters.q) baseBadges.push({ label: "Search", value: baseFilters.q })
    if (baseFilters.created_from || baseFilters.created_to) {
        baseBadges.push({
            label: "Created",
            value: `${baseFilters.created_from ?? "…"} to ${baseFilters.created_to ?? "…"}`
        })
    }

    return (
        <Dialog open={open} onOpenChange={(next) => !applyMutation.isPending && onOpenChange(next)}>
            <DialogContent className="sm:max-w-3xl">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <SparklesIcon className="size-5" />
                        Mass Edit: Change Stage
                    </DialogTitle>
                    <DialogDescription>
                        Dev-only tool. Applies to all surrogates matching your current list filters plus any extra filters below.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-5">
                    {/* Base Filters */}
                    <div className="space-y-2">
                        <div className="text-sm font-medium">Base Filters (from list)</div>
                        <div className="flex flex-wrap gap-2">
                            {baseBadges.length === 0 ? (
                                <Badge variant="secondary">No base filters</Badge>
                            ) : (
                                baseBadges.map((b) => (
                                    <Badge key={b.label} variant="secondary">
                                        {b.label}: {b.value}
                                    </Badge>
                                ))
                            )}
                        </div>
                    </div>

                    <Separator />

                    {/* Extra Filters */}
                    <div className="space-y-3">
                        <div className="text-sm font-medium">Extra Filters</div>
                        <div className="grid gap-4 sm:grid-cols-2">
                            <div className="space-y-2">
                                <Label htmlFor="mass-states">States (comma or space separated)</Label>
                                <Input
                                    id="mass-states"
                                    value={statesInput}
                                    onChange={(e) => setStatesInput(e.target.value)}
                                    placeholder="CA, TX, FL"
                                />
                                {statesError && (
                                    <p className="text-xs text-destructive">{statesError}</p>
                                )}
                            </div>

                            <div className="space-y-2">
                                <Label>Race</Label>
                                <Select
                                    value={raceToAdd}
                                    onValueChange={(value) => {
                                        if (!value) return
                                        setSelectedRaces((prev) =>
                                            prev.includes(value) ? prev : [...prev, value]
                                        )
                                        setRaceToAdd(null)
                                    }}
                                    disabled={optionsQuery.isPending || optionsQuery.isError}
                                >
                                    <SelectTrigger>
                                        <SelectValue
                                            placeholder={
                                                optionsQuery.isPending
                                                    ? "Loading race options…"
                                                    : optionsQuery.isError
                                                        ? "Race options unavailable"
                                                        : "Add race"
                                            }
                                        />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {(optionsQuery.data?.races ?? []).map((raceKey) => (
                                            <SelectItem key={raceKey} value={raceKey}>
                                                {formatRace(raceKey)}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                {selectedRaces.length > 0 ? (
                                    <div className="flex flex-wrap gap-2">
                                        {selectedRaces.map((raceKey) => (
                                            <Badge key={raceKey} variant="secondary" className="gap-1 pr-1">
                                                {formatRace(raceKey)}
                                                <button
                                                    type="button"
                                                    className="rounded-sm p-0.5 hover:bg-black/10"
                                                    onClick={() =>
                                                        setSelectedRaces((prev) => prev.filter((r) => r !== raceKey))
                                                    }
                                                    aria-label={`Remove race ${formatRace(raceKey)}`}
                                                >
                                                    <XIcon className="size-3" />
                                                </button>
                                            </Badge>
                                        ))}
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            size="sm"
                                            className="h-6 px-2"
                                            onClick={() => setSelectedRaces([])}
                                        >
                                            Clear
                                        </Button>
                                    </div>
                                ) : (
                                    <p className="text-xs text-muted-foreground">
                                        Uses the standardized race categories from the intake application form.
                                    </p>
                                )}
                            </div>

                            <div className="space-y-2">
                                <Label>Age</Label>
                                <div className="grid grid-cols-[96px_1fr] gap-3">
                                    <Select
                                        value={ageOp}
                                        onValueChange={(v) => setAgeOp(v ? (v as ComparisonOp) : null)}
                                    >
                                        <SelectTrigger>
                                            <SelectValue placeholder="Op" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value=">">&gt;</SelectItem>
                                            <SelectItem value=">=">&gt;=</SelectItem>
                                            <SelectItem value="<">&lt;</SelectItem>
                                            <SelectItem value="<=">&lt;=</SelectItem>
                                            <SelectItem value="=">=</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <Input
                                        inputMode="numeric"
                                        value={ageValue}
                                        onChange={(e) => setAgeValue(e.target.value)}
                                        placeholder="e.g. 36"
                                    />
                                </div>
                                {ageError && <p className="text-xs text-destructive">{ageError}</p>}
                            </div>

                            <div className="space-y-2">
                                <Label>BMI</Label>
                                <div className="grid grid-cols-[96px_1fr] gap-3">
                                    <Select
                                        value={bmiOp}
                                        onValueChange={(v) => setBmiOp(v ? (v as ComparisonOp) : null)}
                                    >
                                        <SelectTrigger>
                                            <SelectValue placeholder="Op" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value=">">&gt;</SelectItem>
                                            <SelectItem value=">=">&gt;=</SelectItem>
                                            <SelectItem value="<">&lt;</SelectItem>
                                            <SelectItem value="<=">&lt;=</SelectItem>
                                            <SelectItem value="=">=</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <Input
                                        inputMode="decimal"
                                        value={bmiValue}
                                        onChange={(e) => setBmiValue(e.target.value)}
                                        placeholder="e.g. 32"
                                    />
                                </div>
                                {bmiError ? (
                                    <p className="text-xs text-destructive">{bmiError}</p>
                                ) : (
                                    <p className="text-xs text-muted-foreground">
                                        Note: BMI is computed from height/weight; “=” matches roughly the 1-decimal BMI shown in the UI.
                                    </p>
                                )}
                            </div>

                            <div className="space-y-2">
                                <Label>Age Eligible</Label>
                                <Select value={isAgeEligible} onValueChange={(v) => setIsAgeEligible(v as TriState)}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="any">Any</SelectItem>
                                        <SelectItem value="true">Yes</SelectItem>
                                        <SelectItem value="false">No</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="space-y-2">
                                <Label>US Citizen or PR</Label>
                                <Select value={isCitizenOrPr} onValueChange={(v) => setIsCitizenOrPr(v as TriState)}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="any">Any</SelectItem>
                                        <SelectItem value="true">Yes</SelectItem>
                                        <SelectItem value="false">No</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="space-y-2">
                                <Label>Has Child</Label>
                                <Select value={hasChild} onValueChange={(v) => setHasChild(v as TriState)}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="any">Any</SelectItem>
                                        <SelectItem value="true">Yes</SelectItem>
                                        <SelectItem value="false">No</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="space-y-2">
                                <Label>Non-Smoker</Label>
                                <div className="flex items-center gap-2">
                                    <Button
                                        type="button"
                                        variant={isNonSmoker === true ? "secondary" : "outline"}
                                        size="sm"
                                        onClick={() => setIsNonSmoker((prev) => (prev === true ? null : true))}
                                    >
                                        Yes
                                    </Button>
                                    <Button
                                        type="button"
                                        variant={isNonSmoker === false ? "secondary" : "outline"}
                                        size="sm"
                                        onClick={() => setIsNonSmoker((prev) => (prev === false ? null : false))}
                                    >
                                        No
                                    </Button>
                                    {isNonSmoker !== null && (
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => setIsNonSmoker(null)}
                                        >
                                            Clear
                                        </Button>
                                    )}
                                </div>
                                <p className="text-xs text-muted-foreground">
                                    Click again to unset.
                                </p>
                            </div>

                            <div className="space-y-2 sm:col-span-2">
                                <Label>Prior Surrogate Experience</Label>
                                <Select value={hasSurrogateExperience} onValueChange={(v) => setHasSurrogateExperience(v as TriState)}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="any">Any</SelectItem>
                                        <SelectItem value="true">Yes</SelectItem>
                                        <SelectItem value="false">No</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                    </div>

                    <Separator />

                    {/* Stage Change */}
                    <div className="space-y-3">
                        <div className="text-sm font-medium">Stage Change</div>
                        <div className="grid gap-4 sm:grid-cols-2">
                            <div className="space-y-2">
                                <Label>New Stage</Label>
                                <Select value={targetStageId} onValueChange={(v) => setTargetStageId(v ?? "")}>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select a stage">
                                            {(value: string | null) => {
                                                if (!value) return "Select a stage"
                                                const stage = activeStages.find((s) => s.id === value)
                                                return stage?.label ?? value
                                            }}
                                        </SelectValue>
                                    </SelectTrigger>
                                    <SelectContent>
                                        {activeStages.map((s) => (
                                            <SelectItem key={s.id} value={s.id}>
                                                {s.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                {selectedStage && (
                                    <p className="text-xs text-muted-foreground">
                                        Target: <span className="font-medium">{selectedStage.label}</span>
                                    </p>
                                )}
                            </div>

                            <div className="space-y-2">
                                <Label>Trigger Workflows</Label>
                                <div className="flex items-center justify-between rounded-md border px-3 py-2">
                                    <div className="text-sm">
                                        <div className="font-medium">Automation workflows</div>
                                        <div className="text-xs text-muted-foreground">
                                            Toggle whether status-change workflows run.
                                        </div>
                                    </div>
                                    <Switch checked={triggerWorkflows} onCheckedChange={setTriggerWorkflows} />
                                </div>
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="mass-reason">Reason (optional)</Label>
                            <Textarea
                                id="mass-reason"
                                value={reason}
                                onChange={(e) => setReason(e.target.value)}
                                placeholder="e.g. Bulk disqualify based on eligibility checklist"
                                rows={2}
                            />
                        </div>
                    </div>

                    <Separator />

                    {/* Preview */}
                    <div className="space-y-3">
                        <div className="flex items-center justify-between gap-3">
                            <div className="text-sm font-medium">Preview</div>
                            <Button
                                variant="outline"
                                onClick={handlePreview}
                                disabled={!canPreview || previewMutation.isPending || applyMutation.isPending}
                            >
                                {previewMutation.isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                                Preview Matches
                            </Button>
                        </div>

                        {preview && (
                            <div className={cn("rounded-lg border p-3", preview.over_limit && "border-amber-500/50 bg-amber-500/5")}>
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div className="text-sm">
                                        <span className="font-medium">{preview.total.toLocaleString()}</span> match{preview.total === 1 ? "" : "es"}
                                        {selectedStage ? (
                                            <>
                                                {" "}will be moved to{" "}
                                                <span className="font-medium">{selectedStage.label}</span>
                                            </>
                                        ) : null}
                                    </div>
                                    {preview.over_limit && (
                                        <div className="inline-flex items-center gap-2 text-xs text-amber-700">
                                            <TriangleAlertIcon className="size-4" />
                                            Too many matches (max {preview.max_apply.toLocaleString()}). Narrow filters.
                                        </div>
                                    )}
                                </div>

                                {preview.items.length > 0 && (
                                    <div className="mt-3">
                                        <div className="text-xs text-muted-foreground mb-2">Sample</div>
                                        <ScrollArea className="h-44 rounded-md border">
                                            <div className="divide-y">
                                                {preview.items.map((item) => (
                                                    <div key={item.id} className="px-3 py-2 text-sm flex items-center justify-between gap-3">
                                                        <div className="min-w-0">
                                                            <div className="truncate font-medium">
                                                                #{item.surrogate_number} {item.full_name}
                                                            </div>
                                                            <div className="truncate text-xs text-muted-foreground">
                                                                {item.state ?? "—"} · {item.status_label}
                                                                {typeof item.age === "number" ? ` · Age ${item.age}` : ""}
                                                            </div>
                                                        </div>
                                                        <Badge variant="secondary" className="shrink-0">
                                                            {new Date(item.created_at).toLocaleDateString()}
                                                        </Badge>
                                                    </div>
                                                ))}
                                            </div>
                                        </ScrollArea>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>

                <DialogFooter className="gap-2 sm:gap-2">
                    <Button
                        variant="outline"
                        onClick={() => onOpenChange(false)}
                        disabled={applyMutation.isPending}
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleApply}
                        disabled={!canApply}
                        className={cn(preview?.over_limit && "opacity-50")}
                    >
                        {applyMutation.isPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                        Apply Stage Change
                    </Button>
                </DialogFooter>

                {!preview && (
                    <div className="text-xs text-muted-foreground flex items-center gap-2">
                        <TriangleAlertIcon className="size-4" />
                        Always preview first. Apply requires the preview count (prevents accidental wide updates).
                    </div>
                )}
            </DialogContent>
        </Dialog>
    )
}
