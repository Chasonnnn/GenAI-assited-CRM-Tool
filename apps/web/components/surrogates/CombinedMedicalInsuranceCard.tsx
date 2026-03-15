"use client"

import { useEffect, useMemo, useState } from "react"
import {
    ShieldIcon,
    HospitalIcon,
    BuildingIcon,
    ActivityIcon,
    ChevronDownIcon,
    StethoscopeIcon,
    HeartPulseIcon,
    FlaskConicalIcon,
    PlusIcon,
    PencilIcon,
    PrinterIcon,
    Trash2Icon,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuGroup,
    DropdownMenuItem,
    DropdownMenuSub,
    DropdownMenuSubContent,
    DropdownMenuSubTrigger,
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
    providerField?: string
    nameField?: string
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
            "pcp_address_line2", "pcp_city", "pcp_state", "pcp_postal",
            "pcp_phone", "pcp_fax", "pcp_email",
        ],
        showProviderName: true,
        showClinicName: true,
        providerField: "pcp_provider_name",
        nameField: "pcp_name",
    },
    {
        key: "lab_clinic",
        title: "Lab Clinic",
        icon: <FlaskConicalIcon className="size-4" />,
        prefix: "lab_clinic",
        kind: "medical",
        fields: [
            "lab_clinic_name", "lab_clinic_address_line1", "lab_clinic_address_line2",
            "lab_clinic_city", "lab_clinic_state", "lab_clinic_postal",
            "lab_clinic_phone", "lab_clinic_fax", "lab_clinic_email",
        ],
        nameField: "lab_clinic_name",
    },
    {
        key: "clinic",
        title: "IVF Clinic",
        icon: <BuildingIcon className="size-4" />,
        prefix: "clinic",
        kind: "medical",
        fields: [
            "clinic_name", "clinic_address_line1", "clinic_address_line2",
            "clinic_city", "clinic_state", "clinic_postal",
            "clinic_phone", "clinic_fax", "clinic_email",
        ],
        nameField: "clinic_name",
    },
    {
        key: "monitoring_clinic",
        title: "Monitoring Clinic",
        icon: <ActivityIcon className="size-4" />,
        prefix: "monitoring_clinic",
        kind: "medical",
        fields: [
            "monitoring_clinic_name", "monitoring_clinic_address_line1", "monitoring_clinic_address_line2",
            "monitoring_clinic_city", "monitoring_clinic_state", "monitoring_clinic_postal",
            "monitoring_clinic_phone", "monitoring_clinic_fax", "monitoring_clinic_email",
        ],
        nameField: "monitoring_clinic_name",
    },
    {
        key: "ob",
        title: "OB Provider",
        icon: <StethoscopeIcon className="size-4" />,
        prefix: "ob",
        kind: "medical",
        fields: [
            "ob_provider_name", "ob_clinic_name", "ob_address_line1",
            "ob_address_line2", "ob_city", "ob_state", "ob_postal",
            "ob_phone", "ob_fax", "ob_email",
        ],
        showProviderName: true,
        showClinicName: true,
        providerField: "ob_provider_name",
        nameField: "ob_clinic_name",
    },
    {
        key: "delivery_hospital",
        title: "Delivery Hospital",
        icon: <HospitalIcon className="size-4" />,
        prefix: "delivery_hospital",
        kind: "medical",
        fields: [
            "delivery_hospital_name", "delivery_hospital_address_line1", "delivery_hospital_address_line2",
            "delivery_hospital_city", "delivery_hospital_state", "delivery_hospital_postal",
            "delivery_hospital_phone", "delivery_hospital_fax", "delivery_hospital_email",
        ],
        nameField: "delivery_hospital_name",
    },
]

interface CombinedMedicalInsuranceCardProps {
    surrogateData: SurrogateRead
    onUpdate: (data: Partial<SurrogateUpdatePayload>) => Promise<void>
}

function SectionActionIcon({
    icon,
    tone = "default",
}: {
    icon: React.ReactNode
    tone?: "default" | "destructive"
}) {
    return (
        <span
            className={
                tone === "destructive"
                    ? "flex size-7 items-center justify-center rounded-full bg-destructive/10 text-destructive"
                    : "flex size-7 items-center justify-center rounded-full bg-muted text-muted-foreground"
            }
        >
            {icon}
        </span>
    )
}

