"use client"

import { useMemo, useState } from "react"
import {
    BuildingIcon,
    ChevronDownIcon,
    DnaIcon,
    HospitalIcon,
    PencilIcon,
    PlusIcon,
    Trash2Icon,
} from "lucide-react"
import { InlineEditField } from "@/components/inline-edit-field"
import { MedicalContactSection } from "@/components/surrogates/MedicalContactSection"
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
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import type { IntendedParent, IntendedParentUpdate } from "@/lib/types/intended-parent"

type MedicalSectionKey = "clinic" | "embryo"
type SelectOption = {
    value: string
    label: string
}

interface SectionConfig {
    key: MedicalSectionKey
    title: string
    icon: React.ReactNode
    fields: Array<keyof IntendedParentUpdate>
}

const CLINIC_FIELDS: Array<keyof IntendedParentUpdate> = [
    "ip_clinic_name",
    "ip_clinic_address_line1",
    "ip_clinic_address_line2",
    "ip_clinic_city",
    "ip_clinic_state",
    "ip_clinic_postal",
    "ip_clinic_phone",
    "ip_clinic_fax",
    "ip_clinic_email",
]

const EMBRYO_FIELDS: Array<keyof IntendedParentUpdate> = [
    "embryo_count",
    "pgs_tested",
    "egg_source",
    "sperm_source",
]

const SECTION_CONFIGS: SectionConfig[] = [
    {
        key: "clinic",
        title: "IVF Clinic",
        icon: <BuildingIcon className="size-4" />,
        fields: CLINIC_FIELDS,
    },
    {
        key: "embryo",
        title: "Embryo Status",
        icon: <DnaIcon className="size-4" />,
        fields: EMBRYO_FIELDS,
    },
]

const EGG_SOURCE_OPTIONS: SelectOption[] = [
    { value: "intended_mother", label: "Intended Mother" },
    { value: "egg_donor", label: "Egg Donor" },
]

const SPERM_SOURCE_OPTIONS: SelectOption[] = [
    { value: "intended_father", label: "Intended Father" },
    { value: "sperm_donor", label: "Sperm Donor" },
]

const PGS_TESTED_OPTIONS: SelectOption[] = [
    { value: "yes", label: "Yes" },
    { value: "no", label: "No" },
]

interface IntendedParentClinicCardProps {
    intendedParent: IntendedParent
    onUpdate: (data: IntendedParentUpdate) => Promise<void>
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

function SelectField({
    value,
    label,
    placeholder = "Not set",
    options,
    onSave,
}: {
    value: string | null
    label: string
    placeholder?: string
    options: SelectOption[]
    onSave: (value: string | null) => Promise<void>
}) {
    const [isSaving, setIsSaving] = useState(false)
    const normalizedValue = value ?? "__none__"

    return (
        <Select
            key={normalizedValue}
            defaultValue={normalizedValue}
            onValueChange={async (nextValue) => {
                const nextStoredValue = nextValue === "__none__" ? null : nextValue
                setIsSaving(true)
                try {
                    await onSave(nextStoredValue)
                } finally {
                    setIsSaving(false)
                }
            }}
            disabled={isSaving}
        >
            <SelectTrigger aria-label={label} className="h-8 w-[180px]">
                <SelectValue placeholder={placeholder}>
                    {(currentValue: string | null) =>
                        options.find((option) => option.value === currentValue)?.label ?? placeholder
                    }
                </SelectValue>
            </SelectTrigger>
            <SelectContent>
                <SelectItem value="__none__">Not set</SelectItem>
                {options.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                        {option.label}
                    </SelectItem>
                ))}
            </SelectContent>
        </Select>
    )
}

