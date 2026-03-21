import type { CSSProperties } from "react"

import type { StageMetadataOption } from "@/lib/api/metadata"
import type { PipelineStage } from "@/lib/api/pipelines"

export const DEFAULT_INTENDED_PARENT_STAGE_OPTIONS: StageMetadataOption[] = [
    {
        id: "new",
        value: "new",
        label: "New",
        stage_key: "new",
        stage_slug: "new",
        stage_type: "intake",
        color: "#3B82F6",
        order: 1,
    },
    {
        id: "ready_to_match",
        value: "ready_to_match",
        label: "Ready to Match",
        stage_key: "ready_to_match",
        stage_slug: "ready_to_match",
        stage_type: "post_approval",
        color: "#F59E0B",
        order: 2,
    },
    {
        id: "matched",
        value: "matched",
        label: "Matched",
        stage_key: "matched",
        stage_slug: "matched",
        stage_type: "post_approval",
        color: "#10B981",
        order: 3,
    },
    {
        id: "delivered",
        value: "delivered",
        label: "Delivered",
        stage_key: "delivered",
        stage_slug: "delivered",
        stage_type: "post_approval",
        color: "#14B8A6",
        order: 4,
    },
]

function normalizeColor(color: string | null | undefined): string {
    return /^#[0-9A-Fa-f]{6}$/.test(color ?? "") ? String(color) : "#6B7280"
}

function withHexAlpha(color: string, alphaHex: string): string {
    const normalized = normalizeColor(color)
    return `${normalized}${alphaHex}`
}

export function getIntendedParentStageOptions(
    options: StageMetadataOption[] | undefined | null,
): StageMetadataOption[] {
    const resolved = options?.length ? options : DEFAULT_INTENDED_PARENT_STAGE_OPTIONS
    return [...resolved].sort((left, right) => left.order - right.order)
}

export function getIntendedParentStageOptionByValue(
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
    }))
}
