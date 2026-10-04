"use client"

import { useState } from "react"
import { ArchiveIcon, ChevronDownIcon, HospitalIcon, Loader2Icon, PencilIcon, PlusIcon } from "lucide-react"

import { MedicalRecordSectionBlock } from "@/components/medical-records/MedicalRecordSectionBlock"
import {
    MEDICAL_RECORD_SECTIONS,
    groupRecordsBySection,
    isSectionArchived,
    sectionConfig,
} from "@/components/medical-records/medical-record-sections"
import { RecordEditingContext, useRecordEditing } from "@/components/records/RecordEditingContext"
import {
    AlertDialog,
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
    DropdownMenuLabel,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Skeleton } from "@/components/ui/skeleton"
import { toast } from "@/components/ui/toast"
import {
    useArchiveMedicalRecord,
    useMedicalRecords,
    useRestoreMedicalRecordSection,
} from "@/lib/hooks/use-medical-records"
import type { MedicalRecordOwner, MedicalRecordSection } from "@/lib/types/medical-record"

const MENU_ITEM_ICON_CLASS = "flex size-7 items-center justify-center rounded-full bg-muted text-muted-foreground"

function CardShell({ children, action }: { children: React.ReactNode; action?: React.ReactNode }) {
    return (
        <Card className="gap-4 py-4">
            <CardHeader className="px-4 pb-2">
                <div className="flex items-center justify-between gap-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                        <HospitalIcon className="size-4" />
                        Medical & Insurance
                    </CardTitle>
                    {action}
                </div>
            </CardHeader>
            <CardContent className="px-4">{children}</CardContent>
        </Card>
    )
}

