/**
 * TypeScript types for Surrogates module.
 * Matches backend stage-based pipeline model.
 */

export type SurrogateSource = 'manual' | 'meta' | 'website' | 'referral';

// List item (minimal for table display)
export interface SurrogateListItem {
    id: string;
    surrogate_number: string;
    stage_id: string;
    stage_slug: string | null;
    stage_type: string | null;
    status_label: string;
    source: SurrogateSource;
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
    last_activity_at: string | null;
    created_at: string;
}

// Full surrogate detail
export interface SurrogateRead extends SurrogateListItem {
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

    // =========================================================================
    // INSURANCE INFO
    // =========================================================================
    insurance_company: string | null;
    insurance_plan_name: string | null;
    insurance_phone: string | null;
    insurance_policy_number: string | null;
    insurance_member_id: string | null;
    insurance_group_number: string | null;
    insurance_subscriber_name: string | null;
    insurance_subscriber_dob: string | null;  // ISO date string

    // =========================================================================
    // IVF CLINIC
    // =========================================================================
    clinic_name: string | null;
    clinic_address_line1: string | null;
    clinic_address_line2: string | null;
    clinic_city: string | null;
    clinic_state: string | null;
    clinic_postal: string | null;
    clinic_phone: string | null;
    clinic_email: string | null;

    // =========================================================================
    // MONITORING CLINIC
    // =========================================================================
    monitoring_clinic_name: string | null;
    monitoring_clinic_address_line1: string | null;
    monitoring_clinic_address_line2: string | null;
    monitoring_clinic_city: string | null;
    monitoring_clinic_state: string | null;
    monitoring_clinic_postal: string | null;
    monitoring_clinic_phone: string | null;
    monitoring_clinic_email: string | null;

    // =========================================================================
    // OB PROVIDER
    // =========================================================================
    ob_provider_name: string | null;
    ob_clinic_name: string | null;
    ob_address_line1: string | null;
    ob_address_line2: string | null;
    ob_city: string | null;
    ob_state: string | null;
    ob_postal: string | null;
    ob_phone: string | null;
    ob_email: string | null;

    // =========================================================================
    // DELIVERY HOSPITAL
    // =========================================================================
    delivery_hospital_name: string | null;
    delivery_hospital_address_line1: string | null;
    delivery_hospital_address_line2: string | null;
    delivery_hospital_city: string | null;
    delivery_hospital_state: string | null;
    delivery_hospital_postal: string | null;
    delivery_hospital_phone: string | null;
    delivery_hospital_email: string | null;

    // =========================================================================
    // PREGNANCY TRACKING
    // =========================================================================
    pregnancy_start_date: string | null;  // ISO date string
    pregnancy_due_date: string | null;    // ISO date string
    actual_delivery_date: string | null;  // ISO date string
}

// Paginated response
export interface SurrogateListResponse {
    items: SurrogateListItem[];
    total: number;
    page: number;
    per_page: number;
    pages: number;
}
