import type { SurrogateStatusHistory } from "@/lib/api/surrogates"
import type { DonorStatusHistoryItem } from "@/lib/types/donor"
import type { IntendedParentStatusHistoryItem } from "@/lib/types/intended-parent"

function labelFromStatus(value: string | null): string | null {
    return value?.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase()) ?? null
}

export function normalizeIntendedParentHistory(
    history: IntendedParentStatusHistoryItem[],
): SurrogateStatusHistory[] {
    return history.map((entry) => ({
        id: entry.id,
        from_stage_id: entry.old_stage_id ?? null,
        to_stage_id: entry.new_stage_id ?? null,
        from_label_snapshot: entry.old_label_snapshot ?? labelFromStatus(entry.old_status),
        to_label_snapshot: entry.new_label_snapshot ?? labelFromStatus(entry.new_status),
        changed_by_user_id: entry.changed_by_user_id,
        changed_by_name: entry.changed_by_name,
        reason: entry.reason,
        changed_at: entry.changed_at,
        effective_at: entry.effective_at,
        recorded_at: entry.recorded_at,
        requested_at: entry.requested_at,
        approved_by_user_id: entry.approved_by_user_id,
        approved_by_name: entry.approved_by_name,
        approved_at: entry.approved_at,
        is_undo: entry.is_undo,
        request_id: entry.request_id,
    }))
}

export function normalizeDonorHistory(
    history: DonorStatusHistoryItem[],
): SurrogateStatusHistory[] {
    return history.map((entry) => ({
        id: entry.id,
        from_stage_id: entry.old_stage_id,
        to_stage_id: entry.new_stage_id,
        from_label_snapshot: entry.old_label_snapshot,
        to_label_snapshot: entry.new_label_snapshot,
        changed_by_user_id: entry.changed_by_user_id,
        changed_by_name: entry.changed_by_name,
        reason: entry.reason,
        changed_at: entry.effective_at,
        effective_at: entry.effective_at,
        recorded_at: entry.recorded_at,
        requested_at: entry.requested_at,
        approved_by_user_id: entry.approved_by_user_id,
        approved_by_name: entry.approved_by_name,
        approved_at: entry.approved_at,
        is_undo: entry.is_undo,
        request_id: entry.request_id,
    }))
}
