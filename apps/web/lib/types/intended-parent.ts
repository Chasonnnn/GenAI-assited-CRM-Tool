/**
 * Intended Parent types
 */

import type { MaritalStatus } from '@/lib/intended-parent-marital-status'
import type { TrustFundingStatus } from '@/lib/trust-funding-status'

export type IntendedParentStatus = string
export type EmbryoEggSource = 'intended_mother' | 'egg_donor'
export type EmbryoSpermSource = 'intended_father' | 'sperm_donor'

export interface IntendedParent {
    id: string
    organization_id: string
    intended_parent_number: string
    full_name: string
    email: string
    phone: string | null
    state: string | null
    budget: number | null
    notes_internal: string | null
    pronouns: string | null
    date_of_birth: string | null
    marital_status: MaritalStatus | string | null
    partner_name: string | null
    partner_email: string | null
    partner_pronouns: string | null
    partner_date_of_birth: string | null
    embryo_count: number | null
    pgs_tested: boolean | null
    egg_source: EmbryoEggSource | null
    sperm_source: EmbryoSpermSource | null
    trust_provider_name: string | null
    trust_primary_contact_name: string | null
    trust_email: string | null
    trust_phone: string | null
    trust_address_line1: string | null
    trust_address_line2: string | null
    trust_city: string | null
    trust_state: string | null
    trust_postal: string | null
    trust_case_reference: string | null
    trust_funding_status: TrustFundingStatus | null
    trust_portal_url: string | null
    trust_notes: string | null
    address_line1: string | null
    address_line2: string | null
    city: string | null
    postal: string | null
    ip_clinic_name: string | null
    ip_clinic_address_line1: string | null
    ip_clinic_address_line2: string | null
    ip_clinic_city: string | null
    ip_clinic_state: string | null
    ip_clinic_postal: string | null
    ip_clinic_phone: string | null
    ip_clinic_fax: string | null
    ip_clinic_email: string | null
    status: IntendedParentStatus
    stage_id?: string | null
    stage_key?: string | null
    stage_slug?: string | null
    status_label?: string | null
    owner_type: 'user' | 'queue' | null
    owner_id: string | null
    owner_name: string | null
    is_archived: boolean
    archived_at: string | null
    last_activity: string
    created_at: string
    updated_at: string
}

export interface IntendedParentListItem {
    id: string
    intended_parent_number: string
    full_name: string
    email: string
    phone: string | null
    state: string | null
    budget: number | null
    partner_name: string | null
    status: IntendedParentStatus
    stage_id?: string | null
    stage_key?: string | null
    stage_slug?: string | null
    status_label?: string | null
    owner_type: 'user' | 'queue' | null
    owner_id: string | null
    owner_name: string | null
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
    pronouns?: string | null
    date_of_birth?: string | null
    marital_status?: MaritalStatus | null
    partner_name?: string | null
    partner_email?: string | null
    partner_pronouns?: string | null
    partner_date_of_birth?: string | null
    embryo_count?: number | null
    pgs_tested?: boolean | null
    egg_source?: EmbryoEggSource | null
    sperm_source?: EmbryoSpermSource | null
    trust_provider_name?: string | null
    trust_primary_contact_name?: string | null
    trust_email?: string | null
    trust_phone?: string | null
    trust_address_line1?: string | null
    trust_address_line2?: string | null
    trust_city?: string | null
    trust_state?: string | null
    trust_postal?: string | null
    trust_case_reference?: string | null
    trust_funding_status?: TrustFundingStatus | null
    trust_portal_url?: string | null
    trust_notes?: string | null
    address_line1?: string | null
    address_line2?: string | null
    city?: string | null
    postal?: string | null
    ip_clinic_name?: string | null
    ip_clinic_address_line1?: string | null
    ip_clinic_address_line2?: string | null
    ip_clinic_city?: string | null
    ip_clinic_state?: string | null
    ip_clinic_postal?: string | null
    ip_clinic_phone?: string | null
    ip_clinic_fax?: string | null
    ip_clinic_email?: string | null
    owner_type?: 'user' | 'queue' | null
    owner_id?: string | null
}

export interface IntendedParentUpdate {
    full_name?: string
    email?: string
    phone?: string | null
    state?: string | null
    budget?: number | null
    notes_internal?: string | null
    pronouns?: string | null
    date_of_birth?: string | null
    marital_status?: MaritalStatus | string | null
    partner_name?: string | null
    partner_email?: string | null
    partner_pronouns?: string | null
    partner_date_of_birth?: string | null
    embryo_count?: number | null
    pgs_tested?: boolean | null
    egg_source?: EmbryoEggSource | null
    sperm_source?: EmbryoSpermSource | null
    trust_provider_name?: string | null
    trust_primary_contact_name?: string | null
    trust_email?: string | null
    trust_phone?: string | null
    trust_address_line1?: string | null
    trust_address_line2?: string | null
    trust_city?: string | null
    trust_state?: string | null
    trust_postal?: string | null
    trust_case_reference?: string | null
    trust_funding_status?: TrustFundingStatus | string | null
    trust_portal_url?: string | null
    trust_notes?: string | null
    address_line1?: string | null
    address_line2?: string | null
    city?: string | null
    postal?: string | null
    ip_clinic_name?: string | null
    ip_clinic_address_line1?: string | null
    ip_clinic_address_line2?: string | null
    ip_clinic_city?: string | null
    ip_clinic_state?: string | null
    ip_clinic_postal?: string | null
    ip_clinic_phone?: string | null
    ip_clinic_fax?: string | null
    ip_clinic_email?: string | null
    owner_type?: 'user' | 'queue' | null
    owner_id?: string | null
}

export interface IntendedParentStatusUpdate {
    stage_id: string
    reason?: string
    effective_at?: string
}

export interface IntendedParentStatusHistoryItem {
    id: string
    old_stage_id?: string | null
    new_stage_id?: string | null
    old_status: string | null
    new_status: string
    reason: string | null
    changed_by_user_id: string | null
    changed_by_name: string | null
    changed_at: string
    effective_at: string | null
    recorded_at: string | null
    requested_at: string | null
    approved_by_user_id: string | null
    approved_by_name: string | null
    approved_at: string | null
    is_undo: boolean
    request_id: string | null
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

export interface IntendedParentStatusChangeResponse {
    status: 'applied' | 'pending_approval'
    intended_parent: IntendedParent | null
    request_id: string | null
    message: string | null
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
