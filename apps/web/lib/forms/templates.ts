import type {
    FormCreatePayload,
    FormField,
    FormFieldColumn,
    FormFieldCondition,
    FormFieldMappingItem,
    FormFieldOption,
    FormFieldValidation,
    FormSchema,
} from "@/lib/api/forms"

type TemplateFieldOptions = {
    required?: boolean
    helpText?: string
    optionList?: readonly string[]
    showIf?: FormFieldCondition | null
    columns?: FormFieldColumn[]
    minRows?: number | null
    maxRows?: number | null
    mapping?: string
    validation?: FormFieldValidation | null
}

type TemplateColumnOptions = {
    required?: boolean
    optionList?: readonly string[]
    validation?: FormFieldValidation | null
}

export type FormTemplate = {
    id: string
    name: string
    description: string
    badge?: string
    sections: number
    questions: number
    payload: FormCreatePayload
    mappings?: FormFieldMappingItem[]
}

const YES_NO_OPTIONS = ["Yes", "No"] as const
const YES_NO_UNSURE_OPTIONS = ["Yes", "No", "Not sure"] as const
const BLOOD_TYPE_OPTIONS = ["A", "B", "AB", "O"] as const
const RH_FACTOR_OPTIONS = ["Positive", "Negative", "Unknown"] as const
const PREGNANCY_CONDITION_OPTIONS = [
    "Gestational diabetes",
    "Preeclampsia",
    "Preterm labor",
    "Placenta previa",
    "Other complications",
] as const
const DISEASE_OPTIONS = ["HIV", "Hepatitis B", "Hepatitis C", "Herpes", "Syphilis", "Other"] as const
const IP_TYPE_OPTIONS = ["Heterosexual couple", "Same-sex couple", "Single parent", "Not sure"] as const
const COMPLIANCE_NOTICE =
    "By submitting this form, you consent to the collection and use of your information, including health-related details, for eligibility review and care coordination. Access is limited to authorized staff and retained per policy."

const toOptions = (optionList: readonly string[]): FormFieldOption[] =>
    optionList.map((option) => ({
        label: option,
        value: option,
    }))

const buildColumn = (
    key: string,
    label: string,
    type: FormFieldColumn["type"],
    options: TemplateColumnOptions = {},
): FormFieldColumn => ({
    key,
    label,
    type,
    required: options.required ?? false,
    ...(options.optionList ? { options: toOptions(options.optionList) } : {}),
    ...(options.validation ? { validation: options.validation } : {}),
})

const buildField = (
    key: string,
    label: string,
    type: FormField["type"],
    options: TemplateFieldOptions = {},
    mappingCollector?: FormFieldMappingItem[],
): FormField => {
    if (mappingCollector && options.mapping) {
        mappingCollector.push({ field_key: key, surrogate_field: options.mapping })
    }

    return {
        key,
        label,
        type,
        required: options.required ?? false,
        ...(options.optionList ? { options: toOptions(options.optionList) } : {}),
        ...(options.validation ? { validation: options.validation } : {}),
        ...(options.helpText ? { help_text: options.helpText } : {}),
        ...(options.showIf ? { show_if: options.showIf } : {}),
        ...(options.columns ? { columns: options.columns } : {}),
        ...(options.minRows !== undefined ? { min_rows: options.minRows } : {}),
        ...(options.maxRows !== undefined ? { max_rows: options.maxRows } : {}),
    }
}

const createTemplate = (template: Omit<FormTemplate, "sections" | "questions">): FormTemplate => {
    const pages = template.payload.form_schema?.pages ?? []
    const sections = pages.length
    const questions = pages.reduce((total, page) => total + page.fields.length, 0)

    return {
        ...template,
        sections,
        questions,
    }
}

