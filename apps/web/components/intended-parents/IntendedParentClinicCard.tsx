"use client"

import { useEffect, useState } from "react"
import {
    BuildingIcon,
    ChevronDownIcon,
    HospitalIcon,
    PencilIcon,
    PlusIcon,
    Trash2Icon,
} from "lucide-react"
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
import type { IntendedParent, IntendedParentUpdate } from "@/lib/types/intended-parent"

interface IntendedParentClinicCardProps {
    intendedParent: IntendedParent
    onUpdate: (data: IntendedParentUpdate) => Promise<void>
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

export function IntendedParentClinicCard({
    intendedParent,
    onUpdate,
}: IntendedParentClinicCardProps) {
    const [isManuallyAdded, setIsManuallyAdded] = useState(false)
    const [isOptimisticallyHidden, setIsOptimisticallyHidden] = useState(false)
    const [deleteOpen, setDeleteOpen] = useState(false)
    const [isDeletingSection, setIsDeletingSection] = useState(false)

    const handleFieldUpdate = async (field: string, value: string | null) => {
        await onUpdate({ [field]: value } as IntendedParentUpdate)
    }

    const dataRecord = intendedParent as unknown as Record<string, string | null | undefined>
    const hasClinicData = CLINIC_FIELDS.some((field) => {
        const value = dataRecord[field]
        return value !== null && value !== undefined && value !== ""
    })

    useEffect(() => {
        if (!hasClinicData) {
            setIsOptimisticallyHidden(false)
        }
    }, [hasClinicData])

    const isClinicVisible = (hasClinicData || isManuallyAdded) && !isOptimisticallyHidden
    const canAddSection = !isClinicVisible
    const canDeleteSection = isClinicVisible
    const canEditSections = canAddSection || canDeleteSection

    const handleAddSection = () => {
        setIsOptimisticallyHidden(false)
        setIsManuallyAdded(true)
    }

    const handleDeleteSection = async () => {
        setIsDeletingSection(true)
        try {
            const clearedFields = Object.fromEntries(
                CLINIC_FIELDS.map((field) => [field, null])
            ) as IntendedParentUpdate
            await onUpdate(clearedFields)
            setIsManuallyAdded(false)
            setIsOptimisticallyHidden(true)
            setDeleteOpen(false)
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
                                    {canAddSection && (
                                        <DropdownMenuGroup>
                                            <DropdownMenuSub>
                                                <DropdownMenuSubTrigger className="rounded-xl px-2.5 py-2 font-medium">
                                                    <SectionActionIcon icon={<PlusIcon className="size-4" />} />
                                                    Add Section
                                                </DropdownMenuSubTrigger>
                                                <DropdownMenuSubContent
                                                    className="w-60 rounded-2xl border border-border/70 bg-background/95 p-1.5 shadow-lg supports-[backdrop-filter]:bg-background/90"
                                                >
                                                    <DropdownMenuItem
                                                        onClick={handleAddSection}
                                                        className="rounded-xl px-2.5 py-2"
                                                    >
                                                        <SectionActionIcon icon={<BuildingIcon className="size-4" />} />
                                                        <span className="font-medium">IVF Clinic</span>
                                                    </DropdownMenuItem>
                                                </DropdownMenuSubContent>
                                            </DropdownMenuSub>
                                        </DropdownMenuGroup>
                                    )}
                                    {canDeleteSection && (
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
                                                    <DropdownMenuItem
                                                        onClick={() => setDeleteOpen(true)}
                                                        variant="destructive"
                                                        className="rounded-xl px-2.5 py-2"
                                                    >
                                                        <SectionActionIcon
                                                            icon={<BuildingIcon className="size-4" />}
                                                            tone="destructive"
                                                        />
                                                        <span className="font-medium">Delete IVF Clinic</span>
                                                    </DropdownMenuItem>
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
                    {isClinicVisible ? (
                        <MedicalContactSection
                            title="IVF Clinic"
                            icon={<BuildingIcon className="size-4" />}
                            prefix="ip_clinic"
                            data={intendedParent}
                            onUpdate={handleFieldUpdate}
                        />
                    ) : (
                        <p className="py-4 text-center text-sm text-muted-foreground">
                            No medical information added yet.
                        </p>
                    )}
                </CardContent>
            </Card>

            <AlertDialog
                open={deleteOpen}
                onOpenChange={(open) => {
                    if (!open && !isDeletingSection) {
                        setDeleteOpen(false)
                    }
                }}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Delete IVF Clinic section?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This removes the IVF clinic section and clears any saved information for it. You can add it back later if needed.
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
