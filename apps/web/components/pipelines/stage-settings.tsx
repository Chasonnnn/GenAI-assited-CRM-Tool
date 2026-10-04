"use client"

import { useCallback, useState } from "react"
import type * as React from "react"
import { ArrowDownIcon, ArrowRightIcon, ArrowUpIcon, LockIcon } from "lucide-react"

import { PipelineSelectField } from "@/components/pipelines/pipeline-select-field"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import type {
    PipelineEntityType,
    PipelineFeatureConfig,
    PipelineStageDependency,
    StageSemantics,
    StageType,
} from "@/lib/api/pipelines"
import { CUSTOM_STAGE_COLOR_PRESETS } from "@/lib/pipeline-stage-colors"
import {
    buildPresetSemantics,
    createMilestoneLabelGetter,
    getBehaviorPreset,
    getEntityRecordLabel,
    getPresetOptions,
    getStageCategoryOptions,
    getStageMilestoneSlugs,
    getVisibleCapabilityLabels,
    isUuidLike,
    normalizeIdentifier,
    RESERVED_CAPABILITY_KEYS,
    STAGE_LABEL_MAX_LENGTH,
    STAGE_SLUG_MAX_LENGTH,
    SUGGESTION_PROFILE_OPTIONS,
    withAutoStageColor,
    type BehaviorPreset,
    type EditableStage,
    type PipelineSelectOption,
    type StageFieldErrors,
} from "@/lib/pipelines/stage-editor"
import { humanizeSelectKey } from "@/lib/select-labels"
import { stageDisplayColor } from "@/lib/stage-colors"
import { cn } from "@/lib/utils"

export type StageChangeHandler = (updater: (stage: EditableStage) => EditableStage) => void

const FIELD_LABEL_CLASS = "text-muted-foreground flex items-center gap-1 text-xs font-medium"
const HEX_COLOR = /^#?[0-9a-f]{6}$/i

const INTEGRATION_BUCKET_OPTIONS: PipelineSelectOption[] = [
    { value: "none", label: "Not tracked" },
    { value: "intake", label: "Intake" },
    { value: "qualified", label: "Qualified" },
    { value: "converted", label: "Converted" },
    { value: "lost", label: "Lost" },
    { value: "not_qualified", label: "Not qualified" },
]
const PAUSE_BEHAVIOR_OPTIONS: PipelineSelectOption[] = [
    { value: "none", label: "None" },
    { value: "resume_previous_stage", label: "Resume previous stage" },
]
const TERMINAL_OUTCOME_OPTIONS: PipelineSelectOption[] = [
    { value: "none", label: "None" },
    { value: "lost", label: "Lost" },
    { value: "disqualified", label: "Disqualified" },
]
const SUGGESTION_PROFILE_SELECT_OPTIONS: PipelineSelectOption[] = SUGGESTION_PROFILE_OPTIONS.map((option) => ({
    value: option,
    label: option ? humanizeSelectKey(option) ?? "Unknown profile" : "None",
}))

function FieldLock() {
    return <LockIcon className="size-3" aria-hidden="true" />
}

/** Stage color as it displays everywhere (stageDisplayColor), as a small rounded swatch. `raw` skips darkening. */
export function StageSwatch({ color, raw = false, className }: { color: string; raw?: boolean; className?: string }) {
    return (
        <span
            aria-hidden="true"
            data-slot="stage-swatch"
            className={cn("inline-block size-4 shrink-0 rounded-[4px] ring-1 ring-inset ring-foreground/10", className)}
            style={{ backgroundColor: raw ? color : stageDisplayColor(color) }}
        />
    )
}

function SettingsSection({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <section className="flex flex-col gap-3 border-t py-4 first:border-t-0 first:pt-1">
            <h3 className="text-[13px] font-semibold">{title}</h3>
            {children}
        </section>
    )
}

/**
 * The swatch, hex field and presets all show the displayed color, and every pick saves it:
 * picking #FDE68A stores #8B7506. The native picker keeps the raw pick while open so it does
 * not jump under the pointer.
 */
