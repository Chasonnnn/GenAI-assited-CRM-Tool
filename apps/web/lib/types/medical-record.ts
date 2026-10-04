export type MedicalRecordSection =
    | "insurance"
    | "pcp"
    | "lab_clinic"
    | "clinic"
    | "monitoring_clinic"
    | "ob"
    | "delivery_hospital"

export type MedicalRecordSource = "manual" | "import" | "form" | "restore"
export type MedicalRecordStatus = "current" | "past" | "scheduled"

export interface MedicalRecordValues {
    provider_name: string | null
    name: string | null
    address_line1: string | null
    address_line2: string | null
    city: string | null
    state: string | null
    postal: string | null
    phone: string | null
    fax: string | null
    email: string | null
    plan_name: string | null
    policy_number: string | null
    member_id: string | null
    group_number: string | null
    subscriber_name: string | null
    subscriber_dob: string | null
}

export type MedicalRecordField = keyof MedicalRecordValues

export interface MedicalRecordCorrection {
    id: string
    field: MedicalRecordField
    old_value: string | null
    new_value: string | null
    redacted: boolean
    source: MedicalRecordSource
    corrected_by_name: string | null
    corrected_at: string
}

export interface MedicalRecord extends MedicalRecordValues {
    id: string
    section: MedicalRecordSection
    status: MedicalRecordStatus
    effective_date: string | null
    end_date: string | null
    source: MedicalRecordSource
    archived_on: string | null
    archived_by_name: string | null
    revision: number
    created_by_name: string | null
    created_at: string
    corrections: MedicalRecordCorrection[]
}

export interface MedicalRecordListResponse {
    today: string
    records: MedicalRecord[]
}

export type MedicalRecordFieldValues = Partial<MedicalRecordValues>

export interface MedicalRecordCreate extends MedicalRecordFieldValues {
    section: MedicalRecordSection
    effective_date: string
    idempotency_key: string
}

export interface MedicalRecordUpdate extends MedicalRecordFieldValues {
    expected_revision: number
}

export type MedicalRecordOwnerKind = "surrogate" | "donor"

export interface MedicalRecordOwner {
    kind: MedicalRecordOwnerKind
    id: string
}
