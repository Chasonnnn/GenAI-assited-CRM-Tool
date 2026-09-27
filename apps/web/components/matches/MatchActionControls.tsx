"use client"

import { useId } from "react"
import { AlertTriangleIcon } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import type { MatchRead } from "@/lib/api/matches"

export type MatchAction = MatchRead["allowed_actions"][number]

const ACTION_ORDER: MatchAction[] = ["accept", "decline", "complete", "request_cancel", "withdraw_cancel"]

const ACTION_PRESENTATION: Record<MatchAction, { label: string; pendingLabel: string; variant: "default" | "destructive" | "outline"; className?: string }> = {
    accept: { label: "Accept Match", pendingLabel: "Accepting...", variant: "default", className: "bg-green-600 hover:bg-green-700" },
    decline: { label: "Decline", pendingLabel: "Declining...", variant: "destructive" },
    complete: { label: "Complete Match", pendingLabel: "Completing...", variant: "default" },
    request_cancel: { label: "Cancel Match", pendingLabel: "Requesting...", variant: "destructive" },
    withdraw_cancel: { label: "Withdraw Cancellation", pendingLabel: "Withdrawing...", variant: "outline" },
}

function BlockedActionButton({ action, reason }: { action: MatchAction; reason: string }) {
    const reasonId = useId()
    const presentation = ACTION_PRESENTATION[action]
    return (
        <>
            <Tooltip>
                <TooltipTrigger
                    render={
                        <Button
                            variant={presentation.variant}
                            size="sm"
                            className={`h-7 text-xs ${presentation.className ?? ""}`}
                            disabled
                            focusableWhenDisabled
                            aria-describedby={reasonId}
                        />
                    }
                >
                    {presentation.label}
                </TooltipTrigger>
                <TooltipContent className="max-w-72">{reason}</TooltipContent>
            </Tooltip>
            <span id={reasonId} className="sr-only">{reason}</span>
        </>
    )
}

export function MatchActionControls({
    match,
    pending,
    onAction,
}: {
    match: Pick<MatchRead, "allowed_actions" | "blocked_reasons">
    pending: Partial<Record<MatchAction, boolean>>
    onAction: (action: MatchAction) => void
}) {
    const anyPending = Object.values(pending).some(Boolean)
    return (
        <>
            {ACTION_ORDER.map((action) => {
                const reason = match.blocked_reasons[action]
                if (!match.allowed_actions.includes(action)) {
                    return reason ? <BlockedActionButton key={action} action={action} reason={reason} /> : null
                }
                const presentation = ACTION_PRESENTATION[action]
                return (
                    <Button
                        key={action}
                        variant={presentation.variant}
                        size="sm"
                        className={`h-7 text-xs ${presentation.className ?? ""}`}
                        onClick={() => onAction(action)}
                        disabled={anyPending}
                    >
                        {pending[action] ? presentation.pendingLabel : presentation.label}
                    </Button>
                )
            })}
        </>
    )
}

export function MatchConflictBadge({ show }: { show: boolean }) {
    if (!show) return null
    return (
        <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
            Surrogate has an accepted match
        </Badge>
    )
}

export function MatchAcceptWarnings({ warnings }: { warnings: string[] | undefined }) {
    if (!warnings?.length) return null
    return (
        <ul aria-label="Accept warnings" className="space-y-1 border-b px-6 py-2 text-sm text-amber-800 dark:text-amber-200">
            {warnings.map((warning) => (
                <li key={warning} className="flex items-start gap-2">
                    <AlertTriangleIcon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                    <span>{warning}</span>
                </li>
            ))}
        </ul>
    )
}
