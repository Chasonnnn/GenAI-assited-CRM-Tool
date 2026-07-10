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
    useApplySurrogateMassEditArchive,
    useApplySurrogateMassEditStage,
    usePreviewSurrogateMassEditStage,
    useSurrogateMassEditOptions,
} from "@/lib/hooks/use-surrogates"
import { toast } from "@/components/ui/toast"

type TriState = "any" | "true" | "false"
type ComparisonOp = ">" | ">=" | "<" | "<=" | "="
type ActionMode = "change_stage" | "archive"
type PreviewState = {
    signature: string
    result: SurrogateMassEditStagePreviewResponse
}
type MassEditStageState = {
    statesInput: string
    createdFrom: string
    createdTo: string
    selectedRaces: string[]
    raceToAdd: string | null
    ageOp: ComparisonOp | null
    ageValue: string
    bmiOp: ComparisonOp | null
    bmiValue: string
    isAgeEligible: TriState
    isCitizenOrPr: TriState
    hasChild: TriState
    isNonSmoker: boolean | null
    hasSurrogateExperience: TriState
    targetStageId: string
    actionMode: ActionMode
    triggerWorkflows: boolean
    reason: string
    previewState: PreviewState | null
}
type MassEditStageAction =
    | { type: "reset"; targetStageId: string }
    | { type: "set"; patch: Partial<MassEditStageState> }
    | { type: "addRace"; race: string }
    | { type: "removeRace"; race: string }

function createInitialMassEditStageState(targetStageId = ""): MassEditStageState {
    return {
        statesInput: "",
        createdFrom: "",
        createdTo: "",
        selectedRaces: [],
        raceToAdd: null,
        ageOp: null,
        ageValue: "",
        bmiOp: null,
        bmiValue: "",
        isAgeEligible: "any",
        isCitizenOrPr: "any",
        hasChild: "any",
        isNonSmoker: null,
        hasSurrogateExperience: "any",
        targetStageId,
        actionMode: "change_stage",
        triggerWorkflows: false,
        reason: "",
        previewState: null,
    }
}

function massEditStageReducer(
    state: MassEditStageState,
    action: MassEditStageAction
): MassEditStageState {
    switch (action.type) {
        case "reset":
            return createInitialMassEditStageState(action.targetStageId)
        case "set":
            return { ...state, ...action.patch }
        case "addRace": {
            if (state.selectedRaces.includes(action.race)) {
                return { ...state, raceToAdd: null }
            }
            return {
                ...state,
                selectedRaces: [...state.selectedRaces, action.race],
                raceToAdd: null,
            }
        }
        case "removeRace":
            return {
                ...state,
                selectedRaces: state.selectedRaces.filter((race) => race !== action.race),
            }
    }
}

const UTC_MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

function formatUtcDateLabel(value: string): string {
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
    if (!match) return value

    const monthIndex = Number(match[2]) - 1
    const day = Number(match[3])
    const monthLabel = UTC_MONTH_LABELS[monthIndex]

    if (!monthLabel || !Number.isInteger(day) || day < 1 || day > 31) return value

    return `${monthLabel} ${day}, ${match[1]}`
}