function StageColorField({
    id,
    stage,
    onStageChange,
}: {
    id: string
    stage: EditableStage
    onStageChange: StageChangeHandler
}) {
    const [pickerValue, setPickerValue] = useState<string | null>(null)
    const [hexDraft, setHexDraft] = useState<string | null>(null)
    const [adjustedPick, setAdjustedPick] = useState<{ picked: string; saved: string } | null>(null)
    const displayColor = stageDisplayColor(stage.color)
    const presets = CUSTOM_STAGE_COLOR_PRESETS[stage.category] ?? []
    const disabled = Boolean(stage.is_locked)
    const hexInvalid = hexDraft !== null && hexDraft.trim() !== "" && !HEX_COLOR.test(hexDraft.trim())

    const saveColor = (color: string) => {
        const saved = stageDisplayColor(color)
        const picked = color.toUpperCase()
        setAdjustedPick(saved === picked ? null : { picked, saved })
        onStageChange((current) => ({ ...current, color: saved }))
    }
    // Shown until the color changes another way, so the user sees why the saved color differs.
    const visibleAdjustment = adjustedPick && adjustedPick.saved === displayColor ? adjustedPick : null

    const commitHexDraft = () => {
        if (hexDraft === null) return
        const candidate = hexDraft.trim()
        if (HEX_COLOR.test(candidate)) {
            saveColor(candidate.startsWith("#") ? candidate : `#${candidate}`)
        }
        setHexDraft(null)
    }

    return (
        <div className="flex flex-wrap items-center gap-2">
            <span
                className={cn(
                    "relative size-8 shrink-0 overflow-hidden rounded-md ring-1 ring-inset ring-foreground/10 focus-within:ring-[3px] focus-within:ring-ring/50",
                    disabled && "opacity-50",
                )}
                style={{ backgroundColor: displayColor }}
            >
                <input
                    id={id}
                    type="color"
                    value={(pickerValue ?? displayColor).toLowerCase()}
                    disabled={disabled}
                    onChange={(event) => {
                        setPickerValue(event.target.value)
                        saveColor(event.target.value)
                    }}
                    onBlur={() => setPickerValue(null)}
                    aria-label={`${stage.label || "Stage"} color`}
                    className="absolute inset-0 size-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
                />
            </span>
            <Input
                value={hexDraft ?? displayColor}
                disabled={disabled}
                maxLength={7}
                spellCheck={false}
                aria-label={`${stage.label || "Stage"} color hex`}
                aria-invalid={hexInvalid ? true : undefined}
                onChange={(event) => setHexDraft(event.target.value)}
                onBlur={commitHexDraft}
                onKeyDown={(event) => {
                    if (event.key === "Enter") {
                        event.preventDefault()
                        commitHexDraft()
                    }
                    if (event.key === "Escape" && hexDraft !== null) {
                        event.stopPropagation()
                        setHexDraft(null)
                    }
                }}
                className="h-8 w-24 font-mono text-xs uppercase"
            />
            {disabled ? null : (
                <div className="flex flex-wrap items-center gap-1" role="group" aria-label="Preset colors">
                    {presets.map((preset) => (
                        <Button
                            key={preset}
                            unstyled
                            type="button"
                            aria-label={`Use ${preset}`}
                            aria-pressed={preset === displayColor}
                            onClick={() => saveColor(preset)}
                            className="size-5 rounded-full ring-1 ring-inset ring-foreground/10 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 aria-pressed:ring-2 aria-pressed:ring-ring aria-pressed:ring-offset-2 aria-pressed:ring-offset-background"
                            style={{ backgroundColor: preset }}
                        />
                    ))}
                </div>
            )}
            {visibleAdjustment ? (
                <p className="text-muted-foreground flex basis-full items-center gap-1.5 text-xs" aria-live="polite">
                    Picked
                    <StageSwatch color={visibleAdjustment.picked} raw />
                    <span className="font-mono">{visibleAdjustment.picked}</span>
                    <ArrowRightIcon className="size-3" aria-hidden="true" />
                    Saved
                    <StageSwatch color={visibleAdjustment.saved} raw />
                    <span className="text-foreground font-mono">{visibleAdjustment.saved}</span>
                </p>
            ) : null}
        </div>
    )
}

function StagePositionField({
    stage,
    index,
    total,
    onMove,
}: {
    stage: EditableStage
    index: number
    total: number
    onMove: (delta: -1 | 1) => void
}) {
    return (
        <div className="flex items-center gap-2">
            <span className="border-input bg-muted/50 text-muted-foreground flex h-8 min-w-20 items-center rounded-md border px-2.5 text-sm tabular-nums">
                {index + 1} of {total}
            </span>
            {stage.is_locked ? null : (
                <>
                    <Button
                        type="button"
                        variant="outline"
                        size="icon-sm"
                        disabled={index === 0}
                        onClick={() => onMove(-1)}
                        aria-label={`Move ${stage.label} up`}
                    >
                        <ArrowUpIcon aria-hidden="true" />
                    </Button>
                    <Button
                        type="button"
                        variant="outline"
                        size="icon-sm"
                        disabled={index >= total - 1}
                        onClick={() => onMove(1)}
                        aria-label={`Move ${stage.label} down`}
                    >
                        <ArrowDownIcon aria-hidden="true" />
                    </Button>
                </>
            )}
        </div>
    )
}

