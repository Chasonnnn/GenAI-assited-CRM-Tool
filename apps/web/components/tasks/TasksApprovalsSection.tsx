"use client"

import Link from "@/components/app-link"
import { TaskRelatedRecordLinks } from "@/components/tasks/TaskRelatedRecordLinks"
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
import { cn } from "@/lib/utils"

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
    highlightedId?: string | null
}

function approvalRowProps(id: string, highlightedId: string | null | undefined) {
    const highlighted = id === highlightedId
    return {
        id: `approval-${id}`,
        "data-highlighted": highlighted ? "true" : undefined,
        className: cn(
            "group flex flex-col gap-3 p-3 transition-colors hover:bg-muted/30 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:p-4",
            highlighted && "bg-primary/5 ring-2 ring-inset ring-primary/40"
        ),
    }
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
    highlightedId,
}: TasksApprovalsSectionProps) {
    const totalApprovals =
        (pendingApprovals?.length ?? 0) +
        (pendingStatusRequests?.length ?? 0) +
        (pendingImportApprovals?.length ?? 0)
    const isLoading = loadingApprovals || loadingStatusRequests || loadingImportApprovals

    // Nothing to review: render nothing, so the view below keeps its position.
    if (totalApprovals === 0) return null

    return (
        <Card id="tasks-approvals" className="gap-0 overflow-hidden py-0">
            <div className="flex items-center gap-2 border-b border-border px-4 py-3 sm:px-6">
                <ShieldCheckIcon className="size-4 text-muted-foreground" aria-hidden="true" />
                <h2 className="text-sm font-semibold">
                    Pending Approvals
                </h2>
                <Badge variant="secondary" className="tabular-nums">
                    {totalApprovals}
                    <span className="sr-only"> awaiting review</span>
                </Badge>
                {isLoading ? (
                    <Loader2Icon className="ml-auto size-4 animate-spin text-muted-foreground" aria-label="Loading approvals" />
                ) : null}
            </div>
            <div className="divide-y divide-border">
                    <>
                        {pendingStatusRequests.map((item) => {
                            const isIpRequest = item.request.entity_type === "intended_parent"
                            const isMatchRequest = item.request.entity_type === "match"
                            const isDonorRequest = item.request.entity_type === "donor"
                            const requestLabel = isMatchRequest
                                ? "Match Cancellation Request"
                                : isIpRequest
                                  ? "Status Regression Request"
                                  : "Stage Regression Request"
                            const entityHref = isMatchRequest
                                ? `/intended-parents/matches/${item.request.entity_id}`
                                : isIpRequest
                                  ? `/intended-parents/${item.request.entity_id}`
                                  : isDonorRequest
                                    ? `/donors/${item.request.entity_id}`
                                    : `/surrogates/${item.request.entity_id}`
                            return (
                                <div
                                    key={`scr-${item.request.id}`}
                                    {...approvalRowProps(item.request.id, highlightedId)}
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
                                    {...approvalRowProps(approval.id, highlightedId)}
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
                                            <TaskRelatedRecordLinks task={approval} />
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

                    </>
            </div>
        </Card>
    )
}