function parseStates(input: string): { states: string[] | undefined; error: string | null } {
    const trimmed = input.trim()
    if (!trimmed) return { states: undefined, error: null }

    const parts: string[] = []
    for (const rawPart of trimmed.split(/[,\s]+/g)) {
        const part = rawPart.trim().toUpperCase()
        if (part) parts.push(part)
    }

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

type BaseFilterBadge = { label: string; value: string }
type MassEditOptionsQuery = ReturnType<typeof useSurrogateMassEditOptions>
type MassEditFilterErrors = {
    statesError: string | null
    createdDateError: string | null
    ageError: string | null
    bmiError: string | null
}
type MassEditStageModalProps = {
    open: boolean
    onOpenChange: (open: boolean) => void
    stages: PipelineStage[]
    baseFilters: SurrogateMassEditStageFilters
}

const TRI_STATE_LABELS: Record<TriState, string> = {
    any: "Any",
    true: "Yes",
    false: "No",
}

function getTriStateLabel(value: string | null | undefined): string {
    if (value === "any" || value === "true" || value === "false") {
        return TRI_STATE_LABELS[value]
    }
    return TRI_STATE_LABELS.any
}

function MassEditBaseFiltersSection({
    baseBadges,
    effectiveCreatedRange,
    hasCreatedOverride,
}: {
    baseBadges: BaseFilterBadge[]
    effectiveCreatedRange: string | null
    hasCreatedOverride: boolean
}) {
    return (
        <div className="space-y-2">
            <div className="text-sm font-medium">Base Filters (from list)</div>
            <div className="flex flex-wrap gap-2">
                {baseBadges.length === 0 ? (
                    <Badge variant="secondary">No base filters</Badge>
                ) : (
                    baseBadges.map((badge) => (
                        <Badge key={badge.label} variant="secondary">
                            {badge.label}: {badge.value}
                        </Badge>
                    ))
                )}
            </div>
            {effectiveCreatedRange || hasCreatedOverride ? (
                <div className="flex flex-wrap gap-2">
                    {effectiveCreatedRange ? (
                        <Badge variant="outline">
                            Effective Created: {effectiveCreatedRange}
                        </Badge>
                    ) : null}
                    {hasCreatedOverride ? (
                        <Badge variant="outline">Created: modal override</Badge>
                    ) : null}
                </div>
            ) : null}
        </div>
    )
}

function RaceFilterField({
    raceToAdd,
    selectedRaces,
    optionsQuery,
    onRaceAdd,
    onRaceRemove,
    onClearRaces,
}: {
    raceToAdd: string | null
    selectedRaces: string[]
    optionsQuery: MassEditOptionsQuery
    onRaceAdd: (race: string) => void
    onRaceRemove: (race: string) => void
    onClearRaces: () => void
}) {
    return (
        <div className="space-y-2">
            <Label>Race</Label>
            <Select
                value={raceToAdd}
                onValueChange={(value) => {
                    if (!value) return
                    onRaceAdd(value)
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
                            <Button unstyled
                                type="button"
                                className="rounded-sm p-0.5 hover:bg-black/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                onClick={() => onRaceRemove(raceKey)}
                                aria-label={`Remove race ${formatRace(raceKey)}`}
                            >
                                <XIcon className="size-3" aria-hidden="true" />
                            </Button>
                        </Badge>
                    ))}
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2"
                        onClick={onClearRaces}
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
    )
}

function ComparisonFilterField({
    label,
    operator,
    value,
    inputMode,
    placeholder,
    error,
    description,
    onOperatorChange,
    onValueChange,
}: {
    label: string
    operator: ComparisonOp | null
    value: string
    inputMode: "numeric" | "decimal"
    placeholder: string
    error: string | null
    description?: string
    onOperatorChange: (operator: ComparisonOp | null) => void
    onValueChange: (value: string) => void
}) {
    return (
        <div className="space-y-2">
            <Label>{label}</Label>
            <div className="grid grid-cols-[96px_1fr] gap-3">
                <Select
                    value={operator}
                    onValueChange={(nextValue) =>
                        onOperatorChange(nextValue ? (nextValue as ComparisonOp) : null)
                    }
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
                    inputMode={inputMode}
                    value={value}
                    onChange={(event) => onValueChange(event.target.value)}
                    placeholder={placeholder}
                />
            </div>
            {error ? (
                <p className="text-xs text-destructive">{error}</p>
            ) : description ? (
                <p className="text-xs text-muted-foreground">{description}</p>
            ) : null}
        </div>
    )
}

function TriStateFilterField({
    label,
    value,
    onValueChange,
    className,
}: {
    label: string
    value: TriState
    onValueChange: (value: TriState) => void
    className?: string
}) {
    return (
        <div className={cn("space-y-2", className)}>
            <Label>{label}</Label>
            <Select
                value={value}
                onValueChange={(nextValue) => onValueChange(nextValue as TriState)}
            >
                <SelectTrigger>
                    <SelectValue>
                        {(selectedValue: string | null) => getTriStateLabel(selectedValue)}
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="any">Any</SelectItem>
                    <SelectItem value="true">Yes</SelectItem>
                    <SelectItem value="false">No</SelectItem>
                </SelectContent>
            </Select>
        </div>
    )
}