function StageSemanticsFields({
    idPrefix,
    entityType,
    stage,
    onStageChange,
}: {
    idPrefix: string
    entityType: PipelineEntityType
    stage: EditableStage
    onStageChange: StageChangeHandler
}) {
    const updateSemantics = (updater: (semantics: StageSemantics) => StageSemantics) => {
        onStageChange((current) => ({
            ...current,
            semantics: updater(current.semantics),
        }))
    }
    const locked = Boolean(stage.is_locked)

    return (
        <div className="grid grid-cols-2 gap-3">
            <PipelineSelectField
                id={`${idPrefix}-behavior-preset-${stage.id}`}
                label="Behavior preset"
                ariaLabel={`Behavior preset for ${stage.label}`}
                value={getBehaviorPreset(stage, entityType)}
                options={getPresetOptions(stage, entityType)}
                disabled={locked}
                onValueChange={(value) => {
                    const preset = value as BehaviorPreset
                    onStageChange((current) => ({
                        ...current,
                        semantics: buildPresetSemantics(current, preset, entityType),
                    }))
                }}
            />
            {entityType === "surrogate" ? (
                <PipelineSelectField
                    id={`${idPrefix}-integration-bucket-${stage.id}`}
                    label="Integration bucket"
                    ariaLabel={`Integration bucket for ${stage.label}`}
                    value={stage.semantics.integration_bucket}
                    options={INTEGRATION_BUCKET_OPTIONS}
                    disabled={locked}
                    onValueChange={(value) =>
                        updateSemantics((semantics) => ({
                            ...semantics,
                            integration_bucket: value as StageSemantics["integration_bucket"],
                        }))
                    }
                />
            ) : null}
            {entityType === "intended_parent" ? null : (
                <PipelineSelectField
                    id={`${idPrefix}-pause-behavior-${stage.id}`}
                    label="Pause behavior"
                    ariaLabel={`Pause behavior for ${stage.label}`}
                    value={stage.semantics.pause_behavior}
                    options={PAUSE_BEHAVIOR_OPTIONS}
                    disabled
                    labelAddon={<FieldLock />}
                    onValueChange={(value) =>
                        updateSemantics((semantics) => ({
                            ...semantics,
                            pause_behavior: value as StageSemantics["pause_behavior"],
                        }))
                    }
                />
            )}
            <PipelineSelectField
                id={`${idPrefix}-terminal-outcome-${stage.id}`}
                label="Terminal outcome"
                ariaLabel={`Terminal outcome for ${stage.label}`}
                value={stage.semantics.terminal_outcome}
                options={TERMINAL_OUTCOME_OPTIONS}
                disabled
                labelAddon={<FieldLock />}
                onValueChange={(value) =>
                    updateSemantics((semantics) => ({
                        ...semantics,
                        terminal_outcome: value as StageSemantics["terminal_outcome"],
                    }))
                }
            />
            {entityType === "surrogate" ? (
                <>
                    <PipelineSelectField
                        id={`${idPrefix}-suggestion-profile-${stage.id}`}
                        label="Suggestion profile"
                        ariaLabel={`Suggestion profile for ${stage.label}`}
                        value={stage.semantics.suggestion_profile_key}
                        options={SUGGESTION_PROFILE_SELECT_OPTIONS}
                        disabled={locked}
                        onValueChange={(value) =>
                            updateSemantics((semantics) => ({
                                ...semantics,
                                suggestion_profile_key: value || null,
                            }))
                        }
                    />
                    <div className="min-w-0 space-y-1.5">
                        <Label htmlFor={`${idPrefix}-analytics-bucket-${stage.id}`} className={FIELD_LABEL_CLASS}>
                            Analytics bucket
                        </Label>
                        <Input
                            id={`${idPrefix}-analytics-bucket-${stage.id}`}
                            value={stage.semantics.analytics_bucket ?? ""}
                            disabled={locked}
                            onChange={(event) =>
                                updateSemantics((semantics) => ({
                                    ...semantics,
                                    analytics_bucket: event.target.value.trim() || null,
                                }))
                            }
                            placeholder="analytics bucket"
                            className="h-8 font-mono text-xs"
                            aria-label={`Analytics bucket for ${stage.label}`}
                        />
                    </div>
                </>
            ) : null}
        </div>
    )
}

