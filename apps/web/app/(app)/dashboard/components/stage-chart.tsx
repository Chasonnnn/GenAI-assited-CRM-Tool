"use client"

import { useState } from "react"
import type { Route } from "next"
import dynamic from "next/dynamic"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { buttonVariants } from "@/components/ui/button-variants"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Skeleton } from "@/components/ui/skeleton"
import {
    PieChartIcon,
    AlertCircleIcon,
    PlusIcon,
    LockIcon,
} from "lucide-react"
import Link from "@/components/app-link"
import { useDonorsByStatus, useSurrogatesByStatus } from "@/lib/hooks/use-analytics"
import { useSurrogateStats } from "@/lib/hooks/use-surrogates"
import { useDefaultPipeline } from "@/lib/hooks/use-pipelines"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { useAuth } from "@/lib/auth-context"
import { useDashboardFilters } from "../context/dashboard-filters"
import { ApiError } from "@/lib/api"
import { buildStageChartData, type StageChartBuildResult } from "./stage-chart-utils"

type ViewMode = "count" | "percent"
type PipelineSubject = "surrogate" | "egg" | "sperm"
type StageChartDatum = StageChartBuildResult["data"][number]

type StageDistributionChartProps = {
    chartData: StageChartDatum[]
    viewMode: ViewMode
    subjectPlural: string
    onBarClick: (data: { stage_id: string | null }) => void
}

const PIPELINE_SUBJECT_LABELS: Record<PipelineSubject, string> = {
    surrogate: "Surrogates",
    egg: "Egg Donors",
    sperm: "Sperm Donors",
}

const STAGE_CHART_SKELETON_KEYS = [
    "skeleton-stage-1",
    "skeleton-stage-2",
    "skeleton-stage-3",
    "skeleton-stage-4",
    "skeleton-stage-5",
    "skeleton-stage-6",
]

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

