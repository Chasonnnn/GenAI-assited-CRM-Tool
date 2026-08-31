import api from "@/lib/api"
import type {
    Donor,
    DonorCreate,
    DonorListResponse,
    DonorNote,
    DonorNoteCreate,
    DonorNoteListItem,
    DonorStatusChangeResponse,
    DonorStatusHistoryItem,
    DonorStatusUpdate,
    DonorType,
    DonorUpdate,
} from "@/lib/types/donor"

export interface DonorFilters {
    donor_type: DonorType
    stage_id?: string
    state?: string
    q?: string
    owner_id?: string
    dynamic_filter?: "attention_stuck"
    created_from?: string
    created_to?: string
    sort_by?: DonorSortBy
    sort_order?: "asc" | "desc"
    include_archived?: boolean
    archived_only?: boolean
    page?: number
    per_page?: number
}

export type DonorSortBy =
    | "donor_number"
    | "full_name"
    | "state"
    | "education"
    | "stage"
    | "created_at"

export async function listDonors(filters: DonorFilters): Promise<DonorListResponse> {
    const params = new URLSearchParams({ donor_type: filters.donor_type })
    if (filters.stage_id) params.set("stage_id", filters.stage_id)
    if (filters.state) params.set("state", filters.state)
    if (filters.q) params.set("q", filters.q)
    if (filters.owner_id) params.set("owner_id", filters.owner_id)
    if (filters.dynamic_filter) params.set("dynamic_filter", filters.dynamic_filter)
    if (filters.created_from) params.set("created_from", filters.created_from)
    if (filters.created_to) params.set("created_to", filters.created_to)
    if (filters.sort_by) params.set("sort_by", filters.sort_by)
    if (filters.sort_order) params.set("sort_order", filters.sort_order)
    if (filters.include_archived) params.set("include_archived", "true")
    if (filters.archived_only) params.set("archived_only", "true")
    if (filters.page) params.set("page", String(filters.page))
    if (filters.per_page) params.set("per_page", String(filters.per_page))

    return api.get<DonorListResponse>(`/donors?${params.toString()}`)
}

export async function createDonor(data: DonorCreate): Promise<Donor> {
    return api.post<Donor>("/donors", data)
}

export async function getDonor(id: string): Promise<Donor> {
    return api.get<Donor>(`/donors/${id}`)
}

export async function updateDonor(id: string, data: DonorUpdate): Promise<Donor> {
    return api.patch<Donor>(`/donors/${id}`, data)
}

export async function updateDonorStatus(
    id: string,
    data: DonorStatusUpdate,
): Promise<DonorStatusChangeResponse> {
    return api.patch<DonorStatusChangeResponse>(`/donors/${id}/status`, data)
}

export async function archiveDonor(id: string): Promise<Donor> {
    return api.post<Donor>(`/donors/${id}/archive`, {})
}

export async function restoreDonor(id: string): Promise<Donor> {
    return api.post<Donor>(`/donors/${id}/restore`, {})
}

export async function getDonorHistory(id: string): Promise<DonorStatusHistoryItem[]> {
    return api.get<DonorStatusHistoryItem[]>(`/donors/${id}/history`)
}

export async function listDonorNotes(id: string): Promise<DonorNoteListItem[]> {
    return api.get<DonorNoteListItem[]>(`/donors/${id}/notes`)
}

export async function createDonorNote(id: string, data: DonorNoteCreate): Promise<DonorNote> {
    return api.post<DonorNote>(`/donors/${id}/notes`, data)
}

export async function deleteDonorNote(donorId: string, noteId: string): Promise<void> {
    return api.delete(`/donors/${donorId}/notes/${noteId}`)
}
