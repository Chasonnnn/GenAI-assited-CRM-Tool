"use client"

import { useState, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { StageOptionLabel, groupStageOptions } from "@/components/stage-select"
import type { CampaignRecipientType } from "@/lib/api/campaigns"
import type { StageMetadataOption } from "@/lib/api/metadata"
import type { PipelineStage } from "@/lib/api/pipelines"
import {
    CAMPAIGN_RECIPIENT_OPTIONS,
    getCampaignRecipientLabel,
    isCampaignRecipientType,
    isDonorCampaignRecipientType,
} from "@/lib/campaign-recipient"
import { US_STATES } from "@/lib/constants/us-states"
import { getIntendedParentStageOptions } from "@/lib/intended-parent-stage-utils"
import { pipelineStageOptions, type StageOption } from "@/lib/stage-options"

export type CampaignChannel = "email" | "messaging"

const TERRITORY_CODES = new Set(["PR", "GU", "VI", "AS", "MP"])
const STATE_OPTIONS = US_STATES.filter((state) => !TERRITORY_CODES.has(state.value))
const TERRITORY_OPTIONS = US_STATES.filter((state) => TERRITORY_CODES.has(state.value))
const STATE_LABEL_BY_CODE = new Map<string, string>(US_STATES.map((state) => [state.value, state.label]))

/**
 * Stage filter options for a campaign audience. Intended parents filter by status slug; every
 * other recipient type filters by the active stages of its own pipeline.
 */
export function campaignStageOptions(
    recipientType: CampaignRecipientType,
    pipelineStages: readonly PipelineStage[] | undefined,
    intendedParentStatuses: StageMetadataOption[] | undefined | null,
): StageOption[] {
    if (recipientType === "intended_parent") {
        return pipelineStageOptions(
            getIntendedParentStageOptions(intendedParentStatuses).map((status) => ({
                id: status.stage_slug,
                label: status.label,
                color: status.color,
                order: status.order,
                stage_type: status.stage_type,
            })),
        )
    }
    return pipelineStageOptions(pipelineStages ?? [], { activeOnly: true })
}

export function getCampaignStateLabel(code: string): string | undefined {
    return STATE_LABEL_BY_CODE.get(code)
}

function summarizeSelection(labels: readonly string[], allLabel: string, noun: string): string {
    if (labels.length === 0) return allLabel
    if (labels.length <= 2) return labels.join(", ")
    return `${labels.length} ${noun}`
}

/** One-line audience summary, for example "Surrogates · All stages · CA, TX · Unsubscribed excluded". */
export function summarizeCampaignAudience({
    channel,
    recipientType,
    stageOptions,
    selectedStages,
    selectedStates,
    includeUnsubscribed,
}: {
    channel: CampaignChannel
    recipientType: CampaignRecipientType
    stageOptions: readonly StageOption[]
    selectedStages: readonly string[]
    selectedStates: readonly string[]
    includeUnsubscribed: boolean
}): string {
    const isIntendedParent = recipientType === "intended_parent"
    const stageLabels = selectedStages.flatMap((value) => {
        const option = stageOptions.find((candidate) => candidate.value === value)
        return option ? [option.label] : []
    })
    const stateLabels = selectedStates.flatMap((code) => {
        const label = STATE_LABEL_BY_CODE.get(code)
        return label ? [label] : []
    })
    const parts = [
        getCampaignRecipientLabel(recipientType),
        summarizeSelection(
            stageLabels,
            isIntendedParent ? "All statuses" : "All stages",
            isIntendedParent ? "statuses" : "stages",
        ),
        summarizeSelection(stateLabels, "All states", "states"),
    ]
    if (channel === "email") {
        parts.push(includeUnsubscribed ? "Unsubscribed included" : "Unsubscribed excluded")
    }
    return parts.join(" · ")
}

type CampaignAudienceFieldsProps = {
    /** Prefix for control ids, so the wizard and the edit dialog never share ids. */
    idPrefix: string
    channel: CampaignChannel
    recipientType: CampaignRecipientType
    onRecipientTypeChange: (value: CampaignRecipientType) => void
    stageOptions: readonly StageOption[]
    selectedStages: readonly string[]
    onSelectedStagesChange: (next: string[]) => void
    selectedStates: readonly string[]
    onSelectedStatesChange: (next: string[]) => void
    includeUnsubscribed: boolean
    onIncludeUnsubscribedChange: (value: boolean) => void
}

/** Recipient type, stage and state filters, and the unsubscribe option. Shared by create and edit. */
export function CampaignAudienceFields({
    idPrefix,
    channel,
    recipientType,
    onRecipientTypeChange,
    stageOptions,
    selectedStages,
    onSelectedStagesChange,
    selectedStates,
    onSelectedStatesChange,
    includeUnsubscribed,
    onIncludeUnsubscribedChange,
}: CampaignAudienceFieldsProps) {
    const recipientTypeId = `${idPrefix}-recipient-type`
    const recipientOptionItems: ReactNode[] = []
    for (const option of CAMPAIGN_RECIPIENT_OPTIONS) {
        // Messaging campaigns cannot reach donors.
        if (channel === "email" || !isDonorCampaignRecipientType(option.value)) {
            recipientOptionItems.push(
                <SelectItem key={option.value} value={option.value}>
                    {option.label}
                </SelectItem>,
            )
        }
    }

    return (
        <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-2">
                <Label htmlFor={recipientTypeId}>Recipient type</Label>
                <Select
                    aria-label="Recipient type"
                    value={recipientType}
                    onValueChange={(value) => {
                        if (isCampaignRecipientType(value)) onRecipientTypeChange(value)
                    }}
                >
                    <SelectTrigger id={recipientTypeId} aria-label="Recipient type" className="w-full">
                        <SelectValue placeholder="Select type">
                            {(value: string | null) =>
                                isCampaignRecipientType(value) ? getCampaignRecipientLabel(value) : "Select type"
                            }
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>{recipientOptionItems}</SelectContent>
                </Select>
            </div>
            <CampaignStageFilter
                idPrefix={idPrefix}
                label={recipientType === "intended_parent" ? "Filter by status (optional)" : "Filter by stage (optional)"}
                allLabel={recipientType === "intended_parent" ? "All statuses included" : "All stages included"}
                options={stageOptions}
                selected={selectedStages}
                onSelectedChange={onSelectedStagesChange}
            />
            <CampaignStateFilter
                idPrefix={idPrefix}
                selected={selectedStates}
                onSelectedChange={onSelectedStatesChange}
            />
            {channel === "email" ? (
                <div className="flex items-start gap-3 rounded-lg border p-4">
                    <Checkbox
                        id={`${idPrefix}-include-unsubscribed`}
                        checked={includeUnsubscribed}
                        onCheckedChange={(checked) => onIncludeUnsubscribedChange(checked === true)}
                        aria-describedby={`${idPrefix}-include-unsubscribed-hint`}
                    />
                    <div className="flex flex-col gap-1">
                        <Label htmlFor={`${idPrefix}-include-unsubscribed`} className="cursor-pointer">
                            Include unsubscribed recipients
                        </Label>
                        <p id={`${idPrefix}-include-unsubscribed-hint`} className="text-xs text-muted-foreground">
                            Only with explicit consent. Hard bounces and complaints are always suppressed.
                        </p>
                    </div>
                </div>
            ) : null}
        </div>
    )
}

function CampaignStageFilter({
    idPrefix,
    label,
    allLabel,
    options,
    selected,
    onSelectedChange,
}: {
    idPrefix: string
    label: string
    allLabel: string
    options: readonly StageOption[]
    selected: readonly string[]
    onSelectedChange: (next: string[]) => void
}) {
    const labelId = `${idPrefix}-stage-filter-label`
    const selectedSet = new Set(selected)
    const groups = groupStageOptions(options)
    const presetGroups = groups.filter((group) => group.label)

    return (
        <div role="group" aria-labelledby={labelId} className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <span id={labelId} className="text-sm font-medium">
                    {label}
                </span>
                <div className="flex items-center gap-1">
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => onSelectedChange(options.map((option) => option.value))}
                        disabled={options.length === 0}
                    >
                        Select all
                    </Button>
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => onSelectedChange([])}
                        disabled={selected.length === 0}
                    >
                        Clear
                    </Button>
                </div>
            </div>
            {presetGroups.length > 1 ? (
                <div className="flex flex-wrap gap-2">
                    {presetGroups.map((group) => (
                        <Button
                            key={group.label}
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => onSelectedChange(group.options.map((option) => option.value))}
                        >
                            {group.label}
                        </Button>
                    ))}
                </div>
            ) : null}
            <div className="flex max-h-56 flex-col gap-3 overflow-y-auto rounded-md border p-3">
                {groups.map((group) => (
                    <div key={group.label ?? "ungrouped"} className="flex flex-col gap-2">
                        {group.label && presetGroups.length > 1 ? (
                            <p className="text-xs font-medium text-muted-foreground">{group.label}</p>
                        ) : null}
                        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                            {group.options.map((option) => {
                                const checkboxId = `${idPrefix}-stage-${option.value}`
                                return (
                                    <div key={option.value} className="flex min-w-0 items-center gap-2">
                                        <Checkbox
                                            id={checkboxId}
                                            checked={selectedSet.has(option.value)}
                                            onCheckedChange={(checked) =>
                                                onSelectedChange(
                                                    checked
                                                        ? [...selected, option.value]
                                                        : selected.filter((value) => value !== option.value),
                                                )
                                            }
                                        />
                                        <Label htmlFor={checkboxId} className="min-w-0 cursor-pointer font-normal">
                                            <StageOptionLabel option={option} />
                                        </Label>
                                    </div>
                                )
                            })}
                        </div>
                    </div>
                ))}
            </div>
            <p className="text-xs text-muted-foreground">
                {selected.length === 0 ? allLabel : `${selected.length} selected`}
            </p>
        </div>
    )
}

