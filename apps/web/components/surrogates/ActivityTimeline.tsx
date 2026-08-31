"use client"

import { EntityActivityTimeline } from "@/components/activity/EntityActivityTimeline"
import type { PipelineStage } from "@/lib/api/pipelines"
import type { SurrogateActivity } from "@/lib/api/surrogates"
import { useSurrogateHistory } from "@/lib/hooks/use-surrogates"
import type { TaskListItem } from "@/lib/types/task"

interface ActivityTimelineProps {
    surrogateId: string
    currentStageId: string
    effectiveStageId?: string
    stages: PipelineStage[]
    activities?: SurrogateActivity[]
    tasks?: TaskListItem[]
    tasksStatus?: "loading" | "error" | "ready"
    onRetryTasks?: () => void
    activityStatus?: "loading" | "error" | "ready"
    onRetryActivity?: () => void
}

export function ActivityTimeline({
    surrogateId,
    currentStageId,
    effectiveStageId,
    stages,
    activities,
    tasks,
    tasksStatus,
    onRetryTasks,
    activityStatus = "ready",
    onRetryActivity,
}: ActivityTimelineProps) {
    const historyQuery = useSurrogateHistory(surrogateId)
    const status = historyQuery.isLoading || activityStatus === "loading"
        ? "loading"
        : historyQuery.isError || activityStatus === "error"
          ? "error"
          : "ready"

    return (
        <EntityActivityTimeline
            currentStageId={currentStageId}
            stages={stages}
            stageHistory={historyQuery.data ?? []}
            status={status}
            onRetry={() => {
                void historyQuery.refetch()
                onRetryActivity?.()
            }}
            historyHref={`/surrogates/${surrogateId}/history`}
            notesHref={`/surrogates/${surrogateId}/notes`}
            {...(tasksStatus ? { tasksStatus } : {})}
            {...(onRetryTasks ? { onRetryTasks } : {})}
            {...(effectiveStageId ? { effectiveStageId } : {})}
            {...(activities ? { activities } : {})}
            {...(tasks ? { tasks } : {})}
        />
    )
}
