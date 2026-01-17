"use client"

import { LucideIcon } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

interface SurrogateOverviewCardProps {
    title: string
    icon?: LucideIcon // Optional - accepts Lucide icon component
    action?: React.ReactNode // Optional header action (e.g., "Expand All" button)
    children: React.ReactNode
}

export function SurrogateOverviewCard({
    title,
    icon: Icon,
    action,
    children,
}: SurrogateOverviewCardProps) {
    return (
        <Card className="gap-4 py-4">
            <CardHeader className="px-4 pb-2">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-base flex items-center gap-2">
                        {Icon && <Icon className="size-4" />}
                        {title}
                    </CardTitle>
                    {action}
                </div>
            </CardHeader>
            <CardContent className="px-4 space-y-3">{children}</CardContent>
        </Card>
    )
}
