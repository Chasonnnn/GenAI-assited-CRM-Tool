"use client"

import {
    ArchiveIcon,
    ArchiveRestoreIcon,
    ArrowLeftIcon,
    CalendarIcon,
    GraduationCapIcon,
    Loader2Icon,
    MailIcon,
    MapPinIcon,
    MoreVerticalIcon,
    PhoneIcon,
    TagIcon,
} from "lucide-react"

import { RelatedMatchesCard } from "@/components/matches/RelatedMatchesCard"
import { RecordAppointmentsCard } from "@/components/records/RecordAppointmentsCard"
import { RecordCorrespondenceCard } from "@/components/records/RecordCorrespondenceCard"
import { useAuth } from "@/lib/auth-context"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import Link from "@/components/app-link"
import { RecordDetailField } from "@/components/RecordDetailField"
import { EntityActivityTimeline } from "@/components/activity/EntityActivityTimeline"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { DonorDocumentsSection } from "@/components/donors/DonorDocumentsSection"
import { DonorOwnershipSection } from "@/components/donors/DonorOwnershipSection"
import { DonorNotesSection } from "@/components/donors/DonorNotesSection"
import { DonorProfilePhoto } from "@/components/donors/DonorProfilePhoto"
import { DonorTasksSection } from "@/components/donors/DonorTasksSection"
import type { PipelineStage } from "@/lib/api/pipelines"
import type { EntityActivity } from "@/lib/api/activity"
import type { TaskListItem } from "@/lib/api/tasks"
import { normalizeDonorHistory } from "@/lib/activity-history"
import { getDonorStageLabel, getDonorStageStyle } from "@/lib/donor-stage-utils"
import { formatDateTime } from "@/lib/formatters"
import {
    getDonorTypeLabel,
    type Donor,
    type DonorStatusHistoryItem,
} from "@/lib/types/donor"