function NonSmokerFilterField({
    isNonSmoker,
    onChange,
}: {
    isNonSmoker: boolean | null
    onChange: (value: boolean | null) => void
}) {
    return (
        <div className="space-y-2">
            <Label>Non-Smoker</Label>
            <div className="flex items-center gap-2">
                <Button
                    type="button"
                    variant={isNonSmoker === true ? "secondary" : "outline"}
                    size="sm"
                    onClick={() => onChange(isNonSmoker === true ? null : true)}
                >
                    Non-smoker
                </Button>
                <Button
                    type="button"
                    variant={isNonSmoker === false ? "secondary" : "outline"}
                    size="sm"
                    onClick={() => onChange(isNonSmoker === false ? null : false)}
                >
                    Smoker allowed
                </Button>
                {isNonSmoker !== null ? (
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => onChange(null)}
                    >
                        Clear
                    </Button>
                ) : null}
            </div>
            <p className="text-xs text-muted-foreground">
                Click again to unset.
            </p>
        </div>
    )
}

function MassEditExtraFiltersSection({
    state,
    errors,
    optionsQuery,
    dispatch,
}: {
    state: MassEditStageState
    errors: MassEditFilterErrors
    optionsQuery: MassEditOptionsQuery
    dispatch: React.Dispatch<MassEditStageAction>
}) {
    const {
        statesInput,
        createdFrom,
        createdTo,
        selectedRaces,
        raceToAdd,
        ageOp,
        ageValue,
        bmiOp,
        bmiValue,
        isAgeEligible,
        isCitizenOrPr,
        hasChild,
        isNonSmoker,
        hasSurrogateExperience,
    } = state
    const { statesError, createdDateError, ageError, bmiError } = errors

    return (
        <div className="space-y-3">
            <div className="text-sm font-medium">Extra Filters</div>
            <div className="rounded-md border bg-muted/30 p-3 text-xs space-y-1">
                <div className="font-medium text-foreground">Filter Logic</div>
                <p>
                    Different filter groups combine with <span className="font-semibold">AND</span>.
                </p>
                <p>
                    Multiple values in one field (for example, States or Race) combine with{" "}
                    <span className="font-semibold">OR</span>.
                </p>
                <p>
                    Search matches name, email, phone, or surrogate number with{" "}
                    <span className="font-semibold">OR</span>.
                </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                    <Label htmlFor="mass-states">States (comma or space separated)</Label>
                    <Input
                        id="mass-states"
                        value={statesInput}
                        onChange={(event) =>
                            dispatch({ type: "set", patch: { statesInput: event.target.value } })
                        }
                        placeholder="CA, TX, FL"
                    />
                    {statesError ? (
                        <p className="text-xs text-destructive">{statesError}</p>
                    ) : null}
                </div>

                <div className="space-y-2">
                    <Label htmlFor="mass-created-from">Created From</Label>
                    <Input
                        id="mass-created-from"
                        type="date"
                        value={createdFrom}
                        onChange={(event) =>
                            dispatch({ type: "set", patch: { createdFrom: event.target.value } })
                        }
                    />
                </div>

                <div className="space-y-2">
                    <Label htmlFor="mass-created-to">Created To</Label>
                    <Input
                        id="mass-created-to"
                        type="date"
                        value={createdTo}
                        onChange={(event) =>
                            dispatch({ type: "set", patch: { createdTo: event.target.value } })
                        }
                    />
                    {createdDateError ? (
                        <p className="text-xs text-destructive">{createdDateError}</p>
                    ) : (
                        <p className="text-xs text-muted-foreground">
                            When set here, this overrides the Surrogates page date filter.
                        </p>
                    )}
                </div>

                <RaceFilterField
                    raceToAdd={raceToAdd}
                    selectedRaces={selectedRaces}
                    optionsQuery={optionsQuery}
                    onRaceAdd={(race) => dispatch({ type: "addRace", race })}
                    onRaceRemove={(race) => dispatch({ type: "removeRace", race })}
                    onClearRaces={() => dispatch({ type: "set", patch: { selectedRaces: [] } })}
                />

                <ComparisonFilterField
                    label="Age"
                    operator={ageOp}
                    value={ageValue}
                    inputMode="numeric"
                    placeholder="e.g. 36"
                    error={ageError}
                    onOperatorChange={(nextOperator) =>
                        dispatch({ type: "set", patch: { ageOp: nextOperator } })
                    }
                    onValueChange={(value) => dispatch({ type: "set", patch: { ageValue: value } })}
                />

                <ComparisonFilterField
                    label="BMI"
                    operator={bmiOp}
                    value={bmiValue}
                    inputMode="decimal"
                    placeholder="e.g. 32"
                    error={bmiError}
                    description="Note: BMI is computed from height/weight; “=” matches roughly the 1-decimal BMI shown in the UI."
                    onOperatorChange={(nextOperator) =>
                        dispatch({ type: "set", patch: { bmiOp: nextOperator } })
                    }
                    onValueChange={(value) => dispatch({ type: "set", patch: { bmiValue: value } })}
                />

                <TriStateFilterField
                    label="Age Eligible"
                    value={isAgeEligible}
                    onValueChange={(value) =>
                        dispatch({ type: "set", patch: { isAgeEligible: value } })
                    }
                />

                <TriStateFilterField
                    label="US Citizen or PR"
                    value={isCitizenOrPr}
                    onValueChange={(value) =>
                        dispatch({ type: "set", patch: { isCitizenOrPr: value } })
                    }
                />

                <TriStateFilterField
                    label="Has Child"
                    value={hasChild}
                    onValueChange={(value) => dispatch({ type: "set", patch: { hasChild: value } })}
                />

                <NonSmokerFilterField
                    isNonSmoker={isNonSmoker}
                    onChange={(value) => dispatch({ type: "set", patch: { isNonSmoker: value } })}
                />

                <TriStateFilterField
                    label="Prior Surrogate Experience"
                    value={hasSurrogateExperience}
                    onValueChange={(value) =>
                        dispatch({ type: "set", patch: { hasSurrogateExperience: value } })
                    }
                    className="sm:col-span-2"
                />
            </div>
        </div>
    )
}

