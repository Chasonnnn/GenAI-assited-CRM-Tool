import api from "@/lib/api"
import type { JsonObject } from "@/lib/types/json"

export type ActivityEntityType = "intended_parent" | "donor"

export interface EntityActivity {
    id: string
    activity_type: string
    actor_user_id: string | null
    actor_name: string | null
    details: JsonObject | null
    created_at: string
}

export interface EntityActivityResponse {
    items: EntityActivity[]
    total: number
    page: number
    pages: number
}

const ENTITY_PATHS: Record<ActivityEntityType, string> = {
    intended_parent: "intended-parents",
    donor: "donors",
}

export function getEntityActivity(
    entityType: ActivityEntityType,
    entityId: string,
    page = 1,
    perPage = 100,
): Promise<EntityActivityResponse> {
    const params = new URLSearchParams({ page: String(page), per_page: String(perPage) })
    return api.get<EntityActivityResponse>(
        `/${ENTITY_PATHS[entityType]}/${entityId}/activity?${params.toString()}`,
    )
}

/** Stage transitions consumed by entity activity timelines. */
export interface EntityStageHistory {
    id: string
    from_stage_id: string | null
    to_stage_id: string | null
    from_label_snapshot: string | null
    to_label_snapshot: string | null
    changed_by_user_id: string | null
    changed_by_name?: string | null
    reason: string | null
    changed_at: string
    effective_at?: string | null
    recorded_at?: string | null
    requested_at?: string | null
    approved_by_user_id?: string | null
    approved_by_name?: string | null
    approved_at?: string | null
    is_undo?: boolean
    request_id?: string | null
}