export function DonorDetailSections({
    donor,
    returnTo,
    stages,
    history,
    activities,
    tasks,
    tasksStatus,
    onRetryTasks,
    activityStatus,
    onRetryActivity,
    onEdit,
    onChangeStage,
    onArchive,
    archiveStatus,
    onRestore,
    restoreStatus,
    access,
    currentUserId,
}: {
    donor: Donor
    returnTo: string
    stages: PipelineStage[]
    history: DonorStatusHistoryItem[]
    activities: EntityActivity[]
    tasks: TaskListItem[]
    tasksStatus: "loading" | "error" | "ready"
    onRetryTasks: () => void
    activityStatus: "loading" | "error" | "ready"
    onRetryActivity: () => void
    onEdit: () => void
    onChangeStage: () => void
    onArchive: () => void
    archiveStatus: "idle" | "pending"
    onRestore: () => void
    restoreStatus: "idle" | "pending"
    access: {
        edit: boolean
        archive: boolean
        changeStage: boolean
        viewTasks: boolean
        createTasks: boolean
        deleteAnyNote: boolean
    }
    currentUserId: string | null
}) {
    const { user } = useAuth()
    const permissionsQuery = useEffectivePermissions(user?.user_id ?? null)
    const permissions = permissionsQuery.data?.permissions ?? []
    const hasPermission = (permission: string) => user?.role === "developer" || permissions.includes(permission)
    const {
        edit: canEdit,
        archive: canArchive,
        changeStage: canChangeStage,
        viewTasks: canViewTasks,
        createTasks: canCreateTasks,
        deleteAnyNote: canDeleteAnyNote,
    } = access
    const isArchiving = archiveStatus === "pending"
    const isRestoring = restoreStatus === "pending"
    const hasMenuActions = donor.is_archived ? canArchive : canEdit || canArchive
    return (
        <div className="flex flex-1 flex-col">
            <header className="border-b border-border bg-background/95 backdrop-blur">
                <div className="flex min-h-16 min-w-0 flex-col gap-3 px-6 py-3 lg:flex-row lg:flex-wrap lg:items-center lg:justify-between">
                    <div className="flex min-w-0 items-center gap-4 lg:flex-1">
                        <Link
                            href={returnTo}
                            aria-label="Back to donors"
                            className="inline-flex size-9 shrink-0 items-center justify-center rounded-md border border-input bg-background hover:bg-accent hover:text-accent-foreground"
                        >
                            <ArrowLeftIcon className="size-5" />
                            <span className="sr-only">Back to donors</span>
                        </Link>
                        <DonorProfilePhoto donor={donor} canEdit={canEdit && !donor.is_archived} compact />
                        <div className="min-w-0">
                            <h1 className="truncate text-2xl font-semibold">{donor.full_name}</h1>
                            <p className="truncate text-sm text-muted-foreground">
                                {donor.donor_number} • {getDonorTypeLabel(donor.donor_type)} • {donor.email}
                            </p>
                        </div>
                    </div>
                    <div className="flex w-full min-w-0 max-w-full flex-wrap items-center gap-2 lg:w-auto lg:justify-end">
                        {!donor.is_archived && canChangeStage ? (
                            <Button className="shrink-0 px-2 sm:px-4" variant="outline" onClick={onChangeStage}>Change Stage</Button>
                        ) : null}
                        <Badge
                            className="min-w-0 max-w-full"
                            variant="outline"
                            style={getDonorStageStyle(stages, donor)}
                        >
                            <span className="truncate">{getDonorStageLabel(stages, donor)}</span>
                        </Badge>
                        {donor.is_archived ? <Badge variant="secondary">Archived</Badge> : null}
                        {hasMenuActions ? (
                            <DropdownMenu>
                                <DropdownMenuTrigger
                                    aria-label={`Actions for ${donor.full_name}`}
                                    className="inline-flex size-9 shrink-0 items-center justify-center rounded-md border border-input bg-background hover:bg-accent hover:text-accent-foreground"
                                >
                                    <MoreVerticalIcon className="size-4" aria-hidden="true" />
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                    {!donor.is_archived && canEdit ? (
                                        <DropdownMenuItem onClick={onEdit}>Edit</DropdownMenuItem>
                                    ) : null}
                                    {!donor.is_archived && canEdit && canArchive ? (
                                        <DropdownMenuSeparator />
                                    ) : null}
                                    {!donor.is_archived && canArchive ? (
                                        <DropdownMenuItem onClick={onArchive} disabled={isArchiving}>
                                            {isArchiving ? (
                                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                                            ) : (
                                                <ArchiveIcon className="mr-2 size-4" />
                                            )}
                                            Archive
                                        </DropdownMenuItem>
                                    ) : null}
                                    {donor.is_archived && canArchive ? (
                                        <DropdownMenuItem onClick={onRestore} disabled={isRestoring}>
                                            {isRestoring ? (
                                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                                            ) : (
                                                <ArchiveRestoreIcon className="mr-2 size-4" />
                                            )}
                                            Restore
                                        </DropdownMenuItem>
                                    ) : null}
                                </DropdownMenuContent>
                            </DropdownMenu>
                        ) : null}
                    </div>
                </div>
            </header>

            <div className="min-w-0 flex-1 p-6">
                <div className="mx-auto grid min-w-0 max-w-6xl grid-cols-1 gap-6 lg:grid-cols-3">
                    <section className="min-w-0 space-y-6 lg:col-span-2" aria-label="Donor details">
                        <Card>
                            <CardHeader><CardTitle>Contact Information</CardTitle></CardHeader>
                            <CardContent className="grid gap-4 sm:grid-cols-2">
                                <RecordDetailField icon={MailIcon} label="Email" value={donor.email} />
                                <RecordDetailField icon={PhoneIcon} label="Phone" value={donor.phone} />
                                <RecordDetailField icon={MapPinIcon} label="State" value={donor.state} />
                            </CardContent>
                        </Card>
                        <Card>
                            <CardHeader><CardTitle>Donor Information</CardTitle></CardHeader>
                            <CardContent className="grid gap-4 sm:grid-cols-2">
                                <RecordDetailField icon={GraduationCapIcon} label="Education" value={donor.education} />
                                <RecordDetailField icon={TagIcon} label="Source" value={donor.source} />
                                <RecordDetailField
                                    icon={CalendarIcon}
                                    label="Created"
                                    value={formatDateTime(donor.created_at, "—")}
                                />
                            </CardContent>
                        </Card>
                        <DonorOwnershipSection donor={donor} canEdit={canEdit} />
                        <RelatedMatchesCard key={`matches-${donor.id}`} kind="donor" recordId={donor.id} name={donor.full_name} canView={hasPermission("view_matches")} canPropose={hasPermission("propose_matches")} archived={donor.is_archived} />
                        <RecordAppointmentsCard key={`appointments-${donor.id}`} record={{ kind: "donor", id: donor.id, name: donor.full_name, email: donor.email, phone: donor.phone }} canView={hasPermission("manage_appointments")} canViewMatches={hasPermission("view_matches")} canCreate={canEdit} archived={donor.is_archived} />
                        <RecordCorrespondenceCard key={`correspondence-${donor.id}`} kind="donor" recordId={donor.id} canView={user?.role === "developer"} canEdit={canEdit && !donor.is_archived} />
                        <DonorNotesSection
                            donorId={donor.id}
                            canEdit={canEdit}
                            currentUserId={currentUserId}
                            canDeleteAny={canDeleteAnyNote}
                        />
                        <DonorTasksSection
                            donor={donor}
                            canView={canViewTasks}
                            canCreate={canCreateTasks}
                        />
                        <DonorDocumentsSection donor={donor} canEdit={canEdit} />
                    </section>
                    <aside className="min-w-0 space-y-6" aria-label="Donor activity">
                        <EntityActivityTimeline
                            currentStageId={donor.stage_id}
                            stages={stages}
                            stageHistory={normalizeDonorHistory(history)}
                            activities={activities}
                            tasks={tasks}
                            tasksStatus={tasksStatus}
                            onRetryTasks={onRetryTasks}
                            status={activityStatus}
                            onRetry={onRetryActivity}
                            historyHref={`/donors/${donor.id}/history?return_to=${encodeURIComponent(returnTo)}`}
                        />
                    </aside>
                </div>
            </div>
        </div>
    )
}
