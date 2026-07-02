"use client"

import Link from "@/components/app-link"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { ApprovalTaskActions } from "@/components/tasks/ApprovalTaskActions"
import { ApprovalStatusBadge } from "@/components/tasks/ApprovalStatusBadge"
import { StatusChangeRequestActions } from "@/components/status-change-requests/StatusChangeRequestActions"
import { ImportApprovalActions } from "@/components/import/ImportApprovalActions"
import type { TaskListItem } from "@/lib/types/task"
import type { StatusChangeRequestDetail } from "@/lib/api/status-change-requests"
import type { ImportApprovalItem } from "@/lib/api/import"
import { ClockIcon, Loader2Icon, ShieldCheckIcon } from "lucide-react"
import { RelativeTime } from "@/components/ui/time-display"
import { formatUtcDateLabel } from "@/components/ui/time-display-utils"
import { useCurrentMinuteTimestamp } from "@/components/ui/use-current-minute-timestamp"

type TasksApprovalsSectionProps = {
    pendingApprovals: TaskListItem[]
    pendingStatusRequests: StatusChangeRequestDetail[]
    pendingImportApprovals: ImportApprovalItem[]
    loadingApprovals: boolean
    loadingStatusRequests: boolean
    loadingImportApprovals: boolean
    onResolvedStatusRequests: () => void
    onResolvedImportApprovals: () => void
    currentUserId?: string | null
}

function getApprovalDueState(dueAt: string, now: number) {
    const dueAtTimestamp = Date.parse(dueAt)
    if (!Number.isFinite(dueAtTimestamp)) {
        return { label: "Due date unavailable", isUrgent: false }
    }

    const hoursRemaining = Math.max(
        0,
        Math.round((dueAtTimestamp - now) / (1000 * 60 * 60)),
    )

    return {
        label:
            hoursRemaining > 24
                ? `${Math.floor(hoursRemaining / 24)}d ${hoursRemaining % 24}h remaining`
                : hoursRemaining > 0
                  ? `${hoursRemaining}h remaining`
                  : "Due now",
        isUrgent: hoursRemaining < 8,
    }
}

function ApprovalDueTime({ dueAt }: { dueAt: string }) {
    const now = useCurrentMinuteTimestamp()

    if (now === null) {
        return (
            <span className="flex items-center gap-1" suppressHydrationWarning>
                <ClockIcon className="size-3" />
                {formatUtcDateLabel(dueAt)}
            </span>
        )
    }

    const dueState = getApprovalDueState(dueAt, now)

    return (
        <span
            className={`flex items-center gap-1 ${
                dueState.isUrgent ? "text-amber-600 font-medium" : ""
            }`}
            suppressHydrationWarning
        >
            <ClockIcon className="size-3" />
            {dueState.label}
        </span>
    )
}

