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
    insurance_company: string | null
    insurance_plan_name: string | null
    insurance_phone: string | null
    insurance_policy_number: string | null
    insurance_member_id: string | null
    insurance_group_number: string | null
    insurance_subscriber_name: string | null
    insurance_subscriber_dob: string | null
    insurance_fax: string | null
    clinic_name: string | null
    clinic_address_line1: string | null
    clinic_address_line2: string | null
    clinic_city: string | null
    clinic_state: string | null
    clinic_postal: string | null
    clinic_phone: string | null
    clinic_email: string | null
    clinic_fax: string | null
    monitoring_clinic_name: string | null
    monitoring_clinic_address_line1: string | null
    monitoring_clinic_address_line2: string | null
    monitoring_clinic_city: string | null
    monitoring_clinic_state: string | null
    monitoring_clinic_postal: string | null
    monitoring_clinic_phone: string | null
    monitoring_clinic_email: string | null
    monitoring_clinic_fax: string | null
    ob_provider_name: string | null
    ob_clinic_name: string | null
    ob_address_line1: string | null
    ob_address_line2: string | null
    ob_city: string | null
    ob_state: string | null
    ob_postal: string | null
    ob_phone: string | null
    ob_email: string | null
    ob_fax: string | null
    delivery_hospital_name: string | null
    delivery_hospital_address_line1: string | null
    delivery_hospital_address_line2: string | null
    delivery_hospital_city: string | null
    delivery_hospital_state: string | null
    delivery_hospital_postal: string | null
    delivery_hospital_phone: string | null
    delivery_hospital_email: string | null
    delivery_hospital_fax: string | null
    pcp_provider_name: string | null
    pcp_name: string | null
    pcp_address_line1: string | null
    pcp_address_line2: string | null
    pcp_city: string | null
    pcp_state: string | null
    pcp_postal: string | null
    pcp_phone: string | null
    pcp_fax: string | null
    pcp_email: string | null
    lab_clinic_name: string | null
    lab_clinic_address_line1: string | null
    lab_clinic_address_line2: string | null
    lab_clinic_city: string | null
    lab_clinic_state: string | null
    lab_clinic_postal: string | null
    lab_clinic_phone: string | null
    lab_clinic_fax: string | null
    lab_clinic_email: string | null
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
