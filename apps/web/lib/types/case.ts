/**
 * TypeScript types for Cases module.
 * Matches backend Pydantic schemas.
 */

// Enums matching backend
export type CaseStatus =
    | 'new_unread'
    | 'contacted'
    | 'phone_screen_scheduled'
    | 'phone_screened'
    | 'pending_questionnaire'
    | 'questionnaire_received'
    | 'pending_records'
    | 'pending_approval'
    | 'approved'
    | 'disqualified'
    | 'pending_match'
    | 'matched'
    | 'pre_screening'
    | 'synced'
    | 'pregnant'
    | 'delivered'
    | 'archived'
    | 'restored';

export type CaseSource = 'manual' | 'meta' | 'import';

// List item (minimal for table display)
export interface CaseListItem {
    id: string;
    case_number: string;
    status: CaseStatus;
    source: CaseSource;
    full_name: string;
    email: string;
    phone: string | null;
    state: string | null;
    assigned_to_name: string | null;
    created_at: string;
    is_archived: boolean;
}

// Full case detail
export interface CaseRead extends CaseListItem {
    assigned_to_user_id: string | null;
    created_by_user_id: string | null;
    date_of_birth: string | null;
    race: string | null;
    height_ft: number | null;
    weight_lb: number | null;
    is_age_eligible: boolean | null;
    is_citizen_or_pr: boolean | null;
    has_child: boolean | null;
    is_non_smoker: boolean | null;
    has_surrogate_experience: boolean | null;
    num_deliveries: number | null;
    num_csections: number | null;
    archived_at: string | null;
    updated_at: string;
}

// Paginated response
export interface CaseListResponse {
    items: CaseListItem[];
    total: number;
    page: number;
    per_page: number;
    pages: number;
}

// Status display config
export const STATUS_CONFIG: Record<CaseStatus, { label: string; color: string }> = {
    new_unread: { label: 'New', color: 'bg-blue-500' },
    contacted: { label: 'Contacted', color: 'bg-sky-500' },
    phone_screen_scheduled: { label: 'Screen Scheduled', color: 'bg-cyan-500' },
    phone_screened: { label: 'Screened', color: 'bg-teal-500' },
    pending_questionnaire: { label: 'Pending Q', color: 'bg-amber-500' },
    questionnaire_received: { label: 'Q Received', color: 'bg-yellow-500' },
    pending_records: { label: 'Pending Records', color: 'bg-orange-500' },
    pending_approval: { label: 'Pending Approval', color: 'bg-pink-500' },
    approved: { label: 'Approved', color: 'bg-green-500' },
    disqualified: { label: 'Disqualified', color: 'bg-red-500' },
    pending_match: { label: 'Pending Match', color: 'bg-purple-500' },
    matched: { label: 'Matched', color: 'bg-violet-500' },
    pre_screening: { label: 'Pre-Screening', color: 'bg-indigo-500' },
    synced: { label: 'Synced', color: 'bg-fuchsia-500' },
    pregnant: { label: 'Pregnant', color: 'bg-emerald-500' },
    delivered: { label: 'Delivered', color: 'bg-lime-500' },
    archived: { label: 'Archived', color: 'bg-gray-500' },
    restored: { label: 'Restored', color: 'bg-slate-500' },
};
