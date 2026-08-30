export type DonorType = "egg" | "sperm"
export type DonorPipelineEntityType = "egg_donor" | "sperm_donor"
export type DonorOwnerType = "user" | "queue"

export interface Donor {
    id: string
    donor_number: string
    donor_type: DonorType
    full_name: string
    email: string
    phone: string | null
    state: string | null
    education: string | null
    source: string | null
    owner_type: DonorOwnerType | null
    owner_id: string | null
    stage_id: string
    stage_key: string
    stage_slug: string
    status: string
    status_label: string
    profile_photo_attachment_id: string | null
    is_archived: boolean
    archived_at: string | null
    created_at: string
    updated_at: string
}

export type DonorListItem = Donor

export interface DonorListResponse {
    items: DonorListItem[]
    total: number
    page: number
    per_page: number
    pages: number
}

export interface DonorCreate {
    donor_type: DonorType
    full_name: string
    email: string
    phone?: string | null
    state?: string | null
    education?: string | null
    source?: string | null
    owner_type?: DonorOwnerType | null
    owner_id?: string | null
}

export type DonorUpdate = Partial<Omit<DonorCreate, "donor_type">>

export interface DonorStatusUpdate {
    stage_id: string
    reason?: string
    effective_at?: string
}

export interface DonorStatusHistoryItem {
    id: string
    donor_id: string
    changed_by_user_id: string | null
    changed_by_name: string | null
    old_stage_id: string | null
    new_stage_id: string | null
    old_status: string | null
    new_status: string
    old_label_snapshot: string | null
    new_label_snapshot: string
    reason: string | null
    effective_at: string
    recorded_at: string
    requested_at: string | null
    approved_by_user_id: string | null
    approved_by_name: string | null
    approved_at: string | null
    is_undo: boolean
    request_id: string | null
}

export interface DonorStatusChangeResponse {
    status: "applied" | "pending_approval"
    donor: Donor | null
    history: DonorStatusHistoryItem | null
    request_id: string | null
    message: string | null
}

export interface DonorNoteListItem {
    id: string
    author_id: string
    content: string
    created_at: string
}

export interface DonorNote extends DonorNoteListItem {
    organization_id: string
    entity_type: "donor"
    entity_id: string
}

export interface DonorNoteCreate {
    content: string
}

export function getDonorTypeLabel(donorType: DonorType): string {
    return donorType === "egg" ? "Egg Donor" : "Sperm Donor"
}

export function getDonorTypePluralLabel(donorType: DonorType): string {
    return donorType === "egg" ? "Egg Donors" : "Sperm Donors"
}

export function getDonorPipelineEntityType(donorType: DonorType): DonorPipelineEntityType {
    return donorType === "egg" ? "egg_donor" : "sperm_donor"
}
