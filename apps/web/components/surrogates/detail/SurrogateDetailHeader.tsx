"use client"

import * as React from "react"
import { ArrowLeftIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

type SurrogateDetailHeaderProps = {
    surrogateNumber: string
    statusLabel: string
    statusColor: string
    pausedFromLabel?: string | null
    isArchived: boolean
    onBack: () => void
    children?: React.ReactNode
}

export function SurrogateDetailHeader({
    surrogateNumber,
    statusLabel,
    statusColor,
    pausedFromLabel,
    isArchived,
    onBack,
    children,
}: SurrogateDetailHeaderProps) {
    return (
        <header className="flex min-h-16 shrink-0 items-center justify-between gap-2 border-b px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
                <Button variant="ghost" size="sm" onClick={onBack}>
                    <ArrowLeftIcon className="mr-2 size-4" />
                    Back
                </Button>
                <h1 className="text-xl font-semibold">Surrogate #{surrogateNumber}</h1>
                <Badge style={{ backgroundColor: statusColor, color: "white" }}>{statusLabel}</Badge>
                {pausedFromLabel && (
                    <span className="text-sm text-muted-foreground">
                        Paused from: <span className="font-medium text-foreground">{pausedFromLabel}</span>
                    </span>
                )}
                {isArchived && <Badge variant="secondary">Archived</Badge>}
            </div>
            <div className="flex items-center gap-2">{children}</div>
        </header>
    )
}