function StageRulesEditor({
    entityType,
    stage,
    onStageChange,
}: {
    entityType: PipelineEntityType
    stage: EditableStage
    onStageChange: StageChangeHandler
}) {
    const updateSemantics = (updater: (semantics: StageSemantics) => StageSemantics) => {
        onStageChange((current) => ({
            ...current,
            semantics: updater(current.semantics),
        }))
    }

    return (
        <div className="grid grid-cols-1 gap-x-3 gap-y-2.5 sm:grid-cols-2">
            {getVisibleCapabilityLabels(entityType).map((capability) => {
                const reserved = RESERVED_CAPABILITY_KEYS.has(capability.key)
                const disabled = Boolean(stage.is_locked) || reserved
                return (
                    <label
                        key={capability.key}
                        className={cn("flex min-w-0 items-center gap-2 text-[13px]", disabled && "text-muted-foreground")}
                    >
                        <Checkbox
                            checked={stage.semantics.capabilities[capability.key]}
                            disabled={disabled}
                            onCheckedChange={(checked) =>
                                updateSemantics((semantics) => ({
                                    ...semantics,
                                    capabilities: {
                                        ...semantics.capabilities,
                                        [capability.key]: checked,
                                    },
                                }))
                            }
                        />
                        <span className="truncate">{capability.label}</span>
                        {reserved ? <LockIcon className="size-3 shrink-0" aria-hidden="true" /> : null}
                    </label>
                )
            })}
            <label
                className={cn("flex min-w-0 items-center gap-2 text-[13px]", stage.is_locked && "text-muted-foreground")}
            >
                <Checkbox
                    checked={stage.semantics.requires_reason_on_enter}
                    disabled={Boolean(stage.is_locked)}
                    onCheckedChange={(checked) =>
                        updateSemantics((semantics) => ({
                            ...semantics,
                            requires_reason_on_enter: checked,
                        }))
                    }
                />
                <span className="truncate">Require reason on enter</span>
            </label>
        </div>
    )
}

