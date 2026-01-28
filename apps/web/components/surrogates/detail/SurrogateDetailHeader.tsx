"use client"

import * as React from "react"
import { ArrowLeftIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

type SurrogateDetailHeaderProps = {
    surrogateNumber: string
    statusLabel: string
    statusColor: string
    isArchived: boolean
    onBack: () => void
    children?: React.ReactNode
}

export function SurrogateDetailHeader({
    surrogateNumber,
    statusLabel,
    statusColor,
    isArchived,
    onBack,
    children,
}: SurrogateDetailHeaderProps) {
    return (
        <header className="flex h-16 shrink-0 items-center justify-between gap-2 border-b px-4">
            <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={onBack}>
                    <ArrowLeftIcon className="mr-2 size-4" />
                    Back
                </Button>
                <h1 className="text-xl font-semibold">Surrogate #{surrogateNumber}</h1>
                <Badge style={{ backgroundColor: statusColor, color: "white" }}>{statusLabel}</Badge>
                {isArchived && <Badge variant="secondary">Archived</Badge>}
            </div>
            <div className="flex items-center gap-2">{children}</div>
        </header>
    )
}
