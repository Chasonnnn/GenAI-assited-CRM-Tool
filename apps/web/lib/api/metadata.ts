import api from "./index"
import type { MatchStatus } from "./matches"
import type { StageType } from "./pipelines"

export interface StageMetadataOption {
    id: string
    value: string
    label: string
    stage_key: string
    stage_slug: string
    stage_type: StageType
    color: string
    order: number
}

export interface MatchStatusMetadata {
    value: MatchStatus
    label: string
    color: string
    order: number
    allowed_transitions: MatchStatus[]
}

export async function getIntendedParentStatuses(): Promise<{ statuses: StageMetadataOption[] }> {
    return api.get<{ statuses: StageMetadataOption[] }>("/metadata/intended-parent-statuses")
}

export async function getMatchStatuses(): Promise<{ statuses: MatchStatusMetadata[] }> {
    return api.get<{ statuses: MatchStatusMetadata[] }>("/metadata/match-statuses")
}
