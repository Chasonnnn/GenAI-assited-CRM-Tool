"use client"

import { Loader2Icon } from "lucide-react"

import { QueryErrorState } from "@/components/error-state"
import { RelativeTime } from "@/components/ui/time-display"
import type { WorkflowExecution } from "@/lib/api/workflows"
import { getWorkflowExecutionStatusLabel } from "@/lib/constants/workflow-execution-status"
import { useWorkflowExecutions } from "@/lib/hooks/use-workflows"
import { cn } from "@/lib/utils"

const HISTORY_LIMIT = 50

type Outcome = { label: string; tone: "good" | "warn" | "bad" | "muted"; detail?: string | null }

const OUTCOME_CLASSES: Record<Outcome["tone"], string> = {
    good: "bg-emerald-500/12 text-emerald-700 dark:text-emerald-300",
    warn: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
    bad: "bg-destructive/10 text-destructive",
    muted: "bg-muted text-muted-foreground",
}

function runOutcome(execution: WorkflowExecution): Outcome {
    const label = getWorkflowExecutionStatusLabel(execution.status)
    if (!execution.matched_conditions) return { label: "Filters not matched", tone: "muted" }
    if (execution.status === "success") return { label, tone: "good" }
    if (execution.status === "failed" || execution.status === "partial") {
        return { label, tone: "bad", detail: execution.error_message }
    }
    if (execution.status === "paused") return { label, tone: "warn" }
    return { label, tone: "muted" }
}

/**
 * What one step did in a past run. Results are stored by position, so a run from before the
 * steps were reordered or changed reports the step that was in this position then.
 */
export function stepOutcome(execution: WorkflowExecution, index: number, actionType: string): Outcome {
    if (!execution.matched_conditions) return { label: "Filters not matched", tone: "muted" }
    const result = execution.actions_executed[index]
    if (!result) {
        if (execution.status === "paused" && index === execution.actions_executed.length) {
            return { label: "Waiting for approval", tone: "warn" }
        }
        return { label: "Not reached", tone: "muted" }
    }
    if (result.action_type && result.action_type !== actionType) {
        return { label: "Different step at the time", tone: "muted" }
    }
    if (result.success) return { label: "Ran", tone: "good" }
    if (result.skipped) return { label: "Skipped", tone: "muted", detail: result.error ?? null }
    return { label: "Failed", tone: "bad", detail: result.error ?? null }
}

function recordLabel(execution: WorkflowExecution): string {
    const number = execution.entity_number?.trim()
    const name = execution.entity_name?.trim()
    if (number && name) return `${number} · ${name}`
    return number || name || "Record unavailable"
}

/** Recent runs for the trigger, or for one step when a step index is given. */
export function WorkflowStepHistory({
    workflowId,
    step,
}: {
    workflowId: string
    step?: { index: number; actionType: string }
}) {
    const { data, isLoading, isError, error, refetch, isRefetching } = useWorkflowExecutions(workflowId, {
        limit: HISTORY_LIMIT,
    })

    if (isLoading) {
        return (
            <div role="status" className="flex items-center gap-2 p-3 text-xs text-muted-foreground">
                <Loader2Icon aria-hidden="true" className="size-3.5 animate-spin" />
                Loading runs…
            </div>
        )
    }
    if (isError) {
        return (
            <QueryErrorState
                error={error}
                title="Couldn't load runs"
                onRetry={() => void refetch()}
                isRetrying={isRefetching}
                headingLevel={3}
                className="p-3"
            />
        )
    }
    const executions = data?.items ?? []
    if (executions.length === 0) {
        return <p className="p-3 text-xs text-muted-foreground">No runs yet.</p>
    }

    return (
        <ul aria-label={step ? `Runs for step ${step.index + 1}` : "Recent runs"} className="divide-y divide-border">
            {executions.map((execution) => {
                const outcome = step ? stepOutcome(execution, step.index, step.actionType) : runOutcome(execution)
                return (
                    <li key={execution.id} className="flex flex-col gap-1 px-1 py-2.5">
                        <div className="flex items-center justify-between gap-2">
                            <span className="min-w-0 truncate text-xs font-medium">{recordLabel(execution)}</span>
                            <span
                                className={cn(
                                    "shrink-0 rounded-full px-2 py-px text-[11px] font-medium",
                                    OUTCOME_CLASSES[outcome.tone],
                                )}
                            >
                                {outcome.label}
                            </span>
                        </div>
                        <span className="text-[11px] text-muted-foreground">
                            <RelativeTime value={execution.executed_at} />
                        </span>
                        {outcome.detail ? <p className="text-[11px] break-words text-destructive">{outcome.detail}</p> : null}
                    </li>
                )
            })}
        </ul>
    )
}
