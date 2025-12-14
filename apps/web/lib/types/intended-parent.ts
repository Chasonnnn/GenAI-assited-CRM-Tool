/**
 * Intended Parent types
 */

export type IntendedParentStatus = 'new' | 'in_review' | 'matched' | 'inactive'

export interface IntendedParent {
    id: string
    organization_id: string
    full_name: string
    email: string
    phone: string | null
    state: string | null
    budget: number | null
    notes_internal: string | null
    status: IntendedParentStatus
    assigned_to_user_id: string | null
    is_archived: boolean
    archived_at: string | null
    last_activity: string
    created_at: string
    updated_at: string
}

export interface IntendedParentListItem {
    id: string
    full_name: string
    email: string
    phone: string | null
    state: string | null
    budget: number | null
    status: IntendedParentStatus
    assigned_to_user_id: string | null
    is_archived: boolean
    last_activity: string
    created_at: string
}

export interface IntendedParentCreate {
    full_name: string
    email: string
    phone?: string | null
    state?: string | null
    budget?: number | null
    notes_internal?: string | null
    assigned_to_user_id?: string | null
}

export interface IntendedParentUpdate {
    full_name?: string
    email?: string
    phone?: string | null
    state?: string | null
    budget?: number | null
    notes_internal?: string | null
    assigned_to_user_id?: string | null
}

export interface IntendedParentStatusUpdate {
    status: IntendedParentStatus
    reason?: string
}

export interface IntendedParentStatusHistoryItem {
    id: string
    old_status: string | null
    new_status: string
    reason: string | null
    changed_by_user_id: string | null
    changed_at: string
}

export interface IntendedParentStats {
    total: number
    by_status: Record<string, number>
}

export interface IntendedParentListResponse {
    items: IntendedParentListItem[]
    total: number
    page: number
    per_page: number
}

// Entity Note types (polymorphic)
export interface EntityNote {
    id: string
    organization_id: string
    entity_type: string
    entity_id: string
    author_id: string
    content: string
    created_at: string
}

export interface EntityNoteListItem {
    id: string
    author_id: string
    content: string
    created_at: string
}

export interface EntityNoteCreate {
    content: string
}
