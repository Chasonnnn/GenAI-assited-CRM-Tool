"use client"

import { Badge } from "@/components/ui/badge"
import {
    getSurrogateOutcomePresentation,
    type SurrogateOutcomeKind,
} from "@/lib/surrogate-outcome-presentation"
import { cn } from "@/lib/utils"

interface OutcomeBadgeProps {
    kind: SurrogateOutcomeKind
    outcome: string | null | undefined
    prefix?: string
    className?: string
}

export function OutcomeBadge({ kind, outcome, prefix, className }: OutcomeBadgeProps) {
    const presentation = getSurrogateOutcomePresentation(kind, outcome)
    if (!presentation) return null

    const Icon = presentation.icon
    const label = prefix ? `${prefix}: ${presentation.label}` : presentation.label

    return (
        <Badge variant="outline" className={cn(presentation.badgeClassName, className)}>
            <Icon className="size-3" />
            {label}
        </Badge>
    )
}
