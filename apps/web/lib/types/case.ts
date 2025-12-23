/**
 * TypeScript types for Cases module.
 * Matches backend stage-based pipeline model.
 */

export type CaseSource = 'manual' | 'meta' | 'website' | 'referral';

// List item (minimal for table display)
export interface CaseListItem {
    id: string;
    case_number: string;
    stage_id: string;
    stage_slug: string | null;
    stage_type: string | null;
    status_label: string;
    source: CaseSource;
    full_name: string;
    email: string;
    phone: string | null;
    state: string | null;
    race: string | null;  // Added for table display
    owner_type: 'user' | 'queue' | null;
    owner_id: string | null;
    owner_name: string | null;
    is_priority: boolean;
    is_archived: boolean;
    age: number | null;  // Calculated from date_of_birth
    bmi: number | null;  // Calculated from height_ft and weight_lb
    created_at: string;
}

// Full case detail
export interface CaseRead extends CaseListItem {
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
