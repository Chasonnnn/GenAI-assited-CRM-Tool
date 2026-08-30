"use client"

import {
    ActivityIcon,
    ArchiveIcon,
    ArchiveRestoreIcon,
    ArrowLeftIcon,
    ArrowRightIcon,
    CalendarIcon,
    GraduationCapIcon,
    Loader2Icon,
    MailIcon,
    MapPinIcon,
    MoreVerticalIcon,
    PhoneIcon,
    TagIcon,
} from "lucide-react"

import Link from "@/components/app-link"
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
import { DonorNotesSection } from "@/components/donors/DonorNotesSection"
import { DonorProfilePhoto } from "@/components/donors/DonorProfilePhoto"
import { DonorTasksSection } from "@/components/donors/DonorTasksSection"
import type { PipelineStage } from "@/lib/api/pipelines"
import { getDonorStageLabel, getDonorStageStyle } from "@/lib/donor-stage-utils"
import { formatDateTime } from "@/lib/formatters"
import {
    getDonorTypeLabel,
    type Donor,
    type DonorStatusHistoryItem,
} from "@/lib/types/donor"

function DetailRow({
    icon: Icon,
    label,
    value,
}: {
    icon: typeof MailIcon
    label: string
    value: string | null
}) {
    return (
        <div className="flex items-start gap-3">
            <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <div className="min-w-0">
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="break-words text-sm font-medium">{value || "—"}</p>
            </div>
        </div>
    )
}

function DonorActivityTimeline({
    stages,
    history,
    historyStatus,
    onRetry,
}: {
    stages: PipelineStage[]
    history: DonorStatusHistoryItem[]
    historyStatus: "loading" | "error" | "ready"
    onRetry: () => void
}) {
    return (
        <Card className="gap-4 py-4">
            <CardHeader className="px-4 pb-2">
                <CardTitle className="flex items-center gap-2 text-base">
                    <ActivityIcon className="size-4" aria-hidden="true" />
                    <h2>Activity</h2>
                </CardTitle>
            </CardHeader>
            <CardContent className="px-4">
                {historyStatus === "loading" ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
                        <Loader2Icon className="size-4 animate-spin" />
                        Loading activity…
                    </div>
                ) : historyStatus === "error" ? (
                    <div className="space-y-3">
                        <p className="text-sm text-destructive">Failed to load activity.</p>
                        <Button variant="outline" size="sm" onClick={onRetry}>Retry</Button>
                    </div>
                ) : history.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No activity yet.</p>
                ) : (
                    <ol className="space-y-4" aria-label="Donor stage activity">
                        {history.map((item) => {
                            const stageColor = stages.find((stage) => stage.id === item.new_stage_id)?.color
                            return (
                                <li key={item.id} className="relative border-l border-border/60 pb-4 pl-4 last:pb-0">
                                    <span
                                        className="absolute -left-1.5 top-1 size-3 rounded-full border-2 border-background bg-muted-foreground"
                                        style={stageColor ? { backgroundColor: stageColor } : undefined}
                                        aria-hidden="true"
                                    />
                                    <div className="flex flex-col gap-1">
                                        <div className="flex flex-wrap items-center gap-1.5 text-sm font-medium">
                                            {item.old_label_snapshot ? (
                                                <>
                                                    <span>{item.old_label_snapshot}</span>
                                                    <ArrowRightIcon className="size-3.5 text-muted-foreground" aria-hidden="true" />
                                                </>
                                            ) : null}
                                            <span>{item.new_label_snapshot}</span>
                                        </div>
                                        {item.reason ? (
                                            <p className="text-sm text-muted-foreground">{item.reason}</p>
                                        ) : null}
                                        <time className="text-xs text-muted-foreground" dateTime={item.effective_at}>
                                            {formatDateTime(item.effective_at, "—")}
                                        </time>
                                    </div>
                                </li>
                            )
                        })}
                    </ol>
                )}
            </CardContent>
        </Card>
    )
}

export function DonorDetailSections({
    donor,
    returnTo,
    stages,
    history,
    historyStatus,
    onRetryHistory,
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
    historyStatus: "loading" | "error" | "ready"
    onRetryHistory: () => void
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
                <div className="flex min-h-16 items-center justify-between gap-4 px-6 py-2">
                    <div className="flex min-w-0 items-center gap-4">
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
                    <div className="flex shrink-0 items-center gap-2">
                        {!donor.is_archived && canChangeStage ? (
                            <Button variant="outline" onClick={onChangeStage}>Change Stage</Button>
                        ) : null}
                        <Badge variant="outline" style={getDonorStageStyle(stages, donor)}>
                            {getDonorStageLabel(stages, donor)}
                        </Badge>
                        {donor.is_archived ? <Badge variant="secondary">Archived</Badge> : null}
                        {hasMenuActions ? (
                            <DropdownMenu>
                                <DropdownMenuTrigger
                                    aria-label={`Actions for ${donor.full_name}`}
                                    className="inline-flex size-10 items-center justify-center rounded-md border border-input bg-background hover:bg-accent hover:text-accent-foreground"
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

            <div className="flex-1 p-6">
                <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-3">
                    <section className="space-y-6 lg:col-span-2" aria-label="Donor details">
                        <Card>
                            <CardHeader><CardTitle>Contact Information</CardTitle></CardHeader>
                            <CardContent className="grid gap-5 sm:grid-cols-2">
                                <DetailRow icon={MailIcon} label="Email" value={donor.email} />
                                <DetailRow icon={PhoneIcon} label="Phone" value={donor.phone} />
                                <DetailRow icon={MapPinIcon} label="State" value={donor.state} />
                            </CardContent>
                        </Card>
                        <Card>
                            <CardHeader><CardTitle>Donor Information</CardTitle></CardHeader>
                            <CardContent className="grid gap-5 sm:grid-cols-2">
                                <DetailRow icon={GraduationCapIcon} label="Education" value={donor.education} />
                                <DetailRow icon={TagIcon} label="Source" value={donor.source} />
                                <DetailRow
                                    icon={CalendarIcon}
                                    label="Created"
                                    value={formatDateTime(donor.created_at, "—")}
                                />
                            </CardContent>
                        </Card>
                        <DonorNotesSection
                            donorId={donor.id}
                            canEdit={canEdit}
                            currentUserId={currentUserId}
                            canDeleteAny={canDeleteAnyNote}
                        />
                        <DonorDocumentsSection donor={donor} canEdit={canEdit} />
                        <DonorTasksSection
                            donor={donor}
                            canView={canViewTasks}
                            canCreate={canCreateTasks}
                        />
                    </section>
                    <aside className="space-y-6" aria-label="Donor activity">
                        <DonorActivityTimeline
                            stages={stages}
                            history={history}
                            historyStatus={historyStatus}
                            onRetry={onRetryHistory}
                        />
                    </aside>
                </div>
            </div>
        </div>
    )
}
