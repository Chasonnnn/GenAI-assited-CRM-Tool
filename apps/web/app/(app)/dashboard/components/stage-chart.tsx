"use client"

import { useState, useMemo } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button, buttonVariants } from "@/components/ui/button"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Skeleton } from "@/components/ui/skeleton"
import { Bar, BarChart, XAxis, YAxis, Cell, Tooltip, CartesianGrid, LabelList } from "recharts"
import { ChartContainer } from "@/components/ui/chart"
import {
    PieChartIcon,
    AlertCircleIcon,
    PlusIcon,
    LockIcon,
} from "lucide-react"
import Link from "@/components/app-link"
import { useSurrogatesByStatus } from "@/lib/hooks/use-analytics"
import { useSurrogateStats } from "@/lib/hooks/use-surrogates"
import { useDefaultPipeline } from "@/lib/hooks/use-pipelines"
import { useDashboardFilters } from "../context/dashboard-filters"
import { formatLocalDate } from "@/lib/utils/date"
import { ApiError } from "@/lib/api"
import { buildStageChartData } from "./stage-chart-utils"

type ViewMode = "count" | "percent"

export function StageChart() {
    const router = useRouter()
    const { filters, getDateParams, resetFilters, hasActiveFilters } = useDashboardFilters()
    const [viewMode, setViewMode] = useState<ViewMode>("count")

    const dateParams = getDateParams()
    const statusParams = {
        ...dateParams,
        ...(filters.assigneeId ? { owner_id: filters.assigneeId } : {}),
    }
    const { data: statusData, isLoading, isError, error, refetch } = useSurrogatesByStatus(statusParams)
    const orgStatsQuery = useSurrogateStats()
    const { data: pipeline } = useDefaultPipeline()
    const isRestricted = error instanceof ApiError && error.status === 403
    const orgTotal = orgStatsQuery.data?.total
    const hasOrgSurrogates = (orgTotal ?? 0) > 0

    // Build stage color map from pipeline (NOT from API)
    const stageColorMap = useMemo(() => {
        if (!pipeline?.stages) return new Map<string, string>()
        return new Map(pipeline.stages.map((s) => [s.id, s.color]))
    }, [pipeline])

    // Transform and sort data by order
    const { data: chartData, total: totalCount } = useMemo(() => {
        return buildStageChartData(statusData, stageColorMap)
    }, [statusData, stageColorMap])

    const wrapStageLabel = (label: string, maxLength = 20) => {
        const words = label.split(" ")
        const lines: string[] = []
        let current = ""
        for (const word of words) {
            const next = current ? `${current} ${word}` : word
            if (next.length > maxLength && current) {
                lines.push(current)
                current = word
                if (lines.length === 2) break
            } else {
                current = next
            }
        }
        if (current && lines.length < 2) {
            lines.push(current)
        }
        return lines
    }

    // Handle bar click - navigate to surrogates filtered by stage
    const handleBarClick = (data: { stage_id: string | null }) => {
        if (!data.stage_id) return

        const params = new URLSearchParams()
        params.set("stage", data.stage_id)

        // Include current date filters
        if (filters.dateRange !== "all") {
            params.set("range", filters.dateRange)
        }
        if (filters.dateRange === "custom" && filters.customRange.from) {
            params.set("from", formatLocalDate(filters.customRange.from))
            if (filters.customRange.to) {
                params.set("to", formatLocalDate(filters.customRange.to))
            }
        }
        if (filters.assigneeId) {
            params.set("owner_id", filters.assigneeId)
        }

        router.push(`/surrogates?${params.toString()}`)
    }

    return (
        <Card className="h-full flex flex-col gap-0 p-0">
            <CardHeader className="p-6 pb-0 gap-0">
                <div className="flex items-center justify-between mb-1">
                    <CardTitle className="text-base font-semibold">Pipeline Distribution</CardTitle>
                    <ToggleGroup
                        value={[viewMode]}
                        onValueChange={(value) => {
                            const nextValue = Array.isArray(value) ? value[0] : value
                            if (nextValue === "count" || nextValue === "percent") {
                                setViewMode(nextValue)
                            }
                        }}
                        variant="outline"
                        size="sm"
                        spacing={0}
                        className="h-8"
                    >
                        <ToggleGroupItem value="count" className="h-8">Count</ToggleGroupItem>
                        <ToggleGroupItem value="percent" className="h-8">%</ToggleGroupItem>
                    </ToggleGroup>
                </div>
                <CardDescription className="text-sm text-muted-foreground mb-4">
                    {totalCount.toLocaleString()} surrogates in pipeline
                </CardDescription>
            </CardHeader>
            <CardContent className="px-4 pb-6 pt-0 flex-1">
                {isLoading ? (
                    <div className="h-[320px] space-y-3">
                        {Array.from({ length: 6 }).map((_, i) => (
                            <div key={i} className="flex items-center gap-3">
                                <Skeleton className="h-6 w-20" />
                                <Skeleton className="h-6 flex-1" />
                            </div>
                        ))}
                    </div>
                ) : isRestricted ? (
                    <div className="flex flex-col items-center justify-center h-[320px] gap-3 text-center">
                        <LockIcon className="size-8 text-muted-foreground" />
                        <div>
                            <p className="text-sm font-medium">Analytics unavailable</p>
                            <p className="text-xs text-muted-foreground mt-1">
                                Ask an admin to grant access to analytics.
                            </p>
                        </div>
                    </div>
                ) : isError ? (
                    <div className="flex flex-col items-center justify-center h-[320px] gap-3">
                        <AlertCircleIcon className="size-8 text-destructive" />
                        <div className="text-center">
                            <p className="text-sm font-medium text-destructive">Analytics unavailable</p>
                            <p className="text-xs text-muted-foreground mt-1">
                                We couldn’t load pipeline distribution.
                            </p>
                        </div>
                        <Button variant="outline" size="sm" onClick={() => refetch()}>
                            Retry
                        </Button>
                    </div>
                ) : chartData.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-[320px] text-center">
                        <PieChartIcon className="size-12 text-muted-foreground/50 mb-4" />
                        {orgTotal === 0 ? (
                            <>
                                <h4 className="font-medium text-foreground">No surrogates yet</h4>
                                <p className="text-sm text-muted-foreground mt-1 mb-4">
                                    Add your first surrogate to see the distribution.
                                </p>
                                <Link href="/surrogates?new=true" className={buttonVariants({ size: "sm" })}>
                                    <PlusIcon className="size-4 mr-2" />
                                    Add Surrogate
                                </Link>
                            </>
                        ) : hasActiveFilters ? (
                            <>
                                <h4 className="font-medium text-foreground">No surrogates match your filters</h4>
                                <p className="text-sm text-muted-foreground mt-1 mb-4">
                                    Try adjusting or clearing filters to see results.
                                </p>
                                <Button variant="outline" size="sm" onClick={resetFilters}>
                                    Reset filters
                                </Button>
                            </>
                        ) : hasOrgSurrogates ? (
                            <>
                                <h4 className="font-medium text-foreground">Analytics unavailable</h4>
                                <p className="text-sm text-muted-foreground mt-1">
                                    Pipeline distribution is temporarily unavailable.
                                </p>
                            </>
                        ) : (
                            <>
                                <h4 className="font-medium text-foreground">No surrogates yet</h4>
                                <p className="text-sm text-muted-foreground mt-1 mb-4">
                                    Add your first surrogate to see the distribution.
                                </p>
                                <Link href="/surrogates?new=true" className={buttonVariants({ size: "sm" })}>
                                    <PlusIcon className="size-4 mr-2" />
                                    Add Surrogate
                                </Link>
                            </>
                        )}
                    </div>
                ) : (
                    <ChartContainer
                        config={{
                            count: {
                                label: "Surrogates",
                                color: "var(--primary)",
                            },
                        }}
                        className="h-[320px] w-full"
                    >
                        <BarChart
                            data={chartData}
                            layout="vertical"
                            barSize={18}
                            barCategoryGap={10}
                            margin={{ left: 0, right: 24, top: 8, bottom: 8 }}
                        >
                            <CartesianGrid
                                horizontal={false}
                                vertical={true}
                                strokeDasharray="3 3"
                                stroke="var(--border)"
                                strokeOpacity={0.15}
                            />
                            <XAxis
                                type="number"
                                tickLine={false}
                                axisLine={false}
                                tick={{ fontSize: 12 }}
                                tickCount={4}
                                tickFormatter={(value) =>
                                    viewMode === "percent" ? `${value}%` : value.toString()
                                }
                            />
                            <YAxis
                                type="category"
                                dataKey="status"
                                tickLine={false}
                                axisLine={false}
                                width={140}
                                tick={({ x, y, payload }: { x: number; y: number; payload: { value: string } }) => {
                                    const lines = wrapStageLabel(payload.value)
                                    return (
                                        <g transform={`translate(${x},${y})`}>
                                            <text
                                                x={0}
                                                y={0}
                                                dy={4}
                                                textAnchor="end"
                                                fill="currentColor"
                                                fontSize={12}
                                                className="fill-muted-foreground"
                                            >
                                                {lines.map((line, index) => (
                                                    <tspan key={`${line}-${index}`} x={0} dy={index === 0 ? 0 : 12}>
                                                        {line}
                                                    </tspan>
                                                ))}
                                            </text>
                                        </g>
                                    )
                                }}
                            />
                            <Tooltip
                                cursor={{ fill: "var(--muted)", opacity: 0.3 }}
                                content={({ active, payload }) => {
                                    if (!active || !payload?.length) return null
                                    const data = payload[0].payload
                                    return (
                                        <div className="rounded-lg border bg-background p-2 shadow-md">
                                            <p className="font-medium">
                                                {data.status}
                                                {data.groupedCount ? ` (${data.groupedCount} stages)` : ""}
                                            </p>
                                            <p className="text-sm text-muted-foreground">
                                                {data.count.toLocaleString()} surrogates ({data.percent}%)
                                            </p>
                                            {data.groupedCount ? (
                                                <p className="text-xs text-muted-foreground mt-1">
                                                    Includes low-volume stages
                                                </p>
                                            ) : (
                                                <p className="text-xs text-muted-foreground mt-1">
                                                    Click to view
                                                </p>
                                            )}
                                        </div>
                                    )
                                }}
                            />
                            <Bar
                                dataKey={viewMode === "percent" ? "percent" : "count"}
                                radius={[0, 4, 4, 0]}
                                onClick={(data: { payload?: { stage_id: string | null } }) => {
                                    if (data.payload?.stage_id) {
                                        handleBarClick({ stage_id: data.payload.stage_id })
                                    }
                                }}
                            >
                                {viewMode === "count" && (
                                    <LabelList
                                        dataKey="count"
                                        position="right"
                                        formatter={(v) => String(v)}
                                        className="fill-muted-foreground text-xs"
                                    />
                                )}
                                {viewMode === "percent" && (
                                    <LabelList
                                        dataKey="percent"
                                        position="right"
                                        formatter={(v) => `${v}%`}
                                        className="fill-muted-foreground text-xs"
                                    />
                                )}
                                {chartData.map((entry, index) => (
                                    <Cell
                                        key={`cell-${index}`}
                                        fill={entry.fill}
                                        className={`hover:opacity-80 transition-opacity ${entry.stage_id ? "cursor-pointer" : "cursor-default"}`}
                                    />
                                ))}
                            </Bar>
                        </BarChart>
                    </ChartContainer>
                )}
            </CardContent>
        </Card>
    )
}
