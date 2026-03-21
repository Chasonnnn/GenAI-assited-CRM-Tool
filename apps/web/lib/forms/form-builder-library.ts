import type { FieldType } from "@/lib/api/forms"
import type { LucideIcon } from "lucide-react"
import {
    CalendarIcon,
    CheckSquareIcon,
    FileIcon,
    HashIcon,
    HomeIcon,
    ListIcon,
    MailIcon,
    PhoneIcon,
    RulerIcon,
    TypeIcon,
} from "lucide-react"

export type BuilderPaletteField = {
    key: string
    label: string
    type: FieldType
    icon: LucideIcon
    helperText?: string
    required?: boolean
    surrogateFieldMapping?: string
    options?: string[]
}

export type BuilderPaletteGroup = {
    id: string
    label: string
    fields: BuilderPaletteField[]
}

const sharedFieldIcons: Record<FieldType, LucideIcon> = {
    text: TypeIcon,
    textarea: TypeIcon,
    email: MailIcon,
    phone: PhoneIcon,
    number: HashIcon,
    date: CalendarIcon,
    select: ListIcon,
    multiselect: CheckSquareIcon,
    radio: CheckSquareIcon,
    checkbox: CheckSquareIcon,
    file: FileIcon,
    address: HomeIcon,
    repeatable_table: ListIcon,
    height: RulerIcon,
}

export const PRESET_FIELD_GROUPS: BuilderPaletteGroup[] = [
    {
        id: "contacts",
        label: "Contacts",
        fields: [
            {
                key: "full_name",
                label: "Full Name",
                type: "text",
                icon: TypeIcon,
                required: true,
                surrogateFieldMapping: "full_name",
            },
            {
                key: "email",
                label: "Email",
                type: "email",
                icon: MailIcon,
                required: true,
                surrogateFieldMapping: "email",
            },
            {
                key: "phone",
                label: "Phone",
                type: "phone",
                icon: PhoneIcon,
                required: true,
                surrogateFieldMapping: "phone",
            },
            {
                key: "state",
                label: "State",
                type: "text",
                icon: HomeIcon,
                surrogateFieldMapping: "state",
            },
        ],
    },
    {
        id: "demographics",
        label: "Demographics",
        fields: [
            {
                key: "date_of_birth",
                label: "Date of Birth",
                type: "date",
                icon: CalendarIcon,
                required: true,
                surrogateFieldMapping: "date_of_birth",
            },
            {
                key: "race",
                label: "Race",
                type: "select",
                icon: ListIcon,
                surrogateFieldMapping: "race",
                options: [
                    "Asian",
                    "Black or African American",
                    "Hispanic or Latino",
                    "Native Hawaiian or Other Pacific Islander",
                    "White",
                    "Other",
                ],
            },
            {
                key: "height_ft",
                label: "Height (ft/in)",
                type: "height",
                icon: RulerIcon,
                surrogateFieldMapping: "height_ft",
            },
            {
                key: "weight_lb",
                label: "Weight (lb)",
                type: "number",
                icon: HashIcon,
                helperText: "Pounds.",
                surrogateFieldMapping: "weight_lb",
            },
        ],
    },
    {
        id: "eligibility",
        label: "Eligibility",
        fields: [
            {
                key: "is_age_eligible",
                label: "Age Eligible",
                type: "radio",
                icon: CheckSquareIcon,
                surrogateFieldMapping: "is_age_eligible",
                options: ["Yes", "No"],
            },
            {
                key: "is_citizen_or_pr",
                label: "US Citizen/PR",
                type: "radio",
                icon: CheckSquareIcon,
                surrogateFieldMapping: "is_citizen_or_pr",
                options: ["Yes", "No"],
            },
            {
                key: "has_child",
                label: "Has Child",
                type: "radio",
                icon: CheckSquareIcon,
                surrogateFieldMapping: "has_child",
                options: ["Yes", "No"],
            },
            {
                key: "is_non_smoker",
                label: "Non-Smoker",
                type: "radio",
                icon: CheckSquareIcon,
                surrogateFieldMapping: "is_non_smoker",
                options: ["Yes", "No"],
            },
            {
                key: "has_surrogate_experience",
                label: "Surrogate Experience",
                type: "radio",
                icon: CheckSquareIcon,
                surrogateFieldMapping: "has_surrogate_experience",
                options: ["Yes", "No"],
            },
            {
                key: "num_deliveries",
                label: "Number of Deliveries",
                type: "number",
                icon: HashIcon,
                surrogateFieldMapping: "num_deliveries",
            },
            {
                key: "num_csections",
                label: "Number of C-Sections",
                type: "number",
                icon: HashIcon,
                surrogateFieldMapping: "num_csections",
            },
        ],
    },
]

export const CUSTOM_FIELD_GROUPS: BuilderPaletteGroup[] = [
    {
        id: "general",
        label: "General",
        fields: [
            { key: "text", label: "Name", type: "text", icon: TypeIcon },
            { key: "textarea", label: "Long Text", type: "textarea", icon: TypeIcon },
            { key: "email", label: "Email", type: "email", icon: MailIcon },
            { key: "phone", label: "Phone", type: "phone", icon: PhoneIcon },
            { key: "number", label: "Number", type: "number", icon: HashIcon },
        ],
    },
    {
        id: "choices",
        label: "Choices",
        fields: [
            { key: "select", label: "Select", type: "select", icon: ListIcon },
            {
                key: "multiselect",
                label: "Multi-Select",
                type: "multiselect",
                icon: CheckSquareIcon,
            },
            { key: "radio", label: "Radio", type: "radio", icon: CheckSquareIcon },
            { key: "checkbox", label: "Checkbox", type: "checkbox", icon: CheckSquareIcon },
        ],
    },
    {
        id: "dates-and-structured",
        label: "Dates and Structured",
        fields: [
            { key: "date", label: "Date", type: "date", icon: CalendarIcon },
            { key: "address", label: "Address", type: "address", icon: HomeIcon },
            { key: "height", label: "Height (ft/in)", type: "height", icon: RulerIcon },
        ],
    },
    {
        id: "uploads-and-tables",
        label: "Uploads and Tables",
        fields: [
            { key: "file", label: "File Upload", type: "file", icon: FileIcon },
            {
                key: "repeatable_table",
                label: "Repeating Table",
                type: "repeatable_table",
                icon: ListIcon,
            },
        ],
    },
]

export function getBuilderFieldIcon(type: string): LucideIcon {
    return sharedFieldIcons[type as FieldType] || TypeIcon
}