function MassEditActionSection({
    state,
    activeStages,
    selectedStage,
    dispatch,
}: {
    state: MassEditStageState
    activeStages: PipelineStage[]
    selectedStage: PipelineStage | undefined
    dispatch: React.Dispatch<MassEditStageAction>
}) {
    const { actionMode, targetStageId, triggerWorkflows, reason } = state

    return (
        <div className="space-y-3">
            <div className="text-sm font-medium">Action</div>
            <div className="flex flex-wrap gap-2">
                <Button
                    type="button"
                    variant={actionMode === "change_stage" ? "secondary" : "outline"}
                    size="sm"
                    onClick={() => dispatch({ type: "set", patch: { actionMode: "change_stage" } })}
                >
                    Change Stage
                </Button>
                <Button
                    type="button"
                    variant={actionMode === "archive" ? "secondary" : "outline"}
                    size="sm"
                    onClick={() => dispatch({ type: "set", patch: { actionMode: "archive" } })}
                >
                    Archive
                </Button>
            </div>

            {actionMode === "change_stage" ? (
                <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                        <Label>New Stage</Label>
                        <Select
                            value={targetStageId}
                            onValueChange={(value) =>
                                dispatch({ type: "set", patch: { targetStageId: value ?? "" } })
                            }
                        >
                            <SelectTrigger>
                                <SelectValue placeholder="Select a stage">
                                    {(value: string | null) => {
                                        if (!value) return "Select a stage"
                                        const stage = activeStages.find((item) => item.id === value)
                                        return stage?.label ?? "Unknown stage"
                                    }}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                {activeStages.map((stage) => (
                                    <SelectItem key={stage.id} value={stage.id}>
                                        {stage.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        {selectedStage ? (
                            <p className="text-xs text-muted-foreground">
                                Target: <span className="font-medium">{selectedStage.label}</span>
                            </p>
                        ) : null}
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
                            <Switch
                                checked={triggerWorkflows}
                                onCheckedChange={(checked) =>
                                    dispatch({ type: "set", patch: { triggerWorkflows: checked } })
                                }
                            />
                        </div>
                    </div>
                </div>
            ) : (
                <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-700">
                    Archive action will soft-archive all matched surrogates.
                </div>
            )}

            <div className="space-y-2">
                <Label htmlFor="mass-reason">Reason (optional)</Label>
                <Textarea
                    id="mass-reason"
                    value={reason}
                    onChange={(event) =>
                        dispatch({ type: "set", patch: { reason: event.target.value } })
                    }
                    placeholder={
                        actionMode === "archive"
                            ? "e.g. Bulk archive dormant leads"
                            : "e.g. Bulk disqualify based on eligibility checklist"
                    }
                    rows={2}
                />
            </div>
        </div>
    )
}

function MassEditPreviewSection({
    preview,
    actionMode,
    selectedStage,
    canPreview,
    previewPending,
    isApplying,
    onPreview,
}: {
    preview: SurrogateMassEditStagePreviewResponse | null
    actionMode: ActionMode
    selectedStage: PipelineStage | undefined
    canPreview: boolean
    previewPending: boolean
    isApplying: boolean
    onPreview: () => void
}) {
    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-medium">Preview</div>
                <Button
                    variant="outline"
                    onClick={onPreview}
                    disabled={!canPreview || previewPending || isApplying}
                >
                    {previewPending ? <Loader2Icon className="mr-2 size-4 animate-spin" /> : null}
                    Preview Matches
                </Button>
            </div>

            {preview ? (
                <div
                    className={cn(
                        "rounded-lg border p-3",
                        preview.over_limit && "border-amber-500/50 bg-amber-500/5",
                    )}
                >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="text-sm">
                            <span className="font-medium">{preview.total.toLocaleString()}</span>{" "}
                            match{preview.total === 1 ? "" : "es"}
                            {actionMode === "archive" ? (
                                <> will be archived</>
                            ) : selectedStage ? (
                                <>
                                    {" "}
                                    will be moved to{" "}
                                    <span className="font-medium">{selectedStage.label}</span>
                                </>
                            ) : null}
                        </div>
                        {preview.over_limit ? (
                            <div className="inline-flex items-center gap-2 text-xs text-amber-700">
                                <TriangleAlertIcon className="size-4" />
                                Too many matches (max {preview.max_apply.toLocaleString()}). Narrow filters.
                            </div>
                        ) : null}
                    </div>

                    {preview.items.length > 0 ? (
                        <div className="mt-3">
                            <div className="text-xs text-muted-foreground mb-2">Sample</div>
                            <ScrollArea className="h-44 rounded-md border">
                                <div className="divide-y">
                                    {preview.items.map((item) => (
                                        <div
                                            key={item.id}
                                            className="px-3 py-2 text-sm flex items-center justify-between gap-3"
                                        >
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
                                                {formatUtcDateLabel(item.created_at)}
                                            </Badge>
                                        </div>
                                    ))}
                                </div>
                            </ScrollArea>
                        </div>
                    ) : null}
                </div>
            ) : null}
        </div>
    )
}

function MassEditFooter({
    preview,
    actionMode,
    isApplying,
    canApply,
    onCancel,
    onApply,
}: {
    preview: SurrogateMassEditStagePreviewResponse | null
    actionMode: ActionMode
    isApplying: boolean
    canApply: boolean
    onCancel: () => void
    onApply: () => void
}) {
    return (
        <div className="space-y-3">
            <DialogFooter className="gap-2 sm:gap-2">
                <Button
                    variant="outline"
                    onClick={onCancel}
                    disabled={isApplying}
                >
                    Cancel
                </Button>
                <Button
                    onClick={onApply}
                    disabled={!canApply}
                    className={cn(preview?.over_limit && "opacity-50")}
                >
                    {isApplying ? <Loader2Icon className="mr-2 size-4 animate-spin" /> : null}
                    {actionMode === "archive" ? "Apply Archive" : "Apply Stage Change"}
                </Button>
            </DialogFooter>

            {!preview ? (
                <div className="text-xs text-muted-foreground flex items-center gap-2">
                    <TriangleAlertIcon className="size-4" />
                    Always preview first. Apply requires the preview count (prevents accidental wide updates).
                </div>
            ) : null}
        </div>
    )
}

function useMassEditStageModel({
    open,
    onOpenChange,
    stages,
    baseFilters,
}: MassEditStageModalProps) {
    const previewMutation = usePreviewSurrogateMassEditStage()
    const applyStageMutation = useApplySurrogateMassEditStage()
    const applyArchiveMutation = useApplySurrogateMassEditArchive()
    const optionsQuery = useSurrogateMassEditOptions({ enabled: open })

    const [state, dispatch] = React.useReducer(
        massEditStageReducer,
        "",
        createInitialMassEditStageState
    )
    const {
        statesInput,
        createdFrom,
        createdTo,
        selectedRaces,
        ageOp,
        ageValue,
        bmiOp,
        bmiValue,
        isAgeEligible,
        isCitizenOrPr,
        hasChild,
        isNonSmoker,
        hasSurrogateExperience,
        targetStageId,
        actionMode,
        triggerWorkflows,
        reason,
        previewState,
    } = state

    const activeStages = stages.filter((s) => s.is_active).toSorted((a, b) => a.order - b.order)
    const defaultTargetStageId = activeStages.find((s) => s.slug === "disqualified")?.id ?? ""
    const hasInitializedOpenRef = React.useRef(false)

    // Reset only once per open cycle.
    React.useEffect(() => {
        if (!open) {
            hasInitializedOpenRef.current = false
            return
        }
        if (hasInitializedOpenRef.current) return

        hasInitializedOpenRef.current = true
        dispatch({ type: "reset", targetStageId: defaultTargetStageId })
    }, [open, defaultTargetStageId])

    // If stages load after opening, apply the default only while no stage is selected.
    React.useEffect(() => {
        if (!open || targetStageId || !defaultTargetStageId) return
        dispatch({ type: "set", patch: { targetStageId: defaultTargetStageId } })
    }, [open, targetStageId, defaultTargetStageId])

    const { states, error: statesError } = parseStates(statesInput)
    const races = selectedRaces.length ? selectedRaces : undefined
    const createdDateError = (() => {
        if (!createdFrom || !createdTo) return null
        if (createdFrom <= createdTo) return null
        return "Created From must be on or before Created To."
    })()

    const { age_min, age_max, ageError } = (() => {
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
    })()

    const { bmi_min, bmi_max, bmiError } = (() => {
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
    })()

    const derivedFilters: SurrogateMassEditStageFilters = (() => {
        const is_age_eligible = triStateToBool(isAgeEligible)
        const is_citizen_or_pr = triStateToBool(isCitizenOrPr)
        const has_child = triStateToBool(hasChild)
        const is_non_smoker = isNonSmoker === null ? undefined : isNonSmoker
        const has_surrogate_experience = triStateToBool(hasSurrogateExperience)

        return {
            ...(createdFrom ? { created_from: createdFrom } : {}),
            ...(createdTo ? { created_to: createdTo } : {}),
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
    })()

    const mergedFilters: SurrogateMassEditStageFilters = (() => {
        const merged: SurrogateMassEditStageFilters = { ...baseFilters, ...derivedFilters }
        const hasModalCreatedOverride = Boolean(createdFrom || createdTo)

        if (!hasModalCreatedOverride) return merged

        const withoutCreated: SurrogateMassEditStageFilters = { ...merged }
        delete withoutCreated.created_from
        delete withoutCreated.created_to
        return {
            ...withoutCreated,
            ...(createdFrom ? { created_from: createdFrom } : {}),
            ...(createdTo ? { created_to: createdTo } : {}),
        }
    })()
    const previewSignature = JSON.stringify({
        filters: mergedFilters,
        targetStageId,
        actionMode,
        triggerWorkflows,
        reason,
    })
    const preview =
        previewState?.signature === previewSignature ? previewState.result : null

    const hasCreatedOverride = Boolean((baseFilters.created_from || baseFilters.created_to) && (createdFrom || createdTo))
    const effectiveCreatedRange = (() => {
        if (!mergedFilters.created_from && !mergedFilters.created_to) return null
        return `${mergedFilters.created_from ?? "…"} to ${mergedFilters.created_to ?? "…"}`
    })()

    const selectedStage = activeStages.find((s) => s.id === targetStageId)

    const isApplying = applyStageMutation.isPending || applyArchiveMutation.isPending
    const canPreview = !statesError && !ageError && !bmiError && !createdDateError
    const canApply =
        !!preview &&
        !preview.over_limit &&
        !isApplying &&
        (actionMode === "archive" || !!targetStageId)

    const handlePreview = async () => {
        if (!canPreview) return
        try {
            const result = await previewMutation.mutateAsync({ data: { filters: mergedFilters }, limit: 25 })
            dispatch({ type: "set", patch: { previewState: { result, signature: previewSignature } } })
            if (result.total === 0) toast.info("No surrogates matched those filters.")
        } catch (err) {
            const message = err instanceof Error ? err.message : "Preview failed"
            toast.error(message)
        }
    }

    const handleApply = async () => {
        if (!preview) return
        try {
            if (actionMode === "archive") {
                const result = await applyArchiveMutation.mutateAsync({
                    filters: mergedFilters,
                    expected_total: preview.total,
                    ...(reason.trim() ? { reason: reason.trim() } : {}),
                })

                if (result.failed?.length) {
                    toast.error(`Archived ${result.archived}/${result.matched}. ${result.failed.length} failed.`)
                } else {
                    toast.success(`Archived ${result.archived} surrogate${result.archived === 1 ? "" : "s"}.`)
                }
            } else {
                if (!targetStageId) return

                const result = await applyStageMutation.mutateAsync({
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
            label: "Created (list)",
            value: `${baseFilters.created_from ?? "…"} to ${baseFilters.created_to ?? "…"}`
        })
    }

    return {
        state,
        dispatch,
        optionsQuery,
        activeStages,
        selectedStage,
        baseBadges,
        effectiveCreatedRange,
        hasCreatedOverride,
        errors: {
            statesError,
            createdDateError,
            ageError,
            bmiError,
        },
        preview,
        isApplying,
        canPreview,
        canApply,
        previewPending: previewMutation.isPending,
        handlePreview,
        handleApply,
    }
}

export function MassEditStageModal(props: MassEditStageModalProps) {
    const { open, onOpenChange } = props
    const {
        state,
        dispatch,
        optionsQuery,
        activeStages,
        selectedStage,
        baseBadges,
        effectiveCreatedRange,
        hasCreatedOverride,
        errors,
        preview,
        isApplying,
        canPreview,
        canApply,
        previewPending,
        handlePreview,
        handleApply,
    } = useMassEditStageModel(props)

    return (
        <Dialog open={open} onOpenChange={(next) => !isApplying && onOpenChange(next)}>
            <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
                <DialogHeader className="pr-10">
                    <DialogTitle className="flex items-center gap-2">
                        <SparklesIcon className="size-5" />
                        Mass Edit
                    </DialogTitle>
                    <DialogDescription>
                        Dev-only tool. Applies to all surrogates matching your current list filters plus any extra filters below.
                    </DialogDescription>
                </DialogHeader>

                <div className="min-h-0 flex-1 overflow-y-auto pr-1">
                    <div className="space-y-5">
                        <MassEditBaseFiltersSection
                            baseBadges={baseBadges}
                            effectiveCreatedRange={effectiveCreatedRange}
                            hasCreatedOverride={hasCreatedOverride}
                        />

                        <Separator />

                        <MassEditExtraFiltersSection
                            state={state}
                            errors={errors}
                            optionsQuery={optionsQuery}
                            dispatch={dispatch}
                        />

                        <Separator />

                        <MassEditActionSection
                            state={state}
                            activeStages={activeStages}
                            selectedStage={selectedStage}
                            dispatch={dispatch}
                        />

                        <Separator />

                        <MassEditPreviewSection
                            preview={preview}
                            actionMode={state.actionMode}
                            selectedStage={selectedStage}
                            canPreview={canPreview}
                            previewPending={previewPending}
                            isApplying={isApplying}
                            onPreview={() => void handlePreview()}
                        />
                    </div>
                </div>

                <MassEditFooter
                    preview={preview}
                    actionMode={state.actionMode}
                    isApplying={isApplying}
                    canApply={canApply}
                    onCancel={() => onOpenChange(false)}
                    onApply={() => void handleApply()}
                />
            </DialogContent>
        </Dialog>
    )
}