export function MedicalRecordsCard({ owner, readOnly = false }: { owner: MedicalRecordOwner; readOnly?: boolean }) {
    const canEdit = useRecordEditing() && !readOnly
    const query = useMedicalRecords(owner)
    const archiveRecord = useArchiveMedicalRecord(owner)
    const restoreSection = useRestoreMedicalRecordSection(owner)
    const [addedSections, setAddedSections] = useState<MedicalRecordSection[]>([])
    const [pendingArchive, setPendingArchive] = useState<MedicalRecordSection | null>(null)
    const [archiveError, setArchiveError] = useState<string | null>(null)
    const [showArchived, setShowArchived] = useState(false)
    const [restoreKeys] = useState(() => new Map<MedicalRecordSection, string>())

    if (query.isLoading) {
        return (
            <CardShell>
                <div className="grid gap-4 md:grid-cols-2" aria-busy="true">
                    <Skeleton className="h-40" />
                    <Skeleton className="h-40" />
                </div>
            </CardShell>
        )
    }

    if (query.isError || !query.data) {
        return (
            <CardShell>
                <div className="flex flex-col items-center gap-2 py-4 text-sm">
                    <p className="text-muted-foreground">Couldn't load medical and insurance records.</p>
                    <Button type="button" size="sm" variant="outline" onClick={() => void query.refetch()}>
                        Retry
                    </Button>
                </div>
            </CardShell>
        )
    }

    const { today, records } = query.data
    const bySection = groupRecordsBySection(records)
    const recordsFor = (section: MedicalRecordSection) => bySection.get(section) ?? []

    const activeSections = MEDICAL_RECORD_SECTIONS.filter((config) => {
        const sectionRecords = recordsFor(config.key)
        return (sectionRecords.length > 0 && !isSectionArchived(sectionRecords)) || addedSections.includes(config.key)
    })
    const archivedSections = MEDICAL_RECORD_SECTIONS.filter(
        (config) => isSectionArchived(recordsFor(config.key)) && !addedSections.includes(config.key),
    )
    const missingSections = MEDICAL_RECORD_SECTIONS.filter((config) => !activeSections.includes(config))
    const archivableSections = activeSections.filter((config) =>
        recordsFor(config.key).some((record) => record.status === "current"),
    )

    const removeAdded = (section: MedicalRecordSection) =>
        setAddedSections((prev) => prev.filter((key) => key !== section))

    const handleArchive = async () => {
        if (!pendingArchive) return
        const current = recordsFor(pendingArchive).find((record) => record.status === "current")
        if (!current) return
        setArchiveError(null)
        try {
            await archiveRecord.mutateAsync({ recordId: current.id, expectedRevision: current.revision })
        } catch (error) {
            setArchiveError(error instanceof Error ? error.message : "Couldn't archive this section. Try again.")
            return
        }
        toast.success(`${sectionConfig(pendingArchive).title} archived`)
        setPendingArchive(null)
    }

    const handleRestore = async (section: MedicalRecordSection) => {
        const key = restoreKeys.get(section) ?? crypto.randomUUID()
        restoreKeys.set(section, key)
        try {
            await restoreSection.mutateAsync({ section, idempotencyKey: key })
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Couldn't restore this section. Try again.")
            return
        }
        restoreKeys.delete(section)
        toast.success(`${sectionConfig(section).title} restored`)
    }

    const editMenu =
        canEdit && (missingSections.length > 0 || archivableSections.length > 0) ? (
            <DropdownMenu>
                <DropdownMenuTrigger
                    render={
                        <Button
                            variant="outline"
                            size="sm"
                            aria-label="Edit Info"
                            className="group h-8 rounded-full border-border/70 bg-background/90 px-3.5 text-xs font-medium shadow-none transition-colors hover:bg-accent/70 data-popup-open:bg-accent data-popup-open:text-accent-foreground"
                        />
                    }
                >
                    <PencilIcon className="size-3.5 text-muted-foreground transition-colors group-data-popup-open:text-current" />
                    Edit Info
                    <ChevronDownIcon className="ml-0.5 size-3.5 text-muted-foreground transition-all group-data-popup-open:translate-y-px group-data-popup-open:text-current" />
                </DropdownMenuTrigger>
                <DropdownMenuContent
                    align="end"
                    sideOffset={8}
                    className="w-60 rounded-2xl border border-border/70 bg-background/95 p-1.5 shadow-lg supports-[backdrop-filter]:bg-background/90"
                >
                    {missingSections.length > 0 && (
                        <DropdownMenuGroup>
                            <DropdownMenuLabel className="flex items-center gap-1.5">
                                <PlusIcon className="size-3.5" />
                                Add section
                            </DropdownMenuLabel>
                            {missingSections.map((config) => (
                                <DropdownMenuItem
                                    key={config.key}
                                    className="rounded-xl px-2.5 py-2"
                                    onClick={() => setAddedSections((prev) => [...prev, config.key])}
                                >
                                    <span className={MENU_ITEM_ICON_CLASS}>{config.icon}</span>
                                    <span className="mr-auto font-medium">{config.title}</span>
                                    {archivedSections.includes(config) && (
                                        <span className="text-xs text-muted-foreground">Archived</span>
                                    )}
                                </DropdownMenuItem>
                            ))}
                        </DropdownMenuGroup>
                    )}
                    {archivableSections.length > 0 && (
                        <DropdownMenuGroup>
                            <DropdownMenuLabel className="flex items-center gap-1.5">
                                <ArchiveIcon className="size-3.5" />
                                Archive section
                            </DropdownMenuLabel>
                            {archivableSections.map((config) => (
                                <DropdownMenuItem
                                    key={config.key}
                                    className="rounded-xl px-2.5 py-2"
                                    onClick={() => {
                                        setArchiveError(null)
                                        setPendingArchive(config.key)
                                    }}
                                >
                                    <span className={MENU_ITEM_ICON_CLASS}>{config.icon}</span>
                                    <span className="font-medium">{config.title}</span>
                                </DropdownMenuItem>
                            ))}
                        </DropdownMenuGroup>
                    )}
                </DropdownMenuContent>
            </DropdownMenu>
        ) : null

    return (
        <RecordEditingContext value={canEdit}>
            <CardShell action={editMenu}>
                {activeSections.length === 0 ? (
                    <p className="py-4 text-center text-sm text-muted-foreground">
                        No medical or insurance information added yet.
                    </p>
                ) : (
                    <div className="grid gap-4 md:grid-cols-2">
                        {activeSections.map((config) => {
                            const sectionRecords = recordsFor(config.key)
                            const startInForm = addedSections.includes(config.key)
                            return (
                                <MedicalRecordSectionBlock
                                    key={`${config.key}:${startInForm ? "new" : "view"}`}
                                    owner={owner}
                                    config={config}
                                    records={sectionRecords}
                                    today={today}
                                    canEdit={canEdit}
                                    startInForm={startInForm}
                                    onFormClosed={() => removeAdded(config.key)}
                                />
                            )
                        })}
                    </div>
                )}
                {archivedSections.length > 0 && (
                    <div className="mt-4 flex flex-col gap-3 border-t pt-3">
                        <Button
                            type="button"
                            variant="link"
                            className="h-auto w-fit gap-1 p-0 font-normal text-muted-foreground"
                            aria-expanded={showArchived}
                            onClick={() => setShowArchived((value) => !value)}
                        >
                            Archived sections ({archivedSections.length})
                            <ChevronDownIcon className={showArchived ? "size-3.5 rotate-180" : "size-3.5"} />
                        </Button>
                        {showArchived && (
                            <div className="grid gap-4 md:grid-cols-2">
                                {archivedSections.map((config) => (
                                    <MedicalRecordSectionBlock
                                        key={config.key}
                                        owner={owner}
                                        config={config}
                                        records={recordsFor(config.key)}
                                        today={today}
                                        canEdit={canEdit}
                                        archived
                                        onRestore={() => void handleRestore(config.key)}
                                        isRestoring={restoreSection.isPending && restoreSection.variables?.section === config.key}
                                    />
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </CardShell>

            <AlertDialog
                open={pendingArchive !== null}
                onOpenChange={(open) => {
                    if (!open && !archiveRecord.isPending) setPendingArchive(null)
                }}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>
                            Archive {pendingArchive ? sectionConfig(pendingArchive).title : "section"}?
                        </AlertDialogTitle>
                        <AlertDialogDescription>
                            The current record ends today. Its history stays under Archived sections.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    {archiveError && (
                        <p role="alert" className="text-sm text-destructive">
                            {archiveError}
                        </p>
                    )}
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={archiveRecord.isPending}>Cancel</AlertDialogCancel>
                        <Button type="button" onClick={() => void handleArchive()} disabled={archiveRecord.isPending}>
                            {archiveRecord.isPending && <Loader2Icon className="size-3.5 animate-spin" />}
                            {archiveRecord.isPending ? "Archiving" : "Archive"}
                        </Button>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </RecordEditingContext>
    )
}
