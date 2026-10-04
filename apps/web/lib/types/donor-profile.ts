export interface DonorProfile {
    marital_status: string | null
    address_line1: string | null
    address_line2: string | null
    address_city: string | null
    address_state: string | null
    address_postal: string | null
    partner_name: string | null
    partner_date_of_birth: string | null
    partner_email: string | null
    partner_phone: string | null
    partner_address_line1: string | null
    partner_address_line2: string | null
    partner_city: string | null
    partner_state: string | null
    partner_postal: string | null
    date_of_birth: string | null
    race: string | null
    height_ft: number | string | null
    weight_lb: number | null
    education: string | null
    college: string | null
    nicotine: string | null
    cannabis: string | null
    infectious_disease: string | null
    previous_donation: string | null
    ssn_masked: string | null
    partner_ssn_masked: string | null
    eligibility_checklist: DonorChecklistItem[]
}

export type DonorQuestionKey = "education" | "college" | "nicotine" | "cannabis" | "infectious_disease" | "previous_donation"

export interface DonorChecklistItem {
    key: DonorQuestionKey
    label: string
    question: string
    value: string | null
    options: { value: string; label: string }[]
}

export type DonorProfileUpdate = Partial<Omit<DonorProfile, "ssn_masked" | "partner_ssn_masked" | "eligibility_checklist">> & {
    ssn?: string | null
    partner_ssn?: string | null
}
