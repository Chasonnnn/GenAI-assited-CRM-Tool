"use client"

import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import type { MatchRead } from "@/lib/api/matches"
import type { PipelineStage } from "@/lib/api/pipelines"
import { useDefaultPipeline } from "@/lib/hooks/use-pipelines"
import type { IntendedParent } from "@/lib/types/intended-parent"

type StageLike = Pick<PipelineStage, "id" | "label" | "order" | "stage_key" | "system_role">

const MATCHED_SYSTEM_ROLE = "matched"
const FALLBACK_MATCHED_LABEL = "Matched"

function findMatchedStage(stages: readonly StageLike[] | undefined): StageLike | undefined {
    return stages?.find((stage) => stage.system_role === MATCHED_SYSTEM_ROLE)
}

/**
 * Side effects of PUT /matches/{id}/accept, in the order match_lifecycle applies them:
 * the surrogate moves to the pipeline's "matched" stage, the intended parent moves to its
 * "matched" stage when it is earlier in the pipeline, and the surrogate's other matches under
 * review stay open but cannot be accepted. The donor's own move to its "matched" stage is not
 * listed: MatchRead carries no donor stage id to compare.
 */
export function getAcceptMatchChanges({
    match,
    intendedParent,
    surrogateStages,
    intendedParentStages,
}: {
    match: Pick<MatchRead, "match_kind" | "surrogate_id" | "surrogate_stage_id" | "surrogate_stage_label">
    intendedParent: Pick<IntendedParent, "stage_id" | "stage_key"> | undefined
    surrogateStages: readonly StageLike[] | undefined
    intendedParentStages: readonly StageLike[] | undefined
}): string[] {
    const changes: string[] = []
    const isSurrogateMatch = match.match_kind !== "donor" && Boolean(match.surrogate_id)

    if (isSurrogateMatch) {
        const matchedStage = findMatchedStage(surrogateStages)
        if (!matchedStage || match.surrogate_stage_id !== matchedStage.id) {
            const from = match.surrogate_stage_label ?? "Current stage"
            changes.push(`Surrogate stage: ${from} → ${matchedStage?.label ?? FALLBACK_MATCHED_LABEL}`)
        }
    }

    const matchedIpStage = findMatchedStage(intendedParentStages)
    const currentIpStage =
        intendedParentStages?.find((stage) => stage.id === intendedParent?.stage_id) ??
        intendedParentStages?.find((stage) => stage.stage_key === intendedParent?.stage_key)
    if (
        matchedIpStage &&
        currentIpStage &&
        currentIpStage.system_role !== MATCHED_SYSTEM_ROLE &&
        currentIpStage.order < matchedIpStage.order
    ) {
        changes.push(`Intended parent stage: ${currentIpStage.label} → ${matchedIpStage.label}`)
    }

    if (isSurrogateMatch) {
        changes.push("Other matches under review for this surrogate stay open but can't be accepted.")
    }

    return changes
}

export function AcceptMatchDialog({
    match,
    intendedParent,
    open,
    onOpenChange,
    onConfirm,
}: {
    match: MatchRead
    intendedParent: IntendedParent | undefined
    open: boolean
    onOpenChange: (open: boolean) => void
    onConfirm: () => Promise<unknown>
}) {
    const { data: surrogatePipeline } = useDefaultPipeline("surrogate", open && match.match_kind !== "donor")
    const { data: intendedParentPipeline } = useDefaultPipeline("intended_parent", open)
    const changes = getAcceptMatchChanges({
        match,
        intendedParent,
        surrogateStages: surrogatePipeline?.stages,
        intendedParentStages: intendedParentPipeline?.stages,
    })

    return (
        <ConfirmDialog
            open={open}
            onOpenChange={onOpenChange}
            title={match.match_number ? `Accept match ${match.match_number}?` : "Accept this match?"}
            confirmLabel="Accept Match"
            confirmVariant="default"
            errorFallback="Couldn't accept match. Try again."
            onConfirm={onConfirm}
        >
            {changes.length > 0 ? (
                <ul className="list-disc space-y-1 pl-5 text-sm">
                    {changes.map((change) => (
                        <li key={change}>{change}</li>
                    ))}
                </ul>
            ) : null}
        </ConfirmDialog>
    )
}
