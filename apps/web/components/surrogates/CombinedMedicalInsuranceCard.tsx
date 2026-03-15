"use client"

import { useState, useMemo } from "react"
import {
    ShieldIcon,
    HospitalIcon,
    BuildingIcon,
    ActivityIcon,
    StethoscopeIcon,
    HeartPulseIcon,
    FlaskConicalIcon,
    PlusIcon,
    PrinterIcon,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { InlineEditField } from "@/components/inline-edit-field"
import { InlineDateField } from "@/components/inline-date-field"
import { MedicalContactSection } from "@/components/surrogates/MedicalContactSection"
import { SurrogateRead } from "@/lib/types/surrogate"
import { SurrogateUpdatePayload } from "@/lib/api/surrogates"

type SectionType = "insurance" | "pcp" | "lab_clinic" | "clinic" | "monitoring_clinic" | "ob" | "delivery_hospital"

interface SectionConfig {
    key: SectionType
    title: string
    icon: React.ReactNode
    prefix: string
    kind: "insurance" | "medical"
    fields: string[]
    showProviderName?: boolean
    showClinicName?: boolean
}

const SECTION_CONFIGS: SectionConfig[] = [
    {
        key: "insurance",
        title: "Insurance",
        icon: <ShieldIcon className="size-4" />,
        prefix: "insurance",
        kind: "insurance",
        fields: [
            "insurance_company", "insurance_plan_name", "insurance_phone",
            "insurance_policy_number", "insurance_member_id", "insurance_group_number",
            "insurance_subscriber_name", "insurance_subscriber_dob", "insurance_fax",
        ],
    },
    {
        key: "pcp",
        title: "PCP Provider",
        icon: <HeartPulseIcon className="size-4" />,
        prefix: "pcp",
        kind: "medical",
        fields: [
            "pcp_provider_name", "pcp_name", "pcp_address_line1",
            "pcp_city", "pcp_phone", "pcp_fax", "pcp_email",
        ],
        showProviderName: true,
        showClinicName: true,
    },
    {
        key: "lab_clinic",
        title: "Lab Clinic",
        icon: <FlaskConicalIcon className="size-4" />,
        prefix: "lab_clinic",
        kind: "medical",
        fields: [
            "lab_clinic_name", "lab_clinic_address_line1",
            "lab_clinic_city", "lab_clinic_phone", "lab_clinic_fax", "lab_clinic_email",
        ],
    },
    {
        key: "clinic",
        title: "IVF Clinic",
        icon: <BuildingIcon className="size-4" />,
        prefix: "clinic",
        kind: "medical",
        fields: [
            "clinic_name", "clinic_address_line1",
            "clinic_city", "clinic_phone", "clinic_fax", "clinic_email",
        ],
    },
    {
        key: "monitoring_clinic",
        title: "Monitoring Clinic",
        icon: <ActivityIcon className="size-4" />,
        prefix: "monitoring_clinic",
        kind: "medical",
        fields: [
            "monitoring_clinic_name", "monitoring_clinic_address_line1",
            "monitoring_clinic_city", "monitoring_clinic_phone", "monitoring_clinic_fax", "monitoring_clinic_email",
        ],
    },
    {
        key: "ob",
        title: "OB Provider",
        icon: <StethoscopeIcon className="size-4" />,
        prefix: "ob",
        kind: "medical",
        fields: [
            "ob_provider_name", "ob_clinic_name", "ob_address_line1",
            "ob_city", "ob_phone", "ob_fax", "ob_email",
        ],
        showProviderName: true,
        showClinicName: true,
    },
    {
        key: "delivery_hospital",
        title: "Delivery Hospital",
        icon: <HospitalIcon className="size-4" />,
        prefix: "delivery_hospital",
        kind: "medical",
        fields: [
            "delivery_hospital_name", "delivery_hospital_address_line1",
            "delivery_hospital_city", "delivery_hospital_phone", "delivery_hospital_fax", "delivery_hospital_email",
        ],
    },
]

const MAX_SECTIONS = 8

interface CombinedMedicalInsuranceCardProps {
    surrogateData: SurrogateRead
    onUpdate: (data: Partial<SurrogateUpdatePayload>) => Promise<void>
}

export function CombinedMedicalInsuranceCard({ surrogateData, onUpdate }: CombinedMedicalInsuranceCardProps) {
    const [manuallyAdded, setManuallyAdded] = useState<SectionType[]>([])

    const dataRecord = surrogateData as unknown as Record<string, string | null | undefined>

    const sectionsWithData = useMemo(() => {
        return SECTION_CONFIGS.filter((section) =>
            section.fields.some((f) => {
                const val = dataRecord[f]
                return val !== null && val !== undefined && val !== ""
            })
        ).map((s) => s.key)
    }, [dataRecord])

    const visibleSections = useMemo(() => {
        const visible = new Set([...sectionsWithData, ...manuallyAdded])
        return SECTION_CONFIGS.filter((s) => visible.has(s.key))
    }, [sectionsWithData, manuallyAdded])

    const availableSections = useMemo(() => {
        const visibleKeys = new Set(visibleSections.map((s) => s.key))
        return SECTION_CONFIGS.filter((s) => !visibleKeys.has(s.key))
    }, [visibleSections])

    const handleFieldUpdate = async (field: string, value: string | null) => {
        await onUpdate({ [field]: value })
    }

    const handleInsuranceFieldUpdate = (field: string) => async (value: string | null) => {
        await onUpdate({ [field]: value })
    }

    const handleAddSection = (key: SectionType) => {
        setManuallyAdded((prev) => [...prev, key])
    }

    return (
        <Card className="gap-4 py-4">
            <CardHeader className="px-4 pb-2">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-base flex items-center gap-2">
                        <HospitalIcon className="size-4" />
                        Medical & Insurance
                    </CardTitle>
                    {availableSections.length > 0 && visibleSections.length < MAX_SECTIONS && (
                        <DropdownMenu>
                            <DropdownMenuTrigger className="inline-flex items-center justify-center rounded-md border border-input bg-background px-2.5 h-7 text-xs gap-1 hover:bg-accent hover:text-accent-foreground">
                                <PlusIcon className="size-3.5" />
                                Add Info
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                                {availableSections.map((section) => (
                                    <DropdownMenuItem
                                        key={section.key}
                                        onClick={() => handleAddSection(section.key)}
                                        className="gap-2"
                                    >
                                        {section.icon}
                                        {section.title}
                                    </DropdownMenuItem>
                                ))}
                            </DropdownMenuContent>
                        </DropdownMenu>
                    )}
                </div>
            </CardHeader>
            <CardContent className="px-4">
                {visibleSections.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-4">
                        No medical or insurance information added yet.
                    </p>
                ) : (
                    <div className="grid gap-4 md:grid-cols-2">
                        {visibleSections.map((section) =>
                            section.kind === "insurance" ? (
                                <InsuranceSection
                                    key={section.key}
                                    surrogateData={surrogateData}
                                    onUpdate={handleInsuranceFieldUpdate}
                                />
                            ) : (
                                <MedicalContactSection
                                    key={section.key}
                                    title={section.title}
                                    icon={section.icon}
                                    prefix={section.prefix}
                                    data={surrogateData}
                                    onUpdate={handleFieldUpdate}
                                    {...(section.showProviderName !== undefined ? { showProviderName: section.showProviderName } : {})}
                                    {...(section.showClinicName !== undefined ? { showClinicName: section.showClinicName } : {})}
                                />
                            )
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

function InsuranceSection({
    surrogateData,
    onUpdate,
}: {
    surrogateData: SurrogateRead
    onUpdate: (field: string) => (value: string | null) => Promise<void>
}) {
    return (
        <div className="space-y-3 p-3 rounded-lg border bg-card">
            <h4 className="text-sm font-medium flex items-center gap-2">
                <ShieldIcon className="size-4" />
                Insurance
            </h4>

            {/* Company & Plan */}
            <div className="grid grid-cols-2 gap-4">
                <div>
                    <span className="text-sm text-muted-foreground">Company:</span>
                    <InlineEditField
                        value={surrogateData.insurance_company}
                        onSave={onUpdate("insurance_company")}
                        placeholder="Insurance company"
                    />
                </div>
                <div>
                    <span className="text-sm text-muted-foreground">Plan:</span>
                    <InlineEditField
                        value={surrogateData.insurance_plan_name}
                        onSave={onUpdate("insurance_plan_name")}
                        placeholder="Plan name"
                    />
                </div>
            </div>

            {/* Policy Details */}
            <div className="grid grid-cols-2 gap-4">
                <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground shrink-0">Policy #:</span>
                    <InlineEditField
                        value={surrogateData.insurance_policy_number}
                        onSave={onUpdate("insurance_policy_number")}
                        placeholder="Policy number"
                    />
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground shrink-0">Member ID:</span>
                    <InlineEditField
                        value={surrogateData.insurance_member_id}
                        onSave={onUpdate("insurance_member_id")}
                        placeholder="Member ID"
                    />
                </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
                <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground shrink-0">Group #:</span>
                    <InlineEditField
                        value={surrogateData.insurance_group_number}
                        onSave={onUpdate("insurance_group_number")}
                        placeholder="Group number"
                    />
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground shrink-0">Phone:</span>
                    <InlineEditField
                        value={surrogateData.insurance_phone}
                        onSave={onUpdate("insurance_phone")}
                        type="tel"
                        placeholder="Insurance phone"
                    />
                </div>
            </div>

            {/* Fax */}
            <div className="flex items-center gap-2">
                <PrinterIcon className="size-3.5 text-muted-foreground shrink-0" />
                <InlineEditField
                    value={(surrogateData as unknown as Record<string, string | null>).insurance_fax ?? null}
                    onSave={onUpdate("insurance_fax")}
                    type="tel"
                    placeholder="Fax"
                />
            </div>

            {/* Subscriber Info */}
            <div className="border-t pt-3 mt-3">
                <h4 className="text-sm font-medium mb-2">Subscriber</h4>
                <div className="grid grid-cols-2 gap-4">
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground shrink-0">Name:</span>
                        <InlineEditField
                            value={surrogateData.insurance_subscriber_name}
                            onSave={onUpdate("insurance_subscriber_name")}
                            placeholder="Subscriber name"
                        />
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground shrink-0">DOB:</span>
                        <InlineDateField
                            value={surrogateData.insurance_subscriber_dob}
                            onSave={onUpdate("insurance_subscriber_dob")}
                            label="Subscriber date of birth"
                            placeholder="Set DOB"
                        />
                    </div>
                </div>
            </div>
        </div>
    )
}