function EmbryoStatusSection({
    intendedParent,
    onUpdate,
}: {
    intendedParent: IntendedParent
    onUpdate: (data: IntendedParentUpdate) => Promise<void>
}) {
    return (
        <div className="space-y-3 rounded-lg border bg-card p-3">
            <h4 className="flex items-center gap-2 text-sm font-medium">
                <DnaIcon className="size-4" />
                Embryo Status
            </h4>

            <div className="flex flex-wrap items-center gap-2">
                <span className="w-32 shrink-0 text-sm text-muted-foreground">Number of embryos:</span>
                <InlineEditField
                    value={intendedParent.embryo_count?.toString() ?? undefined}
                    onSave={async (value) => {
                        const trimmed = value.trim()
                        await onUpdate({
                            embryo_count: trimmed ? Number.parseInt(trimmed, 10) : null,
                        })
                    }}
                    placeholder="Not set"
                    label="Number of embryos"
                    validate={(value) => {
                        const trimmed = value.trim()
                        if (!trimmed) return null
                        return /^\d+$/.test(trimmed) ? null : "Enter a whole number"
                    }}
                />
            </div>

            <div className="flex flex-wrap items-center gap-2">
                <span className="w-32 shrink-0 text-sm text-muted-foreground">PGS tested:</span>
                <SelectField
                    value={
                        intendedParent.pgs_tested == null
                            ? null
                            : intendedParent.pgs_tested
                              ? "yes"
                              : "no"
                    }
                    label="PGS tested"
                    options={PGS_TESTED_OPTIONS}
                    onSave={async (value) => {
                        await onUpdate({
                            pgs_tested:
                                value == null ? null : value === "yes",
                        })
                    }}
                />
            </div>

            <div className="flex flex-wrap items-center gap-2">
                <span className="w-32 shrink-0 text-sm text-muted-foreground">Egg source:</span>
                <SelectField
                    value={intendedParent.egg_source}
                    label="Egg source"
                    options={EGG_SOURCE_OPTIONS}
                    onSave={async (value) => {
                        await onUpdate({
                            egg_source: value as IntendedParent["egg_source"],
                        })
                    }}
                />
            </div>

            <div className="flex flex-wrap items-center gap-2">
                <span className="w-32 shrink-0 text-sm text-muted-foreground">Sperm source:</span>
                <SelectField
                    value={intendedParent.sperm_source}
                    label="Sperm source"
                    options={SPERM_SOURCE_OPTIONS}
                    onSave={async (value) => {
                        await onUpdate({
                            sperm_source: value as IntendedParent["sperm_source"],
                        })
                    }}
                />
            </div>
        </div>
    )
}