const buildJotformTemplate = (): FormTemplate => {
    const mappings: FormFieldMappingItem[] = []
    const field = (key: string, label: string, type: FormField["type"], options: TemplateFieldOptions = {}) =>
        buildField(key, label, type, options, mappings)

    const pages: FormSchema["pages"] = [
        {
            title: "Surrogate Information",
            fields: [
                field("full_name", "Full Name", "text", {
                    required: true,
                    mapping: "full_name",
                    helpText: "First and last name.",
                }),
                field("date_of_birth", "Date of Birth", "date", {
                    required: true,
                    mapping: "date_of_birth",
                }),
                field("height_ft", "Height (ft)", "number", {
                    helpText: "Feet (e.g., 5.5).",
                    mapping: "height_ft",
                }),
                field("weight_lb", "Weight (lb)", "number", {
                    helpText: "Pounds.",
                    mapping: "weight_lb",
                }),
                field("email", "Email", "email", {
                    required: true,
                    mapping: "email",
                }),
                field("cell_phone", "Cell Phone", "phone", {
                    required: true,
                    mapping: "phone",
                }),
                field("address_line_1", "Street Address", "text", { required: true }),
                field("address_line_2", "Street Address Line 2", "text"),
                field("city", "City", "text", { required: true }),
                field("state", "State / Province", "text", {
                    required: true,
                    mapping: "state",
                }),
                field("postal_code", "Postal / Zip Code", "text", { required: true }),
                field("country", "Country", "text"),
            ],
        },
        {
            title: "Eligibility & Background",
            fields: [
                field("covid_vaccine_received", "Have you received Covid vaccine in the past?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("covid_vaccine_when", "If yes, when?", "date", {
                    helpText: "Date of your most recent vaccine.",
                    showIf: { field_key: "covid_vaccine_received", operator: "equals", value: "Yes" },
                }),
                field("covid_vaccine_willing", "If no, are you willing to receive Covid vaccine?", "radio", {
                    optionList: YES_NO_OPTIONS,
                    showIf: { field_key: "covid_vaccine_received", operator: "equals", value: "No" },
                }),
                field("tattoos_past_year", "Have you received any tattoos in the past year?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("tattoo_last_date", "If yes, date of your last tattoo", "date", {
                    showIf: { field_key: "tattoos_past_year", operator: "equals", value: "Yes" },
                }),
                field("religion_yes_no", "Do you have a religion?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("religion_detail", "If yes, please specify your religion", "text", {
                    showIf: { field_key: "religion_yes_no", operator: "equals", value: "Yes" },
                }),
                field("us_citizen", "Are you a US citizen or permanent resident?", "radio", {
                    required: true,
                    optionList: YES_NO_OPTIONS,
                    mapping: "is_citizen_or_pr",
                }),
                field("race", "What is your race?", "text", { mapping: "race" }),
                field("sexual_orientation", "Sexual Orientation", "text"),
                field("marital_status", "Marital status", "text", {
                    helpText: "Single, married, partnered, divorced, etc.",
                }),
                field("marriage_date", "If married, date of marriage", "date"),
                field("biological_children_count", "How many biological children do you have?", "number", {
                    helpText: "Enter 0 if none.",
                }),
                field("languages_spoken", "What languages do you speak?", "text"),
                field("schedule_flexible", "Is your daily schedule flexible?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("drivers_license", "Do you have a valid driver's license?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("transportation", "Do you have reliable transportation?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("car_insurance", "Do you have car insurance?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("health_insurance_carrier", "Name of health insurance carrier?", "text"),
                field("arrested", "Have you ever been arrested?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("arrested_explain", "If yes, please explain", "textarea", {
                    showIf: { field_key: "arrested", operator: "equals", value: "Yes" },
                }),
                field(
                    "legal_cases_pending",
                    "Are you currently involved in any legal cases that are pending?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
                field("legal_cases_explain", "If yes, please explain", "textarea", {
                    showIf: { field_key: "legal_cases_pending", operator: "equals", value: "Yes" },
                }),
                field(
                    "government_assistance",
                    "Do you receive any government assistance (WIC, Medicaid, Food Stamps, Disability)?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
                field("government_assistance_explain", "If yes, please explain", "textarea", {
                    showIf: { field_key: "government_assistance", operator: "equals", value: "Yes" },
                }),
            ],
        },
        {
            title: "Education & Employment",
            fields: [
                field("education_level", "Highest level of education completed?", "text"),
                field("further_education_plans", "Do you plan on furthering your education?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("further_education_details", "If yes, please explain", "textarea", {
                    showIf: { field_key: "further_education_plans", operator: "equals", value: "Yes" },
                }),
                field("currently_employed", "Are you currently employed?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("employer_title", "If yes, present employer and title", "text", {
                    showIf: { field_key: "currently_employed", operator: "equals", value: "Yes" },
                }),
                field("employment_duration", "How long have you been employed there?", "text", {
                    showIf: { field_key: "currently_employed", operator: "equals", value: "Yes" },
                }),
            ],
        },
        {
            title: "Pregnancy Information",
            fields: [
                buildField(
                    "pregnancy_list",
                    "List of pregnancies",
                    "repeatable_table",
                    {
                        helpText:
                            "Include: own/surrogacy, # babies, delivery date, vaginal/C-section, gender, weight, weeks at birth, complications.",
                        columns: [
                            buildColumn("preg_type", "Type", "select", {
                                required: true,
                                optionList: ["Own", "Surrogacy"],
                            }),
                            buildColumn("babies", "# Babies", "number", { required: true }),
                            buildColumn("delivery_date", "Delivery Date", "date"),
                            buildColumn("delivery_type", "Delivery Type", "select", {
                                optionList: ["Vaginal", "C-Section"],
                            }),
                            buildColumn("gender", "Gender", "text"),
                            buildColumn("weight", "Birth Weight", "text"),
                            buildColumn("weeks", "Weeks at Birth", "number"),
                            buildColumn("complications", "Complications", "text"),
                        ],
                    },
                    mappings,
                ),
                field("had_abortion", "Have you ever had an abortion?", "radio", { optionList: YES_NO_OPTIONS }),
                field("abortion_explain", "If yes, please explain", "textarea", {
                    showIf: { field_key: "had_abortion", operator: "equals", value: "Yes" },
                }),
                field("had_miscarriage", "Have you ever had a miscarriage?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("miscarriage_explain", "If yes, please explain", "textarea", {
                    showIf: { field_key: "had_miscarriage", operator: "equals", value: "Yes" },
                }),
                field(
                    "pregnancy_conditions",
                    "Have you ever experienced the following conditions?",
                    "checkbox",
                    { optionList: PREGNANCY_CONDITION_OPTIONS },
                ),
                field("pregnancy_conditions_explain", "If yes, please explain", "textarea", {
                    showIf: { field_key: "pregnancy_conditions", operator: "is_not_empty", value: "" },
                }),
                field("breastfeeding", "Are you currently breastfeeding?", "radio", { optionList: YES_NO_OPTIONS }),
                field("breastfeeding_stop", "If yes, when do you plan to stop?", "text", {
                    showIf: { field_key: "breastfeeding", operator: "equals", value: "Yes" },
                }),
                field("sexually_active", "Are you sexually active?", "radio", { optionList: YES_NO_OPTIONS }),
                field("birth_control", "Are you using birth control?", "radio", { optionList: YES_NO_OPTIONS }),
                field("birth_control_type", "If yes, what kind?", "text", {
                    showIf: { field_key: "birth_control", operator: "equals", value: "Yes" },
                }),
                field("regular_cycles", "Do you have regular monthly menstrual cycles?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("irregular_cycles_detail", "If no, please specify", "text", {
                    showIf: { field_key: "regular_cycles", operator: "equals", value: "No" },
                }),
                field("last_obgyn_visit", "When did you last see your Ob/Gyn?", "date"),
                field("last_pap_smear", "Date of last Pap Smear and result?", "text"),
                field("reproductive_illnesses", "List any reproductive illness you have experienced", "textarea"),
            ],
        },
        {
            title: "Family Support",
            fields: [
                field("spouse_significant_other", "Do you have a spouse/significant other?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field(
                    "spouse_occupation",
                    "If yes, what is your spouse/significant other's occupation?",
                    "text",
                    { showIf: { field_key: "spouse_significant_other", operator: "equals", value: "Yes" } },
                ),
                field("family_support", "Does your family support your decision to become a surrogate?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("bed_rest_help", "Who would help you if placed on bed rest?", "textarea"),
                field("anticipate_difficulties", "Do you anticipate any difficulties in becoming a surrogate?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("difficulties_explain", "If yes, please explain", "textarea", {
                    showIf: { field_key: "anticipate_difficulties", operator: "equals", value: "Yes" },
                }),
                field("living_conditions", "Describe your current living conditions", "textarea"),
                buildField(
                    "household_members",
                    "List everyone living in household with you, including age and relationship",
                    "repeatable_table",
                    {
                        columns: [
                            buildColumn("member_name", "Name", "text", { required: true }),
                            buildColumn("member_age", "Age", "number", { required: true }),
                            buildColumn("relationship", "Relationship", "text", { required: true }),
                        ],
                    },
                    mappings,
                ),
                field("pets_at_home", "Do you have pets at home?", "radio", { optionList: YES_NO_OPTIONS }),
                field("pets_details", "If yes, what kind?", "text", {
                    showIf: { field_key: "pets_at_home", operator: "equals", value: "Yes" },
                }),
            ],
        },
        {
            title: "Medical Info",
            fields: [
                field("blood_type", "Blood type", "select", { optionList: BLOOD_TYPE_OPTIONS }),
                field("rh_factor", "Rh factor", "select", { optionList: RH_FACTOR_OPTIONS }),
                field("current_weight", "Weight (lb)", "number"),
                field("current_height", "Height (ft)", "number"),
                field("drink_alcohol", "Do you drink alcohol?", "radio", { optionList: YES_NO_OPTIONS }),
                field("drink_alcohol_explain", "If yes, please explain", "textarea", {
                    showIf: { field_key: "drink_alcohol", operator: "equals", value: "Yes" },
                }),
                field("household_smoke", "Does anyone in your household smoke?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("household_smoke_explain", "If yes, please explain", "textarea", {
                    showIf: { field_key: "household_smoke", operator: "equals", value: "Yes" },
                }),
                field("used_illicit_drugs", "Have you ever used illicit drugs?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("used_illicit_drugs_explain", "If yes, please explain", "textarea", {
                    showIf: { field_key: "used_illicit_drugs", operator: "equals", value: "Yes" },
                }),
                field(
                    "used_tobacco_last_6_months",
                    "Have you used tobacco, marijuana or illicit drugs within the past 6 months?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
                field("used_tobacco_last_6_months_explain", "If yes, please explain", "textarea", {
                    showIf: { field_key: "used_tobacco_last_6_months", operator: "equals", value: "Yes" },
                }),
                field("taking_medication", "Are you taking any medication?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("taking_medication_explain", "If yes, please explain", "textarea", {
                    showIf: { field_key: "taking_medication", operator: "equals", value: "Yes" },
                }),
                field("treated_conditions", "Are you being treated for any medical conditions?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("treated_conditions_explain", "If yes, please explain", "textarea", {
                    showIf: { field_key: "treated_conditions", operator: "equals", value: "Yes" },
                }),
                field(
                    "significant_illness_history",
                    "Have you or your immediate family had a history of significant illness or medical condition?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
                field("significant_illness_history_explain", "If yes, please explain", "textarea", {
                    showIf: { field_key: "significant_illness_history", operator: "equals", value: "Yes" },
                }),
                field(
                    "hospitalized_operations",
                    "Have you ever been hospitalized or had any operations (excluding birth)?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
                field("hospitalized_operations_explain", "If yes, please explain", "textarea", {
                    showIf: { field_key: "hospitalized_operations", operator: "equals", value: "Yes" },
                }),
                field("nearest_hospital", "How close are you to nearest hospital? Please list name and city.", "text"),
                field("psychiatric_conditions", "Have you ever been diagnosed or treated for any psychiatric conditions?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("psychiatric_conditions_explain", "If yes, please explain", "textarea", {
                    showIf: { field_key: "psychiatric_conditions", operator: "equals", value: "Yes" },
                }),
                field("depression_anxiety_meds", "Have you ever taken any medication for depression/anxiety?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("depression_anxiety_meds_explain", "If yes, please explain", "textarea", {
                    showIf: { field_key: "depression_anxiety_meds", operator: "equals", value: "Yes" },
                }),
                field(
                    "partner_psychiatric_hospital",
                    "Has your partner/spouse ever been hospitalized for psychiatric illness?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
                field("partner_psychiatric_hospital_explain", "If yes, please explain", "textarea", {
                    showIf: { field_key: "partner_psychiatric_hospital", operator: "equals", value: "Yes" },
                }),
                field("immunized_hep_b", "Have you ever been immunized for Hepatitis B? (past only)", "radio", {
                    optionList: YES_NO_UNSURE_OPTIONS,
                }),
                field("immunized_hep_b_explain", "If yes or unsure, please explain", "textarea", {
                    showIf: { field_key: "immunized_hep_b", operator: "not_equals", value: "No" },
                }),
                field(
                    "diseases_self",
                    "Have you ever been diagnosed with any of the following diseases?",
                    "checkbox",
                    { optionList: DISEASE_OPTIONS },
                ),
                field(
                    "diseases_partner",
                    "Has your partner/spouse ever been diagnosed with any of the following diseases?",
                    "checkbox",
                    { optionList: DISEASE_OPTIONS },
                ),
            ],
        },
        {
            title: "Characteristics",
            fields: [
                field("why_surrogate", "Why do you want to be a surrogate? Message to intended parents?", "textarea"),
                field("personality", "Describe your personality and character", "textarea"),
                field("hobbies", "What are your hobbies, interests, and talents?", "textarea"),
                field("daily_diet", "What is your daily diet?", "textarea"),
            ],
        },
        {
            title: "Decisions",
            fields: [
                field("willing_ip_types", "Will you work with intended parents who are:", "checkbox", {
                    optionList: IP_TYPE_OPTIONS,
                }),
                field(
                    "willing_international",
                    "Would you be willing to work with intended parents from other countries?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
                field("willing_travel_canada", "Would you be willing to travel to Canada?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("willing_ip_hep_b", "Would you be willing to carry for intended parents who carry Hepatitis B?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field(
                    "willing_ip_hep_b_recovered",
                    "Would you be willing to carry for intended parents who do not carry Hepatitis B but have recovered?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
                field("willing_ip_hiv", "Would you be willing to carry for intended parents who have HIV?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("willing_donor", "Would you be willing to carry a child with donor eggs or sperm?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field(
                    "willing_different_religion",
                    "Would you be willing to carry for intended parents of a different religion?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
                field(
                    "relationship_with_ips",
                    "What kind of relationship do you want with intended parents during conception and pregnancy?",
                    "textarea",
                ),
                field("max_embryos_transfer", "Maximum number of embryos you are willing to transfer per cycle", "number"),
                field("willing_twins", "Would you be willing to carry twins if embryo split or two transferred?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field(
                    "terminate_abnormality",
                    "Would you be willing to terminate a pregnancy due to a birth abnormality or deformity?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
                field(
                    "terminate_life_risk",
                    "Would you be willing to terminate a pregnancy if your life or baby's life was in danger?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
                field("reduce_multiple_pregnancy", "Are you okay with reducing multiple pregnancy if it is medically necessary?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("terminate_gender", "Would you be willing to terminate a pregnancy due to gender?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field(
                    "invasive_procedures",
                    "Would you be willing to do any invasive procedures (D&C, Amniocentesis, Chronic Villus Sampling)?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
                field("pump_breast_milk", "Would you be willing to pump breast milk after delivery?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("ip_attend_ob", "Would you be comfortable with intended parents attending OB appointments?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field("delivery_room", "Who are you willing to have in the delivery room?", "textarea"),
                field("agree_ivf_medications", "You will be required to take IVF medications. Do you agree?", "radio", {
                    optionList: YES_NO_OPTIONS,
                }),
                field(
                    "agree_abstain",
                    "Will you abstain from sexual activity while undergoing treatment and throughout pregnancy?",
                    "radio",
                    { optionList: YES_NO_OPTIONS },
                ),
            ],
        },
        {
            title: "Uploads & Signature",
            fields: [
                field("upload_photos", "Upload at least 4 pics of you and your family", "file", {
                    required: true,
                    helpText: "Upload 4+ clear photos.",
                }),
                field("supporting_documents", "Supporting documents (optional)", "file", {
                    helpText: "Upload any additional documents.",
                }),
                field("medical_records", "Medical records (optional)", "file", {
                    helpText: "Upload recent medical records if available.",
                }),
                field("signature_name", "Signature (type full legal name)", "text", { required: true }),
            ],
        },
    ]

    const schema: FormSchema = {
        pages,
        public_title: "Surrogate Intake Form",
        privacy_notice: COMPLIANCE_NOTICE,
    }

    return createTemplate({
        id: "jotform-surrogate-intake",
        name: "Jotform Surrogate Intake",
        description: "Includes uploads and signature",
        badge: "Platform",
        payload: {
            name: "Surrogate Application Form (Official)",
            description: "Template based on the Jotform surrogate intake sample.",
            form_schema: schema,
            max_file_size_bytes: 15 * 1024 * 1024,
            max_file_count: 12,
            allowed_mime_types: ["image/*", "application/pdf"],
        },
        mappings,
    })
}

export const FORM_TEMPLATES: FormTemplate[] = [buildJotformTemplate()]
