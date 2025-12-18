/**
 * TypeScript types for Cases module.
 * Matches backend Pydantic schemas from apps/api/app/db/enums.py
 */

// Enums matching backend EXACTLY
export type CaseStatus =
    // Stage A: Intake Pipeline
    | 'new_unread'
    | 'contacted'
    | 'qualified'  // Intake confirmed info, applicant is qualified
    | 'applied'    // Applicant submitted full application form
    | 'followup_scheduled'
    | 'application_submitted'
    | 'under_review'
    | 'approved'
    | 'pending_handoff'  // Awaiting case manager review
    | 'disqualified'
    // Stage B: Post-Approval (Case Manager only)
    | 'pending_match'
    | 'meds_started'
    | 'exam_passed'
    | 'embryo_transferred'
    | 'delivered'
    // Archive pseudo-statuses
    | 'archived'
    | 'restored';

export type CaseSource = 'manual' | 'meta' | 'website' | 'referral';

// Status categories for role-based filtering
export const INTAKE_VISIBLE_STATUSES: CaseStatus[] = [
    'new_unread', 'contacted', 'qualified', 'applied',
    'followup_scheduled', 'application_submitted', 'under_review',
    'approved', 'pending_handoff', 'disqualified'
];

export const CASE_MANAGER_ONLY_STATUSES: CaseStatus[] = [
    'pending_match', 'meds_started', 'exam_passed',
    'embryo_transferred', 'delivered'
];

export const HANDOFF_QUEUE_STATUSES: CaseStatus[] = ['pending_handoff'];

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
    is_priority: boolean;
    is_archived: boolean;
    age: number | null;  // Calculated from date_of_birth
    bmi: number | null;  // Calculated from height_ft and weight_lb
    created_at: string;
}

// Full case detail
export interface CaseRead extends CaseListItem {
    assigned_to_user_id: string | null;
    created_by_user_id: string | null;
    owner_type: 'user' | 'queue' | null;  // Salesforce-style ownership
    owner_id: string | null;               // User ID or Queue ID
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

// Status display config - matches backend CaseStatus enum
export const STATUS_CONFIG: Record<CaseStatus, { label: string; color: string }> = {
    // Stage A: Intake Pipeline
    new_unread: { label: 'New', color: 'bg-blue-500' },
    contacted: { label: 'Contacted', color: 'bg-sky-500' },
    qualified: { label: 'Qualified', color: 'bg-lime-500' },
    applied: { label: 'Applied', color: 'bg-emerald-400' },
    followup_scheduled: { label: 'Follow-up Scheduled', color: 'bg-cyan-500' },
    application_submitted: { label: 'Application Submitted', color: 'bg-teal-500' },
    under_review: { label: 'Under Review', color: 'bg-amber-500' },
    approved: { label: 'Approved', color: 'bg-green-500' },
    pending_handoff: { label: 'Pending Handoff', color: 'bg-orange-500' },
    disqualified: { label: 'Disqualified', color: 'bg-red-500' },
    // Stage B: Post-Approval (Case Manager only)
    pending_match: { label: 'Pending Match', color: 'bg-purple-500' },
    meds_started: { label: 'Meds Started', color: 'bg-violet-500' },
    exam_passed: { label: 'Exam Passed', color: 'bg-indigo-500' },
    embryo_transferred: { label: 'Embryo Transferred', color: 'bg-fuchsia-500' },
    delivered: { label: 'Delivered', color: 'bg-emerald-500' },
    // Archive
    archived: { label: 'Archived', color: 'bg-gray-500' },
    restored: { label: 'Restored', color: 'bg-slate-500' },
};
