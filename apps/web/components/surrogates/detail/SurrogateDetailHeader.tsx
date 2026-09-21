"use client"

import * as React from "react"
import { ArrowLeftIcon } from "lucide-react"

import { OutcomeBadge } from "@/components/surrogates/OutcomeBadge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { stageMatchesKey } from "@/lib/surrogate-stage-context"
import type { LatestContactOutcome } from "@/lib/types/surrogate"
import { readableForeground } from "@/lib/stage-colors"

type SurrogateDetailHeaderProps = {
    recordLabel?: string
    surrogateNumber: string
    currentStageKey?: string | null
    currentStageSlug?: string | null
    statusLabel: string
    statusColor: string
    statusBadge?: React.ReactNode
    latestContactOutcome?: LatestContactOutcome | null
    pausedFromLabel?: string | null
    isArchived: boolean
    onBack: () => void
    children?: React.ReactNode
}

export function SurrogateDetailHeader({
    recordLabel = "Surrogate",
    surrogateNumber,
    currentStageKey = null,
    currentStageSlug = null,
    statusLabel,
    statusColor,
    statusBadge,
    latestContactOutcome = null,
    pausedFromLabel,
    isArchived,
    onBack,
    children,
}: SurrogateDetailHeaderProps) {
    const currentStage = { stage_key: currentStageKey, slug: currentStageSlug }
    const showContactOutcome =
        latestContactOutcome && stageMatchesKey(currentStage, "contacted")

    return (
        <header className="flex min-h-16 shrink-0 flex-wrap items-center justify-between gap-2 border-b px-4 py-3">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
                <Button variant="ghost" size="sm" onClick={onBack}>
                    <ArrowLeftIcon className="mr-2 size-4" />
                    Back
                </Button>
                <h1 className="text-xl font-semibold">{recordLabel} #{surrogateNumber}</h1>
                <div className="flex flex-wrap items-center gap-2">
                    <Badge style={{ backgroundColor: statusColor, color: readableForeground(statusColor) }}>{statusLabel}</Badge>
                    {statusBadge}
                </div>
                {showContactOutcome && (
                    <OutcomeBadge
                        kind="contact"
                        outcome={latestContactOutcome.outcome}
                        prefix="Contact"
                    />
                )}
                {pausedFromLabel && (
                    <span className="text-sm text-muted-foreground">
                        Paused from: <span className="font-medium text-foreground">{pausedFromLabel}</span>
                    </span>
                )}
                {isArchived && <Badge variant="secondary">Archived</Badge>}
            </div>
            <div className="ml-auto flex items-center gap-2">{children}</div>
        </header>
    )
}
