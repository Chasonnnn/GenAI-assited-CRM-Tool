import type { MatchStatus } from "@/lib/api/matches"
import type { StageType } from "@/lib/api/pipelines"
import { MATCH_STATUS_DEFINITIONS } from "@/lib/match-status-definitions"

export type StageOption = {
    value: string
    label: string
    /** Stage color from pipeline data (hex). */
    color?: string | null
    /** Tailwind background class for colors defined in code, such as match statuses. */
    dotClassName?: string
    /** Group heading. Options with the same group render under one heading, in first-appearance order. */
    group?: string
    count?: number
    disabled?: boolean
}

export const ALL_STAGES_VALUE = "all"

const STAGE_TYPE_GROUP_LABELS: Record<StageType, string> = {
    intake: "Intake",
    post_approval: "Post-approval",
    paused: "Paused & closed",
    terminal: "Paused & closed",
}

type PipelineStageLike = {
    id: string
    label: string
    color?: string | null
    order?: number
    stage_key?: string
    slug?: string
    stage_type?: StageType | null
    category?: StageType | null
    is_active?: boolean
}

/**
 * Stage options in pipeline order, grouped intake / post-approval / paused & closed.
 * `valueKey` selects the field the filter stores: surrogate and donor lists use `id`,
 * intended parent lists use `stage_key`.
 */
export function pipelineStageOptions(
    stages: readonly PipelineStageLike[],
    { valueKey = "id", activeOnly = false }: { valueKey?: "id" | "stage_key" | "slug"; activeOnly?: boolean } = {},
): StageOption[] {
    return stages
        .filter((stage) => !activeOnly || stage.is_active !== false)
        .toSorted((a, b) => (a.order ?? 0) - (b.order ?? 0))
        .map((stage) => {
            const stageType = stage.stage_type ?? stage.category ?? null
            return {
                value: stage[valueKey] ?? stage.id,
                label: stage.label,
                color: stage.color ?? null,
                ...(stageType ? { group: STAGE_TYPE_GROUP_LABELS[stageType] } : {}),
            }
        })
}

const MATCH_STATUS_DOT_CLASS: Record<MatchStatus, string> = {
    under_review: "bg-amber-500",
    accepted: "bg-green-500",
    cancellation_pending: "bg-amber-400",
    declined: "bg-red-500",
    cancelled: "bg-gray-400",
    completed: "bg-emerald-600",
}

const OPEN_MATCH_STATUSES = new Set<MatchStatus>(["under_review", "accepted", "cancellation_pending"])

/** Match statuses as stage options: open statuses first, then closed ones. */
export function matchStatusStageOptions(counts?: Partial<Record<MatchStatus, number>>): StageOption[] {
    return MATCH_STATUS_DEFINITIONS.toSorted((a, b) => a.order - b.order).map((definition) => {
        const count = counts?.[definition.value]
        return {
            value: definition.value,
            label: definition.label,
            dotClassName: MATCH_STATUS_DOT_CLASS[definition.value],
            group: OPEN_MATCH_STATUSES.has(definition.value) ? "Open" : "Closed",
            ...(count === undefined ? {} : { count }),
        }
    })
}

export function findStageOption(
    value: string | null | undefined,
    options: readonly StageOption[],
): StageOption | undefined {
    if (!value) return undefined
    return options.find((option) => option.value === value)
}

/**
 * The one label helper for a stage value: use it for the select trigger, filter chips,
 * summaries and cells so a raw id never reaches the UI.
 */
export function getStageOptionLabel(
    value: string | null | undefined,
    options: readonly StageOption[],
    {
        allLabel = "All Stages",
        emptyLabel = allLabel,
        unknownLabel = "Unknown stage",
    }: { allLabel?: string; emptyLabel?: string; unknownLabel?: string } = {},
): string {
    if (!value) return emptyLabel
    if (value === ALL_STAGES_VALUE) return allLabel
    return findStageOption(value, options)?.label ?? unknownLabel
}

export function getMatchStatusFilterLabel(value: string | null | undefined): string {
    return getStageOptionLabel(value, matchStatusStageOptions())
}