export function CombinedMedicalInsuranceCard({ surrogateData, onUpdate }: CombinedMedicalInsuranceCardProps) {
    const [manuallyAdded, setManuallyAdded] = useState<SectionType[]>([])
    const [optimisticallyHiddenSections, setOptimisticallyHiddenSections] = useState<SectionType[]>([])
    const [sectionPendingDelete, setSectionPendingDelete] = useState<SectionType | null>(null)
    const [isDeletingSection, setIsDeletingSection] = useState(false)

    const dataRecord = surrogateData as unknown as Record<string, string | null | undefined>

    const sectionsWithData = useMemo(() => {
        return SECTION_CONFIGS.filter((section) =>
            section.fields.some((f) => {
                const val = dataRecord[f]
                return val !== null && val !== undefined && val !== ""
            })
        ).map((s) => s.key)
    }, [dataRecord])

    useEffect(() => {
        setOptimisticallyHiddenSections((prev) =>
            prev.filter((key) => sectionsWithData.includes(key))
        )
    }, [sectionsWithData])

    const visibleSections = useMemo(() => {
        const visible = new Set([...sectionsWithData, ...manuallyAdded])
        const hidden = new Set(optimisticallyHiddenSections)
        return SECTION_CONFIGS.filter((s) => visible.has(s.key))
            .filter((section) => !hidden.has(section.key))
    }, [sectionsWithData, manuallyAdded, optimisticallyHiddenSections])

    const availableSections = useMemo(() => {
        const visibleKeys = new Set(visibleSections.map((s) => s.key))
        return SECTION_CONFIGS.filter((s) => !visibleKeys.has(s.key))
    }, [visibleSections])

    const deletableSections = visibleSections
    const canEditSections = availableSections.length > 0 || deletableSections.length > 0

    const handleFieldUpdate = async (field: string, value: string | null) => {
        await onUpdate({ [field]: value })
    }

    const handleInsuranceFieldUpdate = (field: string) => async (value: string | null) => {
        await onUpdate({ [field]: value })
    }

    const handleAddSection = (key: SectionType) => {
        setOptimisticallyHiddenSections((prev) => prev.filter((sectionKey) => sectionKey !== key))
        setManuallyAdded((prev) => (prev.includes(key) ? prev : [...prev, key]))
    }

    const handleDeleteSection = async () => {
        if (!sectionPendingDelete) return
        const section = SECTION_CONFIGS.find((item) => item.key === sectionPendingDelete)
        if (!section) return

        setIsDeletingSection(true)
        try {
            const clearedFields = Object.fromEntries(
                section.fields.map((field) => [field, null])
            ) as Partial<SurrogateUpdatePayload>
            await onUpdate(clearedFields)
            setManuallyAdded((prev) => prev.filter((key) => key !== section.key))
            setOptimisticallyHiddenSections((prev) =>
                prev.includes(section.key) ? prev : [...prev, section.key]
            )
            setSectionPendingDelete(null)
        } finally {
            setIsDeletingSection(false)
        }
    }

    return (
        <>
            <Card className="gap-4 py-4">
                <CardHeader className="px-4 pb-2">
                    <div className="flex items-center justify-between gap-3">
                        <CardTitle className="text-base flex items-center gap-2">
                            <HospitalIcon className="size-4" />
                            Medical & Insurance
                        </CardTitle>
                        {canEditSections && (
                            <DropdownMenu>
                                <DropdownMenuTrigger
                                    render={
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            aria-label="Edit Info"
                                            className="group h-8 rounded-full border-border/70 bg-background/90 px-3.5 text-xs font-medium shadow-none transition-colors hover:bg-accent/70 data-[state=open]:bg-accent data-[state=open]:text-accent-foreground"
                                        />
                                    }
                                >
                                    <PencilIcon className="size-3.5 text-muted-foreground transition-colors group-data-[state=open]:text-current" />
                                    Edit Info
                                    <ChevronDownIcon className="ml-0.5 size-3.5 text-muted-foreground transition-all group-data-[state=open]:translate-y-px group-data-[state=open]:text-current" />
                                </DropdownMenuTrigger>
                                <DropdownMenuContent
                                    align="end"
                                    sideOffset={8}
                                    className="w-56 rounded-2xl border border-border/70 bg-background/95 p-1.5 shadow-lg supports-[backdrop-filter]:bg-background/90"
                                >
                                    {availableSections.length > 0 && (
                                        <DropdownMenuGroup>
                                            <DropdownMenuSub>
                                                <DropdownMenuSubTrigger className="rounded-xl px-2.5 py-2 font-medium">
                                                    <SectionActionIcon icon={<PlusIcon className="size-4" />} />
                                                    Add Section
                                                </DropdownMenuSubTrigger>
                                                <DropdownMenuSubContent
                                                    className="w-60 rounded-2xl border border-border/70 bg-background/95 p-1.5 shadow-lg supports-[backdrop-filter]:bg-background/90"
                                                >
                                                    {availableSections.map((section) => (
                                                        <DropdownMenuItem
                                                            key={section.key}
                                                            onClick={() => handleAddSection(section.key)}
                                                            className="rounded-xl px-2.5 py-2"
                                                        >
                                                            <SectionActionIcon icon={section.icon} />
                                                            <span className="font-medium">{section.title}</span>
                                                        </DropdownMenuItem>
                                                    ))}
                                                </DropdownMenuSubContent>
                                            </DropdownMenuSub>
                                        </DropdownMenuGroup>
                                    )}
                                    {deletableSections.length > 0 && (
                                        <DropdownMenuGroup>
                                            <DropdownMenuSub>
                                                <DropdownMenuSubTrigger className="rounded-xl px-2.5 py-2 font-medium text-destructive data-open:bg-destructive/10 data-open:text-destructive focus:bg-destructive/10 focus:text-destructive">
                                                    <SectionActionIcon
                                                        icon={<Trash2Icon className="size-4" />}
                                                        tone="destructive"
                                                    />
                                                    Delete Section
                                                </DropdownMenuSubTrigger>
                                                <DropdownMenuSubContent
                                                    className="w-60 rounded-2xl border border-border/70 bg-background/95 p-1.5 shadow-lg supports-[backdrop-filter]:bg-background/90"
                                                >
                                                    {deletableSections.map((section) => (
                                                        <DropdownMenuItem
                                                            key={section.key}
                                                            onClick={() => setSectionPendingDelete(section.key)}
                                                            variant="destructive"
                                                            className="rounded-xl px-2.5 py-2"
                                                        >
                                                            <SectionActionIcon icon={section.icon} tone="destructive" />
                                                            <span className="font-medium">Delete {section.title}</span>
                                                        </DropdownMenuItem>
                                                    ))}
                                                </DropdownMenuSubContent>
                                            </DropdownMenuSub>
                                        </DropdownMenuGroup>
                                    )}
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
                                        {...(section.providerField ? { providerField: section.providerField } : {})}
                                        {...(section.nameField ? { nameField: section.nameField } : {})}
                                        {...(section.showProviderName !== undefined ? { showProviderName: section.showProviderName } : {})}
                                        {...(section.showClinicName !== undefined ? { showClinicName: section.showClinicName } : {})}
                                    />
                                )
                            )}
                        </div>
                    )}
                </CardContent>
            </Card>

            <AlertDialog
                open={sectionPendingDelete !== null}
                onOpenChange={(open) => {
                    if (!open && !isDeletingSection) {
                        setSectionPendingDelete(null)
                    }
                }}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>
                            Delete {SECTION_CONFIGS.find((section) => section.key === sectionPendingDelete)?.title ?? "section"} section?
                        </AlertDialogTitle>
                        <AlertDialogDescription>
                            This removes the section from the card and clears any saved information for it. You can add the section back later if needed.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={isDeletingSection}>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            variant="destructive"
                            onClick={handleDeleteSection}
                            disabled={isDeletingSection}
                        >
                            Delete Section
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
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