const StageDistributionChart = dynamic<StageDistributionChartProps>(
    () =>
        Promise.all([
            import("recharts"),
            import("@/components/ui/chart"),
        ]).then(([{
            Bar,
            BarChart,
            XAxis,
            YAxis,
            Cell,
            Tooltip,
            CartesianGrid,
            LabelList,
        }, { ChartContainer }]) => {
            function StageDistributionChartComponent({
                chartData,
                viewMode,
                subjectPlural,
                onBarClick,
            }: StageDistributionChartProps) {
                return (
                    <ChartContainer
                        config={{
                            count: {
                                label: subjectPlural,
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
                                tick={({ x, y, payload }: { x: string | number; y: string | number; payload: { value: string } }) => {
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
                                                    <tspan key={line} x={0} dy={index === 0 ? 0 : 12}>
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
                                    const entry = payload[0]
                                    if (!entry) return null
                                    const data = entry.payload
                                    return (
                                        <div className="rounded-lg border bg-background p-2 shadow-md">
                                            <p className="font-medium">
                                                {data.status}
                                                {data.groupedCount ? ` (${data.groupedCount} stages)` : ""}
                                            </p>
                                            <p className="text-sm text-muted-foreground">
                                                {data.count.toLocaleString()} {subjectPlural.toLowerCase()} ({data.percent}%)
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
                                        onBarClick({ stage_id: data.payload.stage_id })
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
                                {chartData.map((entry) => (
                                    <Cell
                                        key={`${entry.stage_id ?? "grouped"}:${entry.status}`}
                                        fill={entry.fill}
                                        className={`hover:opacity-80 transition-opacity ${entry.stage_id ? "cursor-pointer" : "cursor-default"}`}
                                    />
                                ))}
                            </Bar>
                        </BarChart>
                    </ChartContainer>
                )
            }

            return StageDistributionChartComponent
        }),
    {
        ssr: false,
        loading: () => <Skeleton className="h-[320px] w-full" />,
    },
)

export function StageChart() {
    const { push } = useRouter()
    const { user } = useAuth()
    const { filters, getDateParams, resetFilters, hasActiveFilters } = useDashboardFilters()
    const [viewMode, setViewMode] = useState<ViewMode>("count")
    const [selectedSubject, setSelectedSubject] = useState<PipelineSubject>("surrogate")
    const permissionsQuery = useEffectivePermissions(user?.user_id ?? null)
    const isDeveloper = user?.role === "developer"
    const canViewDonors = isDeveloper
        || (permissionsQuery.data?.permissions ?? []).includes("view_donors")
    const subject = canViewDonors ? selectedSubject : "surrogate"

    const dateParams = getDateParams()
    const statusParams = {
        ...dateParams,
        ...(filters.assigneeId ? { owner_id: filters.assigneeId } : {}),
    }
    const surrogateStatusQuery = useSurrogatesByStatus(statusParams)
    const eggStatusQuery = useDonorsByStatus(
        { donor_type: "egg", ...statusParams },
        { enabled: canViewDonors && subject === "egg", surface: "dashboard" },
    )
    const spermStatusQuery = useDonorsByStatus(
        { donor_type: "sperm", ...statusParams },
        { enabled: canViewDonors && subject === "sperm", surface: "dashboard" },
    )
    const statusQuery = subject === "egg"
        ? eggStatusQuery
        : subject === "sperm"
            ? spermStatusQuery
            : surrogateStatusQuery
    const { data: statusData, isLoading, isError, error, refetch } = statusQuery
    const orgStatsQuery = useSurrogateStats()
    const surrogatePipelineQuery = useDefaultPipeline()
    const eggPipelineQuery = useDefaultPipeline("egg_donor", canViewDonors)
    const spermPipelineQuery = useDefaultPipeline("sperm_donor", canViewDonors)
    const pipeline = subject === "egg"
        ? eggPipelineQuery.data
        : subject === "sperm"
            ? spermPipelineQuery.data
            : surrogatePipelineQuery.data
    const isRestricted = error instanceof ApiError && error.status === 403

    // Build stage color map from pipeline (NOT from API)
    const stageColorMap = pipeline?.stages
        ? new Map(pipeline.stages.map((s) => [s.id, s.color]))
        : new Map<string, string>()

    // Transform and sort data by order
    const { data: chartData, total: totalCount } = buildStageChartData(statusData, stageColorMap)
    const subjectPlural = PIPELINE_SUBJECT_LABELS[subject]
    const orgTotal = subject === "surrogate" ? orgStatsQuery.data?.total : totalCount
    const hasOrgRecords = (orgTotal ?? 0) > 0

    const buildStageUrl = (stageId: string) => {
        const params = new URLSearchParams()
        if (subject === "egg" || subject === "sperm") {
            params.set("type", subject)
        }
        params.set("stage", stageId)

        // Include current date filters
        if (filters.dateRange !== "all") {
            params.set("range", filters.dateRange)
            if (dateParams.from_date) params.set("from", dateParams.from_date)
            if (dateParams.to_date) params.set("to", dateParams.to_date)
        }
        if (filters.assigneeId) {
            params.set("owner_id", filters.assigneeId)
        }

        if (subject === "egg" || subject === "sperm") {
            return `/donors?${params.toString()}`
        }
        return `/surrogates?${params.toString()}`
    }

    // Handle bar click - navigate to surrogates filtered by stage
    const handleBarClick = (data: { stage_id: string | null }) => {
        if (!data.stage_id) return
        push(buildStageUrl(data.stage_id) as Route)
    }

    const stageLinkEntries = chartData.flatMap((entry) => {
        if (!entry.stage_id) return []
        return [{ ...entry, stage_id: entry.stage_id }]
    })

    return (
        <Card className="h-full flex flex-col gap-0 p-0">
            <CardHeader className="p-6 pb-0 gap-0">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                    <CardTitle className="text-base font-semibold">Pipeline Distribution</CardTitle>
                    <div className="flex flex-wrap items-center gap-2">
                        {canViewDonors && (
                            <ToggleGroup
                                value={[subject]}
                                aria-label="Pipeline subject"
                                onValueChange={(value) => {
                                    const nextValue = Array.isArray(value) ? value[0] : value
                                    if (nextValue === "surrogate" || nextValue === "egg" || nextValue === "sperm") {
                                        setSelectedSubject(nextValue)
                                    }
                                }}
                                variant="outline"
                                size="sm"
                                spacing={0}
                                className="h-8"
                            >
                                <ToggleGroupItem value="surrogate" className="h-8">Surrogates</ToggleGroupItem>
                                <ToggleGroupItem value="egg" className="h-8">Egg Donors</ToggleGroupItem>
                                <ToggleGroupItem value="sperm" className="h-8">Sperm Donors</ToggleGroupItem>
                            </ToggleGroup>
                        )}
                        <ToggleGroup
                            value={[viewMode]}
                            aria-label="Pipeline distribution view mode"
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
                </div>
                <CardDescription className="text-sm text-muted-foreground mb-4">
                    {totalCount.toLocaleString()} {subjectPlural.toLowerCase()} in pipeline
                </CardDescription>
            </CardHeader>
            <CardContent className="px-4 pb-6 pt-0 flex-1">
                {isLoading ? (
                    <div className="h-[320px] space-y-3">
                        {STAGE_CHART_SKELETON_KEYS.map((rowKey) => (
                            <div key={rowKey} className="flex items-center gap-3">
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
                ) : totalCount === 0 || chartData.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-[320px] text-center">
                        <PieChartIcon className="size-12 text-muted-foreground/50 mb-4" />
                        {orgTotal === 0 ? (
                            <>
                                <h4 className="font-medium text-foreground">No {subjectPlural.toLowerCase()} yet</h4>
                                <Link
                                    href={subject === "surrogate" ? "/surrogates?new=true" : `/donors?type=${subject}&new=true`}
                                    className={`${buttonVariants({ size: "sm" })} mt-4`}
                                >
                                    <PlusIcon className="size-4 mr-2" />
                                    Add {subject === "surrogate" ? "Surrogate" : "Donor"}
                                </Link>
                            </>
                        ) : hasActiveFilters ? (
                            <>
                                <h4 className="font-medium text-foreground">No {subjectPlural.toLowerCase()} match your filters</h4>
                                <p className="text-sm text-muted-foreground mt-1 mb-4">
                                    Try adjusting or clearing filters to see results.
                                </p>
                                <Button variant="outline" size="sm" onClick={resetFilters}>
                                    Reset filters
                                </Button>
                            </>
                        ) : hasOrgRecords ? (
                            <>
                                <h4 className="font-medium text-foreground">Analytics unavailable</h4>
                                <p className="text-sm text-muted-foreground mt-1">
                                    Pipeline distribution is temporarily unavailable.
                                </p>
                            </>
                        ) : (
                            <>
                                <h4 className="font-medium text-foreground">No {subjectPlural.toLowerCase()} yet</h4>
                                <Link
                                    href={subject === "surrogate" ? "/surrogates?new=true" : `/donors?type=${subject}&new=true`}
                                    className={`${buttonVariants({ size: "sm" })} mt-4`}
                                >
                                    <PlusIcon className="size-4 mr-2" />
                                    Add {subject === "surrogate" ? "Surrogate" : "Donor"}
                                </Link>
                            </>
                        )}
                    </div>
                ) : (
                    <>
                        <StageDistributionChart
                            chartData={chartData}
                            viewMode={viewMode}
                            subjectPlural={subjectPlural}
                            onBarClick={handleBarClick}
                        />
                        <div className="sr-only" aria-label="Pipeline stage links">
                            <ul>
                                {stageLinkEntries.map((entry) => (
                                    <li key={entry.stage_id}>
                                        <Link href={buildStageUrl(entry.stage_id)}>
                                            View {entry.status} {subjectPlural.toLowerCase()}
                                        </Link>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </>
                )}
            </CardContent>
        </Card>
    )
}