function StageJourneyFields({
    idPrefix,
    stage,
    featureConfig,
    onMilestonesChange,
    onFunnelChange,
}: {
    idPrefix: string
    stage: EditableStage
    featureConfig: PipelineFeatureConfig
    onMilestonesChange: (milestoneSlugs: string[]) => void
    onFunnelChange: (included: boolean) => void
}) {
    const milestoneSlugs = getStageMilestoneSlugs(featureConfig, stage.stage_key)
    const getMilestoneLabel = createMilestoneLabelGetter(featureConfig)
    const milestoneSummary = milestoneSlugs.length > 0
        ? milestoneSlugs.map((slug) => getMilestoneLabel(slug)).join(", ")
        : getMilestoneLabel(null)
    const inFunnel = featureConfig.analytics.funnel_stage_keys.includes(stage.stage_key)
    const milestonesId = `${idPrefix}-journey-milestones-${stage.id}`
    const funnelId = `${idPrefix}-analytics-funnel-${stage.id}`

    return (
        <div className="grid grid-cols-2 gap-3">
            <div className="min-w-0 space-y-1.5">
                <Label htmlFor={milestonesId} className={FIELD_LABEL_CLASS}>
                    Journey milestones
                </Label>
                <Select<string, true>
                    multiple
                    value={milestoneSlugs}
                    onValueChange={(next) => onMilestonesChange(next)}
                >
                    <SelectTrigger
                        id={milestonesId}
                        size="sm"
                        aria-label={`Journey milestones for ${stage.label}`}
                        className="w-full"
                    >
                        <SelectValue className={cn("truncate", milestoneSlugs.length === 0 && "text-muted-foreground")}>
                            {() => milestoneSummary}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent className="min-w-56">
                        {featureConfig.journey.milestones.map((milestone) => (
                            <SelectItem key={milestone.slug} value={milestone.slug}>
                                {getMilestoneLabel(milestone.slug)}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>
            <div className="min-w-0 space-y-1.5">
                <Label htmlFor={funnelId} className={FIELD_LABEL_CLASS}>
                    Analytics funnel
                </Label>
                <div className="flex h-8 items-center gap-2 text-sm">
                    <Switch
                        id={funnelId}
                        checked={inFunnel}
                        disabled={!stage.is_active}
                        onCheckedChange={(checked) => onFunnelChange(checked)}
                    />
                    <span>{inFunnel ? "Included" : "Not included"}</span>
                </div>
            </div>
        </div>
    )
}

function StageUsageBadges({
    entityType,
    dependency,
    featureConfig,
}: {
    entityType: PipelineEntityType
    dependency: PipelineStageDependency | undefined
    featureConfig: PipelineFeatureConfig | undefined
}) {
    if (!dependency) return <p className="text-muted-foreground text-sm">None</p>
    const getMilestoneLabel = featureConfig ? createMilestoneLabelGetter(featureConfig) : null
    const milestoneLabels = dependency.journey_milestone_slugs.map((slug) => {
        const label = getMilestoneLabel?.(slug)
        return label && label !== "Unknown milestone" ? label : humanizeSelectKey(slug) ?? slug
    })

    return (
        <div className="flex flex-wrap gap-1.5">
            <Badge variant="outline">{getEntityRecordLabel(entityType, dependency.surrogate_count)}</Badge>
            {entityType === "surrogate" && milestoneLabels.length > 0 ? (
                <Badge variant="outline">Journey: {milestoneLabels.join(", ")}</Badge>
            ) : null}
            {entityType === "surrogate" && dependency.analytics_funnel ? (
                <Badge variant="outline">Analytics funnel</Badge>
            ) : null}
            {entityType === "surrogate" && dependency.integration_refs.length > 0 ? (
                <Badge variant="outline">Integrations: {dependency.integration_refs.join(", ")}</Badge>
            ) : null}
            {dependency.campaign_refs.length > 0 ? (
                <Badge variant="outline">Campaigns: {dependency.campaign_refs.length}</Badge>
            ) : null}
            {dependency.workflow_refs.length > 0 ? (
                <Badge variant="outline">Workflows: {dependency.workflow_refs.length}</Badge>
            ) : null}
        </div>
    )
}

/** Inline label/slug error, wired to the input through aria-describedby. */
export function StageFieldError({ id, message }: { id: string; message: string | undefined }) {
    if (!message) return null
    return (
        <p id={id} className="text-destructive text-xs">
            {message}
        </p>
    )
}

/**
 * Every stage setting, grouped as in the stage drawer and the phone stage page:
 * stage, behavior, rules, journey and funnel (surrogates only), used by.
 */
export function StageSettingsFields({
    idPrefix,
    entityType,
    stage,
    index,
    total,
    errors,
    dependency,
    featureConfig,
    showSurrogateEditors,
    onStageChange,
    onMove,
    onMilestonesChange,
    onFunnelChange,
    autoFocusLabel = false,
}: {
    idPrefix: string
    entityType: PipelineEntityType
    stage: EditableStage
    index: number
    total: number
    errors: StageFieldErrors | undefined
    dependency: PipelineStageDependency | undefined
    featureConfig: PipelineFeatureConfig | undefined
    showSurrogateEditors: boolean
    onStageChange: StageChangeHandler
    onMove: (delta: -1 | 1) => void
    onMilestonesChange: (milestoneSlugs: string[]) => void
    onFunnelChange: (included: boolean) => void
    /** Focuses and selects the label on mount, for a stage that was just added. */
    autoFocusLabel?: boolean
}) {
    const locked = Boolean(stage.is_locked)
    const focusLabelOnMount = useCallback((node: HTMLInputElement | null) => {
        if (!node) return
        node.focus({ preventScroll: true })
        node.select()
    }, [])
    const labelId = `${idPrefix}-stage-label-${stage.id}`
    const slugId = `${idPrefix}-stage-slug-${stage.id}`
    const labelErrorId = `${labelId}-error`
    const slugErrorId = `${slugId}-error`

    return (
        <div className="flex flex-col">
            {locked ? (
                <p className="text-muted-foreground pb-3 text-sm">
                    Locked because platform workflows depend on it. Existing org-specific label,
                    color, and ordering are frozen as-is.
                </p>
            ) : null}
            <SettingsSection title="Stage">
                <div className="grid grid-cols-2 gap-3">
                    <div className="min-w-0 space-y-1.5">
                        <Label htmlFor={labelId} className={FIELD_LABEL_CLASS}>
                            Label
                        </Label>
                        <Input
                            id={labelId}
                            ref={autoFocusLabel && !locked ? focusLabelOnMount : undefined}
                            value={stage.label}
                            disabled={locked}
                            maxLength={STAGE_LABEL_MAX_LENGTH}
                            aria-invalid={errors?.label ? true : undefined}
                            aria-describedby={errors?.label ? labelErrorId : undefined}
                            onChange={(event) =>
                                onStageChange((current) =>
                                    withAutoStageColor(current, { ...current, label: event.target.value }),
                                )
                            }
                            className="h-8"
                        />
                        <StageFieldError id={labelErrorId} message={errors?.label} />
                    </div>
                    <div className="min-w-0 space-y-1.5">
                        <Label htmlFor={slugId} className={FIELD_LABEL_CLASS}>
                            Slug
                        </Label>
                        <Input
                            id={slugId}
                            value={stage.slug}
                            disabled={locked}
                            maxLength={STAGE_SLUG_MAX_LENGTH}
                            spellCheck={false}
                            aria-invalid={errors?.slug ? true : undefined}
                            aria-describedby={errors?.slug ? slugErrorId : undefined}
                            onChange={(event) =>
                                onStageChange((current) => {
                                    const slug = normalizeIdentifier(event.target.value)
                                    return withAutoStageColor(current, {
                                        ...current,
                                        slug,
                                        stage_key: isUuidLike(current.id) ? current.stage_key : slug || current.stage_key,
                                    })
                                })
                            }
                            className="h-8 font-mono text-xs"
                        />
                        <StageFieldError id={slugErrorId} message={errors?.slug} />
                    </div>
                    <div className="min-w-0 space-y-1.5">
                        <Label htmlFor={`${idPrefix}-stage-key-${stage.id}`} className={FIELD_LABEL_CLASS}>
                            Stage key
                        </Label>
                        <div className="relative">
                            <Input
                                id={`${idPrefix}-stage-key-${stage.id}`}
                                value={stage.stage_key}
                                readOnly
                                disabled
                                className="h-8 pr-7 font-mono text-xs"
                                aria-label="Stage key"
                            />
                            <LockIcon
                                className="text-muted-foreground pointer-events-none absolute top-1/2 right-2.5 size-3.5 -translate-y-1/2"
                                aria-hidden="true"
                            />
                        </div>
                    </div>
                    <PipelineSelectField
                        id={`${idPrefix}-stage-category-${stage.id}`}
                        label="Type"
                        ariaLabel={`Type for ${stage.label}`}
                        value={stage.category}
                        options={getStageCategoryOptions(stage)}
                        disabled={locked}
                        onValueChange={(value) =>
                            onStageChange((current) =>
                                withAutoStageColor(current, {
                                    ...current,
                                    category: value as StageType,
                                    stage_type: value as StageType,
                                }),
                            )
                        }
                    />
                    <div className="col-span-2 min-w-0 space-y-1.5 min-[440px]:col-span-1">
                        <Label htmlFor={`${idPrefix}-stage-color-${stage.id}`} className={FIELD_LABEL_CLASS}>
                            Color
                        </Label>
                        <StageColorField
                            id={`${idPrefix}-stage-color-${stage.id}`}
                            stage={stage}
                            onStageChange={onStageChange}
                        />
                    </div>
                    <div className="col-span-2 min-w-0 space-y-1.5 min-[440px]:col-span-1">
                        <span className={FIELD_LABEL_CLASS}>Position</span>
                        <StagePositionField stage={stage} index={index} total={total} onMove={onMove} />
                    </div>
                </div>
            </SettingsSection>
            <SettingsSection title="Behavior">
                <StageSemanticsFields
                    idPrefix={idPrefix}
                    entityType={entityType}
                    stage={stage}
                    onStageChange={onStageChange}
                />
            </SettingsSection>
            <SettingsSection title="Rules">
                <StageRulesEditor entityType={entityType} stage={stage} onStageChange={onStageChange} />
            </SettingsSection>
            {showSurrogateEditors && featureConfig ? (
                <SettingsSection title="Journey and funnel">
                    <StageJourneyFields
                        idPrefix={idPrefix}
                        stage={stage}
                        featureConfig={featureConfig}
                        onMilestonesChange={onMilestonesChange}
                        onFunnelChange={onFunnelChange}
                    />
                </SettingsSection>
            ) : null}
            <SettingsSection title="Used by">
                <StageUsageBadges entityType={entityType} dependency={dependency} featureConfig={featureConfig} />
            </SettingsSection>
        </div>
    )
}
