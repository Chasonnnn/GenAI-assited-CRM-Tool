import type { DonorType } from "@/lib/types/donor"

export interface DonorFormValues {
    donor_type: DonorType
    full_name: string
    email: string
    phone: string
    state: string
    education: string
}

export const EMPTY_DONOR_FORM_VALUES: DonorFormValues = {
    donor_type: "egg",
    full_name: "",
    email: "",
    phone: "",
    state: "",
    education: "",
}