export function IntendedParentClinicCard({
    intendedParent,
    onUpdate,
}: IntendedParentClinicCardProps) {
    const [manuallyAddedSections, setManuallyAddedSections] = useState<MedicalSectionKey[]>([])
    const [optimisticallyHiddenSections, setOptimisticallyHiddenSections] = useState<MedicalSectionKey[]>([])
    const [deleteTarget, setDeleteTarget] = useState<MedicalSectionKey | null>(null)
    const [isDeletingSection, setIsDeletingSection] = useState(false)

    const dataRecord = intendedParent as unknown as Record<string, string | number | boolean | null | undefined>

    const sectionsWithData = useMemo(() => {
        return SECTION_CONFIGS.filter((section) =>
            section.fields.some((field) => {
                const value = dataRecord[field]
                return value !== null && value !== undefined && value !== ""
            })
        ).map((section) => section.key)
    }, [dataRecord])

    const visibleSections = useMemo(() => {
        const visibleKeys = new Set([...sectionsWithData, ...manuallyAddedSections])
        const hiddenKeys = new Set(
            optimisticallyHiddenSections.filter((sectionKey) => sectionsWithData.includes(sectionKey))
        )
        return SECTION_CONFIGS.filter((section) => visibleKeys.has(section.key)).filter(
            (section) => !hiddenKeys.has(section.key)
        )
    }, [manuallyAddedSections, optimisticallyHiddenSections, sectionsWithData])

    const availableSections = useMemo(() => {
        const visibleKeys = new Set(visibleSections.map((section) => section.key))
        return SECTION_CONFIGS.filter((section) => !visibleKeys.has(section.key))
    }, [visibleSections])

    const canEditSections = availableSections.length > 0 || visibleSections.length > 0

    const handleAddSection = (sectionKey: MedicalSectionKey) => {
        setOptimisticallyHiddenSections((previous) =>
            previous.filter((currentKey) => currentKey !== sectionKey)
        )
        setManuallyAddedSections((previous) =>
            previous.includes(sectionKey) ? previous : [...previous, sectionKey]
        )
    }

    const handleDeleteSection = async () => {
        if (!deleteTarget) return
        const targetSection = SECTION_CONFIGS.find((section) => section.key === deleteTarget)
        if (!targetSection) return

        setIsDeletingSection(true)
        try {
            const clearedFields = Object.fromEntries(
                targetSection.fields.map((field) => [field, null])
            ) as IntendedParentUpdate
            await onUpdate(clearedFields)
            setManuallyAddedSections((previous) =>
                previous.filter((sectionKey) => sectionKey !== targetSection.key)
            )
            setOptimisticallyHiddenSections((previous) =>
                previous.includes(targetSection.key)
                    ? previous
                    : [...previous, targetSection.key]
            )
            setDeleteTarget(null)
        } finally {
            setIsDeletingSection(false)
        }
    }

    return (
        <>
            <Card className="gap-4 py-4">
                <CardHeader className="px-4 pb-2">
                    <div className="flex items-center justify-between gap-3">
                        <CardTitle className="flex items-center gap-2 text-base">
                            <HospitalIcon className="size-4" />
                            Medical Information
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
                                                <DropdownMenuSubContent className="w-60 rounded-2xl border border-border/70 bg-background/95 p-1.5 shadow-lg supports-[backdrop-filter]:bg-background/90">
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
                                    {visibleSections.length > 0 && (
                                        <DropdownMenuGroup>
                                            <DropdownMenuSub>
                                                <DropdownMenuSubTrigger className="rounded-xl px-2.5 py-2 font-medium text-destructive data-open:bg-destructive/10 data-open:text-destructive focus:bg-destructive/10 focus:text-destructive">
                                                    <SectionActionIcon
                                                        icon={<Trash2Icon className="size-4" />}
                                                        tone="destructive"
                                                    />
                                                    Delete Section
                                                </DropdownMenuSubTrigger>
                                                <DropdownMenuSubContent className="w-60 rounded-2xl border border-border/70 bg-background/95 p-1.5 shadow-lg supports-[backdrop-filter]:bg-background/90">
                                                    {visibleSections.map((section) => (
                                                        <DropdownMenuItem
                                                            key={section.key}
                                                            onClick={() => setDeleteTarget(section.key)}
                                                            variant="destructive"
                                                            className="rounded-xl px-2.5 py-2"
                                                        >
                                                            <SectionActionIcon
                                                                icon={section.icon}
                                                                tone="destructive"
                                                            />
                                                            <span className="font-medium">
                                                                Delete {section.title}
                                                            </span>
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
                    {visibleSections.length > 0 ? (
                        <div
                            data-testid="ip-medical-sections-grid"
                            className="grid items-start gap-4 md:grid-cols-2"
                        >
                            {visibleSections.map((section) => {
                                if (section.key === "clinic") {
                                    return (
                                        <MedicalContactSection
                                            key={section.key}
                                            title="IVF Clinic"
                                            icon={<BuildingIcon className="size-4" />}
                                            prefix="ip_clinic"
                                            data={intendedParent}
                                            onUpdate={async (field, value) => {
                                                await onUpdate({
                                                    [field]: value,
                                                } as IntendedParentUpdate)
                                            }}
                                        />
                                    )
                                }

                                return (
                                    <EmbryoStatusSection
                                        key={section.key}
                                        intendedParent={intendedParent}
                                        onUpdate={onUpdate}
                                    />
                                )
                            })}
                        </div>
                    ) : (
                        <p className="py-4 text-center text-sm text-muted-foreground">
                            No medical information added yet.
                        </p>
                    )}
                </CardContent>
            </Card>

            <AlertDialog
                open={deleteTarget !== null}
                onOpenChange={(open) => {
                    if (!open && !isDeletingSection) {
                        setDeleteTarget(null)
                    }
                }}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>
                            Delete {SECTION_CONFIGS.find((section) => section.key === deleteTarget)?.title ?? "section"}?
                        </AlertDialogTitle>
                        <AlertDialogDescription>
                            This removes the section and clears any saved information for it. You can add it back later if needed.
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