function CampaignStateFilter({
    idPrefix,
    selected,
    onSelectedChange,
}: {
    idPrefix: string
    selected: readonly string[]
    onSelectedChange: (next: string[]) => void
}) {
    const [search, setSearch] = useState("")
    const [showTerritories, setShowTerritories] = useState(false)
    const selectedSet = new Set(selected)
    const labelId = `${idPrefix}-state-filter-label`
    const searchId = `${idPrefix}-state-search`
    const normalizedSearch = search.trim().toLowerCase()
    const matchesSearch = (option: (typeof US_STATES)[number]) =>
        normalizedSearch ? option.label.toLowerCase().includes(normalizedSearch) : true
    const includeTerritories = showTerritories || normalizedSearch.length > 0
    const visibleOptions = [
        ...STATE_OPTIONS.filter(matchesSearch),
        ...(includeTerritories ? TERRITORY_OPTIONS.filter(matchesSearch) : []),
    ]

    return (
        <div role="group" aria-labelledby={labelId} className="flex flex-col gap-2">
            <span id={labelId} className="text-sm font-medium">
                Filter by state (optional)
            </span>
            <Input
                id={searchId}
                aria-label="Search states"
                placeholder="Search states"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
            />
            <div className="flex flex-wrap items-center gap-1">
                <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                        const next = new Set(selected)
                        for (const option of visibleOptions) next.add(option.value)
                        onSelectedChange(Array.from(next))
                    }}
                    disabled={visibleOptions.length === 0}
                >
                    {normalizedSearch ? "Select results" : "Select all"}
                </Button>
                <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => onSelectedChange([])}
                    disabled={selected.length === 0}
                >
                    Clear
                </Button>
                <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    aria-pressed={showTerritories}
                    onClick={() => setShowTerritories((current) => !current)}
                >
                    {showTerritories ? "Hide territories" : "Show territories"}
                </Button>
            </div>
            <div className="grid max-h-56 grid-cols-2 gap-2 overflow-y-auto rounded-md border p-3 sm:grid-cols-3">
                {visibleOptions.length === 0 ? (
                    <p className="col-span-full text-sm text-muted-foreground">No states match your search.</p>
                ) : null}
                {visibleOptions.map((option) => {
                    const checkboxId = `${idPrefix}-state-${option.value}`
                    return (
                        <div key={option.value} className="flex min-w-0 items-center gap-2">
                            <Checkbox
                                id={checkboxId}
                                checked={selectedSet.has(option.value)}
                                onCheckedChange={(checked) =>
                                    onSelectedChange(
                                        checked
                                            ? [...selected, option.value]
                                            : selected.filter((value) => value !== option.value),
                                    )
                                }
                            />
                            <Label htmlFor={checkboxId} className="min-w-0 cursor-pointer truncate font-normal">
                                {option.label}
                            </Label>
                        </div>
                    )
                })}
            </div>
            <p className="text-xs text-muted-foreground">
                {selected.length === 0 ? "All states included" : `${selected.length} selected`}
            </p>
        </div>
    )
}
