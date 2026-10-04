import type { ReactNode } from "react"
import {
    ActivityIcon,
    BuildingIcon,
    FlaskConicalIcon,
    HeartPulseIcon,
    HospitalIcon,
    ShieldIcon,
    StethoscopeIcon,
} from "lucide-react"

import { formatDate } from "@/lib/formatters"
import type {
    MedicalRecord,
    MedicalRecordField,
    MedicalRecordSection,
} from "@/lib/types/medical-record"
import { parseDateInput } from "@/lib/utils/date"

export interface MedicalRecordFieldConfig {
    key: MedicalRecordField
    label: string
    placeholder: string
    type?: "text" | "tel" | "email" | "date"
    /** Starts a new visual group in the record view. */
    divider?: boolean
    /** City, state and ZIP share one row in the record view. */
    cityStateZip?: boolean
    half?: boolean
}

export interface MedicalRecordSectionConfig {
    key: MedicalRecordSection
    title: string
    noun: string
    icon: ReactNode
    fields: MedicalRecordFieldConfig[]
    /** Changing one of these on the current record asks whether it is a new record. */
    identityFields: MedicalRecordField[]
}

function contactFields(withProvider: boolean): MedicalRecordFieldConfig[] {
    return [
        ...(withProvider
            ? [{ key: "provider_name", label: "Provider", placeholder: "Doctor name" } as const]
            : []),
        { key: "name", label: "Name", placeholder: "Clinic/Hospital name" },
        { key: "address_line1", label: "Address", placeholder: "Street address", divider: true },
        { key: "address_line2", label: "Address 2", placeholder: "Suite, unit, etc." },
        { key: "city", label: "City", placeholder: "City", cityStateZip: true },
        { key: "state", label: "State", placeholder: "XX", cityStateZip: true },
        { key: "postal", label: "ZIP", placeholder: "00000", cityStateZip: true },
        { key: "phone", label: "Phone", placeholder: "Phone", type: "tel", divider: true, half: true },
        { key: "fax", label: "Fax", placeholder: "Fax", type: "tel", half: true },
        { key: "email", label: "Email", placeholder: "Email", type: "email" },
    ]
}

const INSURANCE_FIELDS: MedicalRecordFieldConfig[] = [
    { key: "name", label: "Company", placeholder: "Insurance company", half: true },
    { key: "plan_name", label: "Plan", placeholder: "Plan name", half: true },
    { key: "policy_number", label: "Policy #", placeholder: "Policy number", half: true },
    { key: "member_id", label: "Member ID", placeholder: "Member ID", half: true },
    { key: "group_number", label: "Group #", placeholder: "Group number", half: true },
    { key: "phone", label: "Phone", placeholder: "Phone", type: "tel", half: true },
    { key: "fax", label: "Fax", placeholder: "Fax", type: "tel", half: true },
    { key: "subscriber_name", label: "Subscriber", placeholder: "Subscriber name", divider: true, half: true },
    { key: "subscriber_dob", label: "Subscriber DOB", placeholder: "", type: "date", half: true },
]

export const MEDICAL_RECORD_SECTIONS: MedicalRecordSectionConfig[] = [
    {
        key: "insurance",
        title: "Insurance",
        noun: "insurance policy",
        icon: <ShieldIcon className="size-4" />,
        fields: INSURANCE_FIELDS,
        identityFields: ["name", "plan_name", "policy_number"],
    },
    {
        key: "pcp",
        title: "PCP Provider",
        noun: "PCP provider",
        icon: <HeartPulseIcon className="size-4" />,
        fields: contactFields(true),
        identityFields: ["provider_name", "name"],
    },
    {
        key: "lab_clinic",
        title: "Lab Clinic",
        noun: "lab clinic",
        icon: <FlaskConicalIcon className="size-4" />,
        fields: contactFields(false),
        identityFields: ["name"],
    },
    {
        key: "clinic",
        title: "IVF Clinic",
        noun: "IVF clinic",
        icon: <BuildingIcon className="size-4" />,
        fields: contactFields(false),
        identityFields: ["name"],
    },
    {
        key: "monitoring_clinic",
        title: "Monitoring Clinic",
        noun: "monitoring clinic",
        icon: <ActivityIcon className="size-4" />,
        fields: contactFields(false),
        identityFields: ["name"],
    },
    {
        key: "ob",
        title: "OB Provider",
        noun: "OB provider",
        icon: <StethoscopeIcon className="size-4" />,
        fields: contactFields(true),
        identityFields: ["provider_name", "name"],
    },
    {
        key: "delivery_hospital",
        title: "Delivery Hospital",
        noun: "delivery hospital",
        icon: <HospitalIcon className="size-4" />,
        fields: contactFields(false),
        identityFields: ["name"],
    },
]

export function sectionConfig(section: MedicalRecordSection): MedicalRecordSectionConfig {
    const config = MEDICAL_RECORD_SECTIONS.find((item) => item.key === section)
    if (!config) throw new Error(`Unknown medical record section: ${section}`)
    return config
}

export function fieldLabel(section: MedicalRecordSection, field: MedicalRecordField): string {
    return sectionConfig(section).fields.find((item) => item.key === field)?.label ?? field
}

export function formatRecordDate(value: string | null | undefined): string {
    return value ? formatDate(parseDateInput(value)) : ""
}

export function recordName(record: MedicalRecord): string {
    const parts =
        record.section === "insurance"
            ? [record.name, record.plan_name]
            : [record.provider_name, record.name]
    return parts.filter(Boolean).join(" · ") || "Untitled"
}

export function recordRange(record: MedicalRecord): string {
    if (record.status === "current") {
        return record.effective_date ? `Since ${formatRecordDate(record.effective_date)}` : "Date unknown"
    }
    if (record.status === "scheduled") return `From ${formatRecordDate(record.effective_date)}`
    const start = record.effective_date ? formatRecordDate(record.effective_date) : "Unknown"
    return `${start} – ${formatRecordDate(record.end_date)}`
}

export type RecordStatusLabel = "Current" | "Past" | "Scheduled" | "Archived"

export function recordStatusLabel(record: MedicalRecord): RecordStatusLabel {
    if (record.status === "past" && record.archived_on) return "Archived"
    if (record.status === "current") return "Current"
    if (record.status === "scheduled") return "Scheduled"
    return "Past"
}

/** Records in API order: scheduled first, then newest to oldest. */
export function groupRecordsBySection(records: MedicalRecord[]): Map<MedicalRecordSection, MedicalRecord[]> {
    const grouped = new Map<MedicalRecordSection, MedicalRecord[]>()
    for (const record of records) {
        const list = grouped.get(record.section) ?? []
        list.push(record)
        grouped.set(record.section, list)
    }
    return grouped
}

export function isSectionArchived(records: MedicalRecord[]): boolean {
    return records.length > 0 && records.every((record) => record.status === "past")
}