export function TasksApprovalsSection({
    pendingApprovals,
    pendingStatusRequests,
    pendingImportApprovals,
    loadingApprovals,
    loadingStatusRequests,
    loadingImportApprovals,
    onResolvedStatusRequests,
    onResolvedImportApprovals,
    currentUserId,
}: TasksApprovalsSectionProps) {
    const totalApprovals =
        (pendingApprovals?.length ?? 0) +
        (pendingStatusRequests?.length ?? 0) +
        (pendingImportApprovals?.length ?? 0)
    const isLoading = loadingApprovals || loadingStatusRequests || loadingImportApprovals
    const isEmpty = totalApprovals === 0

    return (
        <Card
            id="tasks-approvals"
            className="overflow-hidden border-amber-500/30 bg-gradient-to-br from-amber-500/5 to-transparent"
        >
            <div className="border-b border-amber-500/20 bg-amber-500/5 px-4 py-3 sm:px-6 sm:py-4">
                <div className="flex items-center gap-3">
                    <div className="flex size-8 items-center justify-center rounded-lg bg-amber-500/10 text-amber-600 sm:size-9">
                        <ShieldCheckIcon className="size-4 sm:size-5" />
                    </div>
                    <div>
                        <h2 className="text-sm font-semibold text-amber-700 dark:text-amber-500 sm:text-base">
                            Pending Approvals
                        </h2>
                        <p className="text-xs text-amber-600/80 dark:text-amber-500/70 sm:text-sm">
                            {totalApprovals} item{totalApprovals !== 1 ? "s" : ""} awaiting
                            review
                        </p>
                    </div>
                </div>
            </div>
            <div className="divide-y divide-border">
                {isLoading ? (
                    <div className="flex items-center justify-center py-8">
                        <Loader2Icon className="size-5 animate-spin text-muted-foreground" />
                    </div>
                ) : (
                    <>
                        {pendingStatusRequests.map((item) => {
                            const isIpRequest = item.request.entity_type === "intended_parent"
                            const isMatchRequest = item.request.entity_type === "match"
                            const requestLabel = isMatchRequest
                                ? "Match Cancellation Request"
                                : isIpRequest
                                  ? "Status Regression Request"
                                  : "Stage Regression Request"
                            const entityHref = isMatchRequest
                                ? `/intended-parents/matches/${item.request.entity_id}`
                                : isIpRequest
                                  ? `/intended-parents/${item.request.entity_id}`
                                  : `/surrogates/${item.request.entity_id}`
                            return (
                                <div
                                    key={`scr-${item.request.id}`}
                                    className="group flex flex-col gap-3 p-3 transition-colors hover:bg-muted/30 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:p-4"
                                >
                                    <div className="flex-1 space-y-2">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <span className="font-medium">{requestLabel}</span>
                                            <Badge
                                                variant="secondary"
                                                className="bg-amber-500/10 text-amber-600 border-amber-500/20 text-xs"
                                            >
                                                {isMatchRequest ? "Cancellation" : "Regression"}
                                            </Badge>
                                        </div>
                                        <p className="text-sm text-muted-foreground">
                                            {item.current_stage_label} → {item.target_stage_label}
                                            {item.request.reason && ` • ${item.request.reason}`}
                                        </p>
                                        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                                            <Link
                                                href={entityHref}
                                                className="hover:text-foreground hover:underline"
                                            >
                                                {item.entity_name || "Unknown"} (
                                                {item.entity_number})
                                            </Link>
                                            <span>
                                                Requested by {item.requester_name || "Unknown"}
                                            </span>
                                        </div>
                                    </div>
                                    <div className="flex-shrink-0">
                                        <StatusChangeRequestActions
                                            requestId={item.request.id}
                                            onResolved={onResolvedStatusRequests}
                                        />
                                    </div>
                                </div>
                            )
                        })}

                        {pendingImportApprovals.map((item) => {
                            const dedupe = item.deduplication_stats
                            const duplicateCount = dedupe?.duplicates?.length ?? 0
                            const newRecords =
                                typeof dedupe?.new_records === "number"
                                    ? dedupe.new_records
                                    : Math.max(item.total_rows - duplicateCount, 0)
                            return (
                                <div
                                    key={`import-${item.id}`}
                                    className="group flex flex-col gap-3 p-3 transition-colors hover:bg-muted/30 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:p-4"
                                >
                                    <div className="flex-1 space-y-2">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <span className="font-medium">Import Approval</span>
                                            <Badge
                                                variant="secondary"
                                                className="bg-amber-500/10 text-amber-600 border-amber-500/20 text-xs"
                                            >
                                                Awaiting Approval
                                            </Badge>
                                            {item.backdate_created_at && (
                                                <Badge
                                                    variant="secondary"
                                                    className="bg-amber-500/10 text-amber-600 border-amber-500/20 text-xs"
                                                >
                                                    Backdated
                                                </Badge>
                                            )}
                                        </div>
                                        <p className="text-sm text-muted-foreground">
                                            {item.filename}
                                        </p>
                                        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                                            <span>{item.total_rows} rows</span>
                                            <span>{newRecords} new</span>
                                            <span>
                                                {duplicateCount} duplicate
                                                {duplicateCount === 1 ? "" : "s"}
                                            </span>
                                            <span>
                                                Submitted by {item.created_by_name || "Unknown"}
                                            </span>
                                            <span>
                                                <RelativeTime
                                                    value={item.created_at}
                                                    fallback="Unknown time"
                                                />
                                            </span>
                                        </div>
                                    </div>
                                    <div className="flex-shrink-0">
                                        <ImportApprovalActions
                                            importId={item.id}
                                            onResolved={onResolvedImportApprovals}
                                        />
                                    </div>
                                </div>
                            )
                        })}

                        {pendingApprovals.map((approval) => {
                            const isOwner = currentUserId === approval.owner_id

                            return (
                                <div
                                    key={approval.id}
                                    className="group flex flex-col gap-3 p-3 transition-colors hover:bg-muted/30 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:p-4"
                                >
                                    <div className="flex-1 space-y-2">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <span className="font-medium">{approval.title}</span>
                                            <ApprovalStatusBadge
                                                status={approval.status || "pending"}
                                            />
                                        </div>
                                        {approval.workflow_action_preview && (
                                            <p className="text-sm text-muted-foreground">
                                                {approval.workflow_action_preview}
                                            </p>
                                        )}
                                        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                                            {approval.surrogate_id && (
                                                <Link
                                                    href={`/surrogates/${approval.surrogate_id}`}
                                                    className="hover:text-foreground hover:underline"
                                                >
                                                    Surrogate #{approval.surrogate_number}
                                                </Link>
                                            )}
                                            {approval.due_at && (
                                                <ApprovalDueTime dueAt={approval.due_at} />
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex-shrink-0">
                                        <ApprovalTaskActions
                                            taskId={approval.id}
                                            isOwner={isOwner}
                                        />
                                    </div>
                                </div>
                            )
                        })}

                        {isEmpty && (
                            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
                                No pending approvals right now.
                            </div>
                        )}
                    </>
                )}
            </div>
        </Card>
    )
}
