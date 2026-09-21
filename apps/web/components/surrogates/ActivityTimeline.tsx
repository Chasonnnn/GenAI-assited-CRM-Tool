"use client"

import { EntityActivityTimeline } from "@/components/activity/EntityActivityTimeline"
import { getStageSemantics, stageMatchesKey } from "@/lib/surrogate-stage-context"
import type { PipelineStage } from "@/lib/api/pipelines"
import type { SurrogateActivity } from "@/lib/api/surrogates"
import { useSurrogateHistory } from "@/lib/hooks/use-surrogates"
import type { TaskListItem } from "@/lib/types/task"
import { InterviewAppointmentManager } from "@/components/surrogates/InterviewAppointmentManager"

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
    const currentStage = stages.find((stage) => stage.id === currentStageId)
    const canHaveInterviewAppointment = stageMatchesKey(currentStage, "interview_scheduled")
        || stageMatchesKey(currentStage, "reschedule_needed")
    const latestInterviewActivity = canHaveInterviewAppointment
        ? activities?.filter((activity) => ["interview_scheduled", "interview_rescheduled"].includes(activity.activity_type))
            .toSorted((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0]
        : undefined
    const status = historyQuery.isLoading || activityStatus === "loading"
        ? "loading"
        : historyQuery.isError || activityStatus === "error"
          ? "error"
          : "ready"

    return (
        <EntityActivityTimeline
            {...(latestInterviewActivity ? { activityAction: {
                activityId: latestInterviewActivity.id,
                content: <InterviewAppointmentManager surrogateId={surrogateId} stageId={currentStageId} triggerOnly />,
            } } : {})}
            currentStageId={currentStageId}
            stages={stages.map((stage) => ({ ...stage, semantics: getStageSemantics(stage) }))}
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
