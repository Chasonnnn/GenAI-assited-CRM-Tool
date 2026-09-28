import type { CSSProperties } from "react"

import type { StageMetadataOption } from "@/lib/api/metadata"
import type { PipelineStage } from "@/lib/api/pipelines"

function normalizeColor(color: string | null | undefined): string {
    return /^#[0-9A-Fa-f]{6}$/.test(color ?? "") ? String(color) : "#6B7280"
}

function withHexAlpha(color: string, alphaHex: string): string {
    const normalized = normalizeColor(color)
    return `${normalized}${alphaHex}`
}

/** Stage ids come only from the org's pipeline; there is no built-in fallback list. */
export function getIntendedParentStageOptions(
    options: StageMetadataOption[] | undefined | null,
): StageMetadataOption[] {
    return (options ?? []).toSorted((left, right) => left.order - right.order)
}

function getIntendedParentStageOptionByValue(
    options: StageMetadataOption[] | undefined | null,
    value: string | null | undefined,
): StageMetadataOption | undefined {
    if (!value) return undefined
    return getIntendedParentStageOptions(options).find(
        (stage) => stage.stage_key === value || stage.stage_slug === value || stage.value === value,
    )
}

export function getIntendedParentStageOptionById(
    options: StageMetadataOption[] | undefined | null,
    stageId: string | null | undefined,
): StageMetadataOption | undefined {
    if (!stageId) return undefined
    return getIntendedParentStageOptions(options).find((stage) => stage.id === stageId)
}

export function getIntendedParentStatusLabel(
    options: StageMetadataOption[] | undefined | null,
    value: string | null | undefined,
    fallbackLabel?: string | null,
): string {
    return (
        getIntendedParentStageOptionByValue(options, value)?.label
        ?? fallbackLabel
        ?? (value ? value.replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase()) : "Unknown")
    )
}

export function getIntendedParentStatusStyle(
    options: StageMetadataOption[] | undefined | null,
    value: string | null | undefined,
    fallbackColor?: string | null,
): CSSProperties {
    const color = normalizeColor(
        getIntendedParentStageOptionByValue(options, value)?.color ?? fallbackColor,
    )
    return {
        borderColor: withHexAlpha(color, "33"),
        backgroundColor: withHexAlpha(color, "14"),
        color,
    }
}

export function toPipelineStages(options: StageMetadataOption[] | undefined | null): PipelineStage[] {
    return getIntendedParentStageOptions(options).map((stage) => ({
        id: stage.id,
        stage_key: stage.stage_key,
        slug: stage.stage_slug,
        label: stage.label,
        color: stage.color,
        order: stage.order,
        category: stage.stage_type,
        stage_type: stage.stage_type,
        is_active: true,
        semantics: stage.semantics,
    }))
}
