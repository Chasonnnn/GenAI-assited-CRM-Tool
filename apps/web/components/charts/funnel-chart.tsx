"use client"

import { useMemo } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Loader2Icon } from "lucide-react"

interface FunnelStage {
    stage: string
    label: string
    count: number
    percentage: number
}

interface FunnelChartProps {
    data: FunnelStage[] | undefined
    isLoading?: boolean
    title?: string
}

// Gradient colors for funnel stages
const stageColors = [
    "from-blue-500 to-blue-600",
    "from-indigo-500 to-indigo-600",
    "from-purple-500 to-purple-600",
    "from-violet-500 to-violet-600",
    "from-green-500 to-green-600",
]

export function FunnelChart({
    data,
    isLoading = false,
    title = "Conversion Funnel",
}: FunnelChartProps) {
    const maxCount = useMemo(() => {
        if (!data || data.length === 0) return 0
        return Math.max(...data.map(d => d.count))
    }, [data])

    if (isLoading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle>{title}</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex h-[300px] items-center justify-center">
                        <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                    </div>
                </CardContent>
            </Card>
        )
    }

    if (!data || data.length === 0) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle>{title}</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex h-[300px] items-center justify-center text-muted-foreground">
                        No funnel data available
                    </div>
                </CardContent>
            </Card>
        )
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle>{title}</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="space-y-3">
                    {data.map((stage, index) => {
                        const widthPercent = maxCount > 0 ? (stage.count / maxCount) * 100 : 0
                        const colorClass = stageColors[index % stageColors.length]

                        return (
                            <div key={stage.stage} className="relative">
                                {/* Stage label and count */}
                                <div className="mb-1 flex items-center justify-between text-sm">
                                    <span className="font-medium">{stage.label}</span>
                                    <span className="text-muted-foreground">
                                        {stage.count} ({stage.percentage}%)
                                    </span>
                                </div>

                                {/* Funnel bar */}
                                <div className="relative h-10 w-full rounded-md bg-muted/30">
                                    <div
                                        className={`absolute left-0 top-0 h-full rounded-md bg-gradient-to-r ${colorClass} transition-all duration-500`}
                                        style={{
                                            width: `${Math.max(widthPercent, 5)}%`,
                                        }}
                                    />

                                    {/* Arrow indicator for conversion */}
                                    {index < data.length - 1 && (
                                        <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 text-muted-foreground/50">
                                            ↓
                                        </div>
                                    )}
                                </div>
                            </div>
                        )
                    })}
                </div>

                {/* Legend */}
                <div className="mt-6 flex items-center justify-center gap-4 text-xs text-muted-foreground">
                    <span>Lead → Qualified → Active</span>
                </div>
            </CardContent>
        </Card>
    )
}
