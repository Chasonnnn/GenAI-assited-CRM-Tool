/**
 * Intended Parents API client
 */

import api from './index'
import type {
    IntendedParent,
    IntendedParentCreate,
    IntendedParentUpdate,
    IntendedParentStatusUpdate,
    IntendedParentStatusHistoryItem,
    IntendedParentStats,
    IntendedParentListResponse,
    EntityNote,
    EntityNoteListItem,
    EntityNoteCreate,
} from '@/lib/types/intended-parent'

// Filters interface
export interface IntendedParentFilters {
    status?: string[]
    state?: string
    budget_min?: number
    budget_max?: number
    q?: string
    owner_id?: string
    include_archived?: boolean
    created_after?: string
    created_before?: string
    page?: number
    per_page?: number
    sort_by?: string
    sort_order?: 'asc' | 'desc'
}

// List with filters
export async function listIntendedParents(
    filters: IntendedParentFilters = {}
): Promise<IntendedParentListResponse> {
    const params = new URLSearchParams()

    if (filters.status?.length) {
        filters.status.forEach(s => params.append('status', s))
    }
    if (filters.state) params.set('state', filters.state)
    if (filters.budget_min !== undefined) params.set('budget_min', String(filters.budget_min))
    if (filters.budget_max !== undefined) params.set('budget_max', String(filters.budget_max))
    if (filters.q) params.set('q', filters.q)
    if (filters.owner_id) params.set('owner_id', filters.owner_id)
    if (filters.include_archived) params.set('include_archived', 'true')
    if (filters.created_after) params.set('created_after', filters.created_after)
    if (filters.created_before) params.set('created_before', filters.created_before)
    if (filters.page) params.set('page', String(filters.page))
    if (filters.per_page) params.set('per_page', String(filters.per_page))
    if (filters.sort_by) params.set('sort_by', filters.sort_by)
    if (filters.sort_order) params.set('sort_order', filters.sort_order)

    const queryString = params.toString()
    const url = queryString ? `/intended-parents?${queryString}` : '/intended-parents'
    return api.get<IntendedParentListResponse>(url)
}

// Stats
export async function getIntendedParentStats(): Promise<IntendedParentStats> {
    return api.get<IntendedParentStats>('/intended-parents/stats')
}

// CRUD
export async function getIntendedParent(id: string): Promise<IntendedParent> {
    return api.get<IntendedParent>(`/intended-parents/${id}`)
}

export async function createIntendedParent(data: IntendedParentCreate): Promise<IntendedParent> {
    return api.post<IntendedParent>('/intended-parents', data)
}

export async function updateIntendedParent(
    id: string,
    data: IntendedParentUpdate
): Promise<IntendedParent> {
    return api.patch<IntendedParent>(`/intended-parents/${id}`, data)
}

// Status
export async function updateIntendedParentStatus(
    id: string,
    data: IntendedParentStatusUpdate
): Promise<IntendedParent> {
    return api.patch<IntendedParent>(`/intended-parents/${id}/status`, data)
}

// Archive / Restore / Delete
export async function archiveIntendedParent(id: string): Promise<IntendedParent> {
    return api.post<IntendedParent>(`/intended-parents/${id}/archive`, {})
}

export async function restoreIntendedParent(id: string): Promise<IntendedParent> {
    return api.post<IntendedParent>(`/intended-parents/${id}/restore`, {})
}

export async function deleteIntendedParent(id: string): Promise<void> {
    return api.delete(`/intended-parents/${id}`)
}

// Status History
export async function getIntendedParentHistory(
    id: string
): Promise<IntendedParentStatusHistoryItem[]> {
    return api.get<IntendedParentStatusHistoryItem[]>(`/intended-parents/${id}/history`)
}

// Notes
export async function listIntendedParentNotes(id: string): Promise<EntityNoteListItem[]> {
    return api.get<EntityNoteListItem[]>(`/intended-parents/${id}/notes`)
}

export async function createIntendedParentNote(
    id: string,
    data: EntityNoteCreate
): Promise<EntityNote> {
    return api.post<EntityNote>(`/intended-parents/${id}/notes`, data)
}

export async function deleteIntendedParentNote(ipId: string, noteId: string): Promise<void> {
    return api.delete(`/intended-parents/${ipId}/notes/${noteId}`)
}
