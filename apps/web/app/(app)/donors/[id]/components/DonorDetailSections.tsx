"use client"

import type { Route } from "next"
import { useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { ArchiveIcon, ArchiveRestoreIcon, Loader2Icon, MoreVerticalIcon } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { EntityActivityTimeline } from "@/components/activity/EntityActivityTimeline"
import { EntityActivityHistory } from "@/components/activity/EntityActivityHistory"
import { RecordCorrespondenceCard } from "@/components/records/RecordCorrespondenceCard"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { DonorAssignMenu } from "@/components/donors/DonorAssignMenu"
import { DonorDocumentsSection } from "@/components/donors/DonorDocumentsSection"
import { DonorNotesSection } from "@/components/donors/DonorNotesSection"
import { DonorProfilePhoto } from "@/components/donors/DonorProfilePhoto"
import { DonorTasksSection } from "@/components/donors/DonorTasksSection"
import { DonorOverviewTab } from "@/components/donors/DonorOverviewTab"
import { DonorOwnershipSection } from "@/components/donors/DonorOwnershipSection"
import { RecordCollaborators } from "@/components/permissions/record-collaborators"
import { SurrogateDetailHeader } from "@/components/surrogates/detail/SurrogateDetailHeader"
import type { PipelineStage } from "@/lib/api/pipelines"
import type { EntityActivity } from "@/lib/api/activity"
import type { TaskListItem } from "@/lib/api/tasks"
import { normalizeDonorHistory } from "@/lib/activity-history"
import { getDonorStageLabel, getDonorStageStyle } from "@/lib/donor-stage-utils"
import type { Donor, DonorStatusHistoryItem } from "@/lib/types/donor"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"

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
    const policyV2 = (permissionsQuery.data?.policy_version ?? 1) >= 2
    const router = useRouter()
    const searchParams = useSearchParams()
    const initialTab = searchParams.get("tab")
    const [tab, setTab] = useState(initialTab && ["overview", "notes", "tasks", "history"].includes(initialTab) ? initialTab : "overview")
    const [correspondenceOpen, setCorrespondenceOpen] = useState(false)
    const canEdit = access.edit && !donor.is_archived
    const changeTab = (value: unknown) => {
        if (typeof value !== "string") return
        setTab(value)
        const params = new URLSearchParams(window.location.search)
        if (value === "overview") params.delete("tab")
        else params.set("tab", value)
        const query = params.toString()
        window.history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}`)
    }
    const activityPanel = <><EntityActivityTimeline
        currentStageId={donor.stage_id}
        stages={stages}
        stageHistory={normalizeDonorHistory(history)}
        activities={activities}
        tasks={tasks}
        tasksStatus={tasksStatus}
        onRetryTasks={onRetryTasks}
        status={activityStatus}
        onRetry={onRetryActivity}
        historyHref={`/donors/${donor.id}?tab=history&return_to=${encodeURIComponent(returnTo)}`}
        onViewHistory={() => changeTab("history")}
    />
        <DonorOwnershipSection
            donor={donor}
            canEdit={canEdit && (!policyV2 || hasPermission("assign_donors"))}
            canClaim={policyV2 && hasPermission("assign_donors")}
        />
        <RecordCollaborators kind="donor" recordId={donor.id} />
    </>
    return <div className="flex flex-1 flex-col">
        <SurrogateDetailHeader
            recordLabel="Donor"
            surrogateNumber={donor.donor_number}
            statusLabel={getDonorStageLabel(stages, donor)}
            statusColor={String(getDonorStageStyle(stages, donor).color)}
            isArchived={donor.is_archived}
            onBack={() => router.push(returnTo as Route)}>
            <DonorProfilePhoto donor={donor} canEdit={canEdit} compact />
            {access.changeStage && !donor.is_archived && <Button size="sm" variant="outline" onClick={onChangeStage}>Change Stage</Button>}
            {(canEdit || access.archive || user?.role === "developer") && <DropdownMenu>
                <DropdownMenuTrigger render={<Button size="icon" variant="ghost" aria-label={`Actions for ${donor.full_name}`} />}><MoreVerticalIcon className="size-4" /></DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                    {canEdit && <DropdownMenuItem onClick={onEdit}>Edit</DropdownMenuItem>}
                    {canEdit && (!policyV2 || hasPermission("assign_donors")) && <DonorAssignMenu donor={donor} />}
                    {canEdit && <DropdownMenuSeparator />}
                    {user?.role === "developer" && <DropdownMenuItem onClick={() => setCorrespondenceOpen(true)}>Correspondence</DropdownMenuItem>}
                    {access.archive && (donor.is_archived
                        ? <DropdownMenuItem onClick={onRestore} disabled={restoreStatus === "pending"}>{restoreStatus === "pending" ? <Loader2Icon className="size-4 animate-spin" /> : <ArchiveRestoreIcon className="size-4" />}Restore</DropdownMenuItem>
                        : <DropdownMenuItem onClick={onArchive} disabled={archiveStatus === "pending"}>{archiveStatus === "pending" ? <Loader2Icon className="size-4 animate-spin" /> : <ArchiveIcon className="size-4" />}Archive</DropdownMenuItem>)}
                </DropdownMenuContent>
            </DropdownMenu>}
        </SurrogateDetailHeader>
        <div className="min-w-0 flex-1 p-4 md:p-6">
            <Tabs value={tab} onValueChange={changeTab}>
                <TabsList className="mb-4 max-w-full overflow-x-auto print:hidden" aria-label="Donor details">
                    <TabsTrigger value="overview">Overview</TabsTrigger>
                    <TabsTrigger value="notes">Notes</TabsTrigger>
                    <TabsTrigger value="tasks">Tasks</TabsTrigger>
                    <TabsTrigger value="history">History</TabsTrigger>
                </TabsList>
                {tab === "overview" && <DonorOverviewTab donor={donor} canEdit={canEdit} activityPanel={activityPanel} />}
                <TabsContent value="notes">
                    <Card><div className="grid grid-cols-1 divide-y divide-border lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:divide-x lg:divide-y-0">
                        <div className="order-last min-w-0 p-6 lg:order-first"><DonorNotesSection embedded donorId={donor.id} canEdit={canEdit} currentUserId={currentUserId} canDeleteAny={access.deleteAnyNote} /></div>
                        <div className="order-first min-w-0 p-6 lg:sticky lg:top-4 lg:self-start lg:order-last"><DonorDocumentsSection embedded donor={donor} canEdit={canEdit} /></div>
                    </div></Card>
                </TabsContent>
                <TabsContent value="tasks" className="space-y-4">
                    {access.viewTasks ? <DonorTasksSection donor={donor} canView={access.viewTasks} canCreate={access.createTasks} /> : <p className="text-sm text-muted-foreground">You don’t have permission to view tasks.</p>}
                </TabsContent>
                <TabsContent value="history">
                    {tab === "history" && <EntityActivityHistory embedded entityType="donor" entityId={donor.id} backHref={returnTo} />}
                </TabsContent>
            </Tabs>
        </div>
        {correspondenceOpen && <Dialog open onOpenChange={setCorrespondenceOpen}><DialogContent className="sm:max-w-2xl"><DialogHeader><DialogTitle>Correspondence</DialogTitle></DialogHeader><RecordCorrespondenceCard kind="donor" recordId={donor.id} canView={user?.role === "developer"} canEdit={canEdit} /></DialogContent></Dialog>}
    </div>
}
